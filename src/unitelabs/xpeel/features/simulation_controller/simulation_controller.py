import typing_extensions as typing

from unitelabs.cdk.features.core.simulation_controller import (
    SimulationControllerBase,
    StartRealModeFailed,
    StartSimulationModeFailed,
)

from ...io import SerialCommunicationError, XPeelProtocol


class SimulationController(SimulationControllerBase):
    """
    Switch between the instrument on the serial port (Real Mode) and a simulated instrument (Simulation Mode).

    The simulated instrument completes every command instantly and without error.
    """

    def __init__(self, protocol: XPeelProtocol):
        super().__init__()

        self.protocol = protocol

    @typing.override
    async def start_simulation_mode(self) -> None:
        if self._simulation_mode:
            return

        if self.protocol.is_busy:
            msg = "Cannot start the Simulation Mode while a command is executed. Wait for it to complete."
            raise StartSimulationModeFailed(msg)

        await self.protocol.open_simulator()
        self._simulation_mode = True

    @typing.override
    async def start_real_mode(self) -> None:
        if not self._simulation_mode:
            return

        if self.protocol.is_busy:
            msg = "Cannot start the Real Mode while a command is executed. Wait for it to complete."
            raise StartRealModeFailed(msg)

        try:
            await self.protocol.open_instrument()
        except SerialCommunicationError as error:
            await self.protocol.open_simulator()
            raise StartRealModeFailed(str(error)) from error

        self._simulation_mode = False

    @typing.override
    async def simulation_mode(self) -> bool:
        return self._simulation_mode
