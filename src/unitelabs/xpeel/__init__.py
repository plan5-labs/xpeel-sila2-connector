import collections.abc
from importlib.metadata import version

from unitelabs.cdk import Connector
from unitelabs.cdk.features.core.lock_controller import LockController

from .config import XPeelConfig
from .features.automated_plate_seal_remover_controller import AutomatedPlateSealRemoverController
from .features.simulation_controller import SimulationController
from .io import XPeelProtocol

__version__ = version("unitelabs-xpeel")


async def create_app(config: XPeelConfig) -> collections.abc.AsyncGenerator[Connector, None]:
    """Create the connector application."""

    app = Connector(config)
    protocol = XPeelProtocol(port=config.serial_port, treat_warnings_as_errors=config.treat_warnings_as_errors)
    simulation_controller = SimulationController(protocol)

    try:
        if config.simulation_mode:
            await simulation_controller.start_simulation_mode()
        else:
            await protocol.open_instrument()

        app.register(LockController())
        app.register(simulation_controller)
        app.register(AutomatedPlateSealRemoverController(protocol))

        yield app
    finally:
        protocol.close()
