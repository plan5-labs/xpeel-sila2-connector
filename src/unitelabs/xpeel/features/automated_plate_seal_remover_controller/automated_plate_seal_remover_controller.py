import typing_extensions as typing

from unitelabs.cdk import Replay, sila

from ...io import COMMAND_ERRORS, XPeelProtocol


class AutomatedPlateSealRemoverController(sila.Feature):
    """
    Control the Automated Plate Seal Remover made by Azenta Life Sciences.

    The Automated Plate Seal Remover (formerly known as XPeel) is an automated seal remover.
    It can remove various seals from various types of microplates.
    Model number: XP-A_100V
    Product URL: https://www.azenta.com/products/automated-plate-seal-remover-formerly-xpeel
    """

    def __init__(self, protocol: XPeelProtocol):
        super().__init__(originator="org.riken", category="instruments")

        self.protocol = protocol

    @sila.ObservableProperty()
    async def subscribe_status(
        self,
    ) -> sila.Stream[typing.Annotated[int, sila.constraints.MinimalInclusive(0), sila.constraints.MaximalInclusive(3)]]:
        """
        Return the status of the instrument. This property is common to all instruments.

        0: Not Connected
        1: Idle
        2: Running
        3: Error
        """

        subscription = self.protocol.status.subscribe(replay=Replay.CURRENT)
        try:
            async for status in subscription:
                yield status.value
        finally:
            subscription.terminate()

    @sila.ObservableCommand(errors=COMMAND_ERRORS)
    async def peel(
        self,
        begin_peel_location: typing.Annotated[
            int, sila.constraints.MinimalInclusive(1), sila.constraints.MaximalInclusive(9)
        ],
        adhesion_time: typing.Annotated[
            int, sila.constraints.MinimalInclusive(1), sila.constraints.MaximalInclusive(4)
        ],
    ) -> str:
        """
        Peel the seal attached to the plate.

        Status required to execute this command: Idle
        Status while this command is running: Running
        Status after this command finishes: Idle if it completes normally, Error if it fails

        Depending on the plate and the specified parameters, the instrument may return an
        error even if the seal is successfully removed. Please try different parameters to
        find a combination that allows the result to be recognized correctly.

        Args:
          BeginPeelLocation: Parameter for the beginning location and peeling speed.
            1: Default -2 mm / fast
            2: Default -2 mm / slow
            3: Default / fast
            4: Default / slow
            5: Default +2 mm / fast
            6: Default +2 mm / slow
            7: Default +4 mm / fast
            8: Default +4 mm / slow
            9: custom / custom
          AdhesionTime: Adhesion time between the peeler and the seal.
            1: 2.5 seconds
            2: 5.0 seconds
            3: 7.5 seconds
            4: 10.0 seconds

        Returns:
          InstrumentWarningMessage: Warning message corresponding to the error code returned
            by the instrument. If there is no error code that indicates an instrument warning
            (i.e., all error codes indicate "No error" or non-warning error), the empty string
            will be returned.
        """

        return await self.protocol.xpeel(begin_peel_location, adhesion_time)

    @sila.ObservableCommand(errors=COMMAND_ERRORS)
    async def get_tape_left(self) -> tuple[int, int, str]:
        """
        Get the tape left on the supply spool and the capacity left on the take-up spool.

        Returns the number of seal removals remaining on the supply spool and the number of
        seal removals that the remaining space on the take-up spool can accommodate.

        This command may not work as intended because the instrument command returns an
        unexpected value due to a bug in the current firmware version.

        Status required to execute this command: Idle
        Status while this command is running: Same as the status at the start of execution
        Status after this command finishes: Unchanged if it completes normally, Error if it
        fails

        Returns:
          SupplySpoolRemaining: The number of seal removals remaining on the supply spool.
          TakeUpSpoolRemaining: The number of seal removals that can be accommodated by the
            remaining space on the take-up spool.
          InstrumentWarningMessage: Warning message corresponding to the error code returned
            by the instrument. If there is no error code that indicates an instrument warning
            (i.e., all error codes indicate "No error" or non-warning error), the empty string
            will be returned.
        """

        tape = await self.protocol.tapeleft()

        return tape.supply_spool_remaining, tape.take_up_spool_remaining, tape.warning_message

    @sila.ObservableCommand(errors=COMMAND_ERRORS)
    async def reset_instrument(self) -> str:
        """
        Advance to fresh tape and return the elevator and conveyor to their home positions.

        Moves the spool forward a few inches to access fresh tape, returns the elevator and
        conveyor to their home positions, and prepares the plate for pickup. Variables such as
        error codes and remaining tape information will be preserved.

        Status required to execute this command: Idle
        Status while this command is running: Running
        Status after this command finishes: Idle if it completes normally, Error if it fails

        Returns:
          InstrumentWarningMessage: Warning message corresponding to the error code returned
            by the instrument. If there is no error code that indicates an instrument warning
            (i.e., all error codes indicate "No error" or non-warning error), the empty string
            will be returned.
        """

        return await self.protocol.reset()

    @sila.ObservableCommand(errors=COMMAND_ERRORS)
    async def reset(self) -> str:
        """
        Reset the server to its Idle state. This command is common to all instruments.

        Restarts the instrument, which then returns to its home position. Use this command to
        recover from the Error status.

        Status required to execute this command: Idle, Error
        Status while this command is running: Same as the status at the start of execution
        Status after this command finishes: Idle if it completes normally, Error if it fails

        Returns:
          InstrumentWarningMessage: Warning message corresponding to the error code returned
            by the instrument. If there is no error code that indicates an instrument warning
            (i.e., all error codes indicate "No error" or non-warning error), the empty string
            will be returned.
        """

        return await self.protocol.restart()
