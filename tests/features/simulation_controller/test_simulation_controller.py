import sys

import pytest
from unitelabs.cdk.features.core.simulation_controller import StartRealModeFailed

from unitelabs.xpeel.features.simulation_controller import SimulationController
from unitelabs.xpeel.io import InstrumentStatus, XPeelProtocol
from unitelabs.xpeel.io.simulation import STUBS


@pytest.fixture
async def controller():
    protocol = XPeelProtocol(port="/dev/does-not-exist")
    controller = SimulationController(protocol)
    await controller.start_simulation_mode()

    yield controller

    protocol.close()


async def test_starts_in_simulation_mode(controller: SimulationController):
    assert await controller.simulation_mode() is True
    assert controller.protocol.status.current == InstrumentStatus.IDLE
    assert await controller.protocol.xpeel(4, 1) == ""


async def test_stays_in_simulation_mode_without_instrument(controller: SimulationController, monkeypatch):
    monkeypatch.setattr("unitelabs.xpeel.io.protocol.OPEN_TIMEOUT", 0.1)

    with pytest.raises(StartRealModeFailed, match="/dev/does-not-exist"):
        await controller.start_real_mode()

    assert await controller.simulation_mode() is True
    assert controller.protocol.status.current == InstrumentStatus.IDLE
    assert await controller.protocol.xpeel(4, 1) == ""


@pytest.mark.skipif(sys.platform == "win32", reason="The mock serial device requires a pty.")
async def test_switches_to_real_mode_and_back(serial_device):
    serial_device.stubs = STUBS
    protocol = XPeelProtocol(port=serial_device.port)
    controller = SimulationController(protocol)
    await controller.start_simulation_mode()

    try:
        await controller.start_real_mode()
        assert await controller.simulation_mode() is False
        assert await protocol.tapeleft() is not None

        await controller.start_simulation_mode()
        assert await controller.simulation_mode() is True
        assert await protocol.xpeel(4, 1) == ""
    finally:
        protocol.close()
