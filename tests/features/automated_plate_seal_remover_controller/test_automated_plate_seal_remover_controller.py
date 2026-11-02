import asyncio
import collections.abc
import pathlib
import socket

import pytest
from sila.client import Client, ClientConfig
from sila.framework.fdl.serializer import Serializer
from unitelabs.bus.testing import create_mock_connection, stub_maker

import sila
from unitelabs.cdk import Connector
from unitelabs.xpeel import XPeelConfig, create_app
from unitelabs.xpeel.features.automated_plate_seal_remover_controller import AutomatedPlateSealRemoverController
from unitelabs.xpeel.io import XPeelProtocol

ORIGINAL_DEFINITION = pathlib.Path(__file__).with_name("AutomatedPlateSealRemoverController-v1_0.sila.xml")

ACK = b"*ack\r\n"
READY = b"*ready:00,00,00\r\n"


def data_type(element) -> str:
    return Serializer.serialize(element.data_type.serialize, remove_whitespace=True)


def interface(feature: sila.framework.Feature) -> dict:
    """Everything a client binds to: identifiers, observability, data types and errors."""

    return {
        "identifier": str(feature.fully_qualified_identifier),
        "commands": {
            identifier: {
                "observable": isinstance(command, sila.framework.ObservableCommand),
                "parameters": [(element.identifier, data_type(element)) for element in command.parameters.values()],
                "responses": [(element.identifier, data_type(element)) for element in command.responses.values()],
                "intermediate_responses": [
                    (element.identifier, data_type(element))
                    for element in getattr(command, "intermediate_responses", {}).values()
                ],
                "errors": sorted(command.errors),
            }
            for identifier, command in feature.commands.items()
        },
        "properties": {
            identifier: {
                "observable": isinstance(prop, sila.framework.ObservableProperty),
                "data_type": data_type(prop),
                "errors": sorted(prop.errors),
            }
            for identifier, prop in feature.properties.items()
        },
        "metadata": sorted(feature.metadata),
        "errors": sorted(feature.errors),
    }


@pytest.fixture
async def app() -> collections.abc.AsyncGenerator[Connector, None]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    config = XPeelConfig(discovery=None)
    config.sila_server.hostname = "127.0.0.1"
    config.sila_server.port = port

    factory = create_app(config)
    connector = await factory.__anext__()
    await connector.start()

    yield connector

    await connector.stop()
    await factory.aclose()


@pytest.fixture
async def client(app: Connector) -> collections.abc.AsyncGenerator[Client, None]:
    client = Client(ClientConfig(hostname="127.0.0.1", port=app.config.sila_server.port, tls=False))
    await client.open()

    yield client

    await client.close()


@pytest.fixture
def xpeel(app: Connector) -> XPeelProtocol:
    return app.get_feature(AutomatedPlateSealRemoverController).protocol


async def complete(execution) -> sila.framework.Native:
    async for _ in await execution.subscribe_status():
        pass

    return await execution.get_responses()


async def test_definition_matches_original(app: Connector):
    feature = app.get_feature(AutomatedPlateSealRemoverController)
    definition = Serializer.serialize(feature.serialize)

    generated = sila.framework.Feature.from_definition(definition)
    original = sila.framework.Feature.from_definition(ORIGINAL_DEFINITION.read_text())

    assert interface(generated) == interface(original)


async def test_peel(client: Client):
    responses = await complete(
        await client.AutomatedPlateSealRemoverController.Peel(BeginPeelLocation=4, AdhesionTime=1)
    )

    assert responses.InstrumentWarningMessage == ""


async def test_peel_rejects_invalid_parameters(client: Client):
    with pytest.raises(sila.framework.errors.ValidationError):
        await client.AutomatedPlateSealRemoverController.Peel(BeginPeelLocation=10, AdhesionTime=1)


async def test_get_tape_left(client: Client):
    responses = await complete(await client.AutomatedPlateSealRemoverController.GetTapeLeft())

    assert (responses.SupplySpoolRemaining, responses.TakeUpSpoolRemaining, responses.InstrumentWarningMessage) == (
        260,
        240,
        "",
    )


async def test_reset_instrument(client: Client):
    responses = await complete(await client.AutomatedPlateSealRemoverController.ResetInstrument())

    assert responses.InstrumentWarningMessage == ""


async def test_reset(client: Client):
    responses = await complete(await client.AutomatedPlateSealRemoverController.Reset())

    assert responses.InstrumentWarningMessage == ""


async def test_status(client: Client):
    assert await client.AutomatedPlateSealRemoverController.Status.read() == 1


async def test_errors_and_recovery(client: Client, xpeel: XPeelProtocol):
    feature = client.AutomatedPlateSealRemoverController
    stubs = [
        stub_maker(b"*xpeel:41\r\n", [ACK, b"*ready:04,00,00\r\n"]),
        stub_maker(b"*restart\r\n", [ACK, b"*poweron\r\n", b"*homing\r\n", READY]),
    ]
    await xpeel.connect(create_mock_connection, stubs=stubs)
    await asyncio.sleep(0)

    with pytest.raises(sila.framework.DefinedExecutionError) as error:
        await complete(await feature.Peel(BeginPeelLocation=4, AdhesionTime=1))
    assert error.value.identifier == "InstrumentErrorDetected"
    assert "Seal not removed" in str(error.value)
    assert await feature.Status.read() == 3

    with pytest.raises(sila.framework.DefinedExecutionError) as error:
        await complete(await feature.Peel(BeginPeelLocation=4, AdhesionTime=1))
    assert error.value.identifier == "InvalidInstrumentStatusError"

    await complete(await feature.Reset())
    assert await feature.Status.read() == 1
