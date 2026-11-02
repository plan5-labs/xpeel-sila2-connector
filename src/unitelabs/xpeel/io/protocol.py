import asyncio
import collections.abc
import contextlib
import dataclasses
import enum
import logging

import typing_extensions as typing
from unitelabs.bus import CommandExecutionError, Protocol, TransportFactory, create_serial_connection
from unitelabs.cdk import Subject

from .commands import ACK, HOMING, POWERON, TAPE, Reply, XPeelCommand
from .errors import InvalidInstrumentStatusError, SerialCommunicationError
from .simulation import create_simulated_connection

logger = logging.getLogger(__name__)

BAUDRATE = 9600
"""The instrument communicates at 9600 baud, with 8 data bits, no parity and 1 stop bit."""

OPEN_TIMEOUT = 5.0
"""Seconds to wait for the connection to the instrument to open."""


class InstrumentStatus(enum.IntEnum):
    """The status of the instrument, as tracked by the connector."""

    NOT_CONNECTED = 0
    """The connector has no connection to the instrument."""

    IDLE = 1
    """The instrument accepts commands."""

    RUNNING = 2
    """The instrument is peeling a seal or moving to its home position."""

    ERROR = 3
    """A command failed. Only a restart is accepted, which clears the error."""


HINTS: dict[InstrumentStatus, str] = {
    InstrumentStatus.NOT_CONNECTED: "Check that the instrument is connected.",
    InstrumentStatus.IDLE: "",
    InstrumentStatus.RUNNING: "Wait for the running command to complete.",
    InstrumentStatus.ERROR: "Restart the instrument to clear the error.",
}


@dataclasses.dataclass(frozen=True)
class TapeLeft:
    """
    The tape left on the instrument.

    Attributes:
      supply_spool_remaining: The number of seal removals remaining on the supply spool.
      take_up_spool_remaining: The number of seal removals that the take-up spool has room for.
      warning_message: The message of the latest warning the instrument reported, or an empty string.
    """

    supply_spool_remaining: int
    take_up_spool_remaining: int
    warning_message: str


class XPeelProtocol(Protocol):
    """
    The RS-232 command set of the XPeel automated plate seal remover.

    Every command requires the instrument to be in a certain status, and a failed command leaves
    the instrument in the `ERROR` status until it is restarted.

    Args:
      port: The serial port the instrument is connected to.
      treat_warnings_as_errors: Whether commands fail on warnings, e.g. when the tape runs low,
        instead of returning them.
    """

    def __init__(self, port: str, *, treat_warnings_as_errors: bool = False) -> None:
        super().__init__(create_serial_connection, port=port, baudrate=BAUDRATE)

        self.port = port
        self.treat_warnings_as_errors = treat_warnings_as_errors
        self.status = Subject[InstrumentStatus](maxsize=100, initial_value=InstrumentStatus.NOT_CONNECTED)
        """The status of the instrument, `NOT_CONNECTED` whenever the connection is down."""

        self._state = InstrumentStatus.IDLE
        self._connected = False
        self._operations = 0

    @property
    @typing.override
    def logger(self) -> logging.Logger:
        return logger

    @property
    def is_busy(self) -> bool:
        """Whether a command is being executed."""

        return self._operations > 0

    async def open_instrument(self) -> None:
        """
        Connect to the instrument on the serial port, closing any previous connection.

        Raises:
          SerialCommunicationError: If the serial port cannot be opened.
        """

        await self._reopen(create_serial_connection, port=self.port, baudrate=BAUDRATE)

    async def open_simulator(self) -> None:
        """Connect to a simulated instrument, closing any previous connection."""

        await self._reopen(create_simulated_connection)

    @typing.override
    async def open(self, validation_timeout: float = 1.0, **validation_kwargs) -> None:
        """
        Open the connection, giving up after `OPEN_TIMEOUT` seconds.

        A serial port that fails to open is reported to the event loop instead of raising, so the
        wait is bounded here.

        Args:
          validation_timeout: How long in seconds to wait for the device to be validated.
          **validation_kwargs: Passed on to `Protocol.validate`.

        Raises:
          SerialCommunicationError: If the connection does not open in time.
        """

        try:
            await asyncio.wait_for(super().open(validation_timeout, **validation_kwargs), timeout=OPEN_TIMEOUT)
        except (TimeoutError, asyncio.TimeoutError):
            msg = (
                f"Could not open the serial port '{self.port}' within {OPEN_TIMEOUT} s. "
                "Check the configured port and that the instrument is connected."
            )
            raise SerialCommunicationError(msg) from None

    @typing.override
    def connection_made(self, transport: asyncio.Transport) -> None:
        super().connection_made(transport)

        self._connected = True
        self._publish()

    @typing.override
    def connection_lost(self, exc: Exception | None = None) -> None:
        self._connected = False
        self._publish()

        super().connection_lost(exc)

    async def xpeel(self, begin_peel_location: int, adhesion_time: int) -> str:
        """
        Remove the seal from the plate.

        Requires the status `IDLE`, which is `RUNNING` until the seal is removed.

        Args:
          begin_peel_location: Where to begin peeling and how fast to peel, from 1 to 9.
          adhesion_time: How long the peeler adheres to the seal, from 1 to 4.

        Returns:
          The message of the latest warning the instrument reported, or an empty string.
        """

        with self._operation(InstrumentStatus.IDLE, during=InstrumentStatus.RUNNING, after=InstrumentStatus.IDLE):
            reply = await self._execute(XPeelCommand(f"*xpeel:{begin_peel_location}{adhesion_time}"))
            warning = reply.check_error_codes(treat_warnings_as_errors=self.treat_warnings_as_errors)
            reply.match(ACK)

        return warning

    async def tapeleft(self) -> TapeLeft:
        """
        Get the tape left on the supply spool and the room left on the take-up spool.

        Requires the status `IDLE`, which it keeps.

        Returns:
          The tape left.
        """

        with self._operation(InstrumentStatus.IDLE):
            reply = await self._execute(XPeelCommand("*tapeleft"))
            warning = reply.check_error_codes(treat_warnings_as_errors=self.treat_warnings_as_errors)
            _, tape = reply.match(ACK, TAPE)

        return TapeLeft(
            supply_spool_remaining=int(tape[1]) * 10,
            take_up_spool_remaining=int(tape[2]) * 10,
            warning_message=warning,
        )

    async def reset(self) -> str:
        """
        Advance the spool to fresh tape, home the elevator and conveyor, and present the plate.

        Keeps error codes and the tape left. Requires the status `IDLE`, which is `RUNNING` until
        the instrument is home.

        Returns:
          The message of the latest warning the instrument reported, or an empty string.
        """

        with self._operation(InstrumentStatus.IDLE, during=InstrumentStatus.RUNNING, after=InstrumentStatus.IDLE):
            reply = await self._execute(XPeelCommand("*reset"))
            warning = reply.check_error_codes(treat_warnings_as_errors=self.treat_warnings_as_errors)
            # Not documented in the manual, but the instrument reports `*homing` after `*ack`.
            reply.match(ACK, HOMING)

        return warning

    async def restart(self) -> str:
        """
        Restart the instrument, which homes it and clears the `ERROR` status.

        Requires the status `IDLE` or `ERROR`, and is `IDLE` once the instrument has restarted.

        Returns:
          The message of the latest warning the instrument reported, or an empty string.
        """

        with self._operation(InstrumentStatus.IDLE, InstrumentStatus.ERROR, after=InstrumentStatus.IDLE):
            reply = await self._execute(XPeelCommand("*restart"))
            warning = reply.check_error_codes(treat_warnings_as_errors=self.treat_warnings_as_errors)
            reply.match(ACK, POWERON, HOMING)

        return warning

    async def _reopen(self, transport_factory: TransportFactory, **transport_kwargs) -> None:
        """Replace the connection with a new one created by `transport_factory`."""

        self.close()
        self._transport_factory = transport_factory
        self._transport_kwargs = transport_kwargs
        self._state = InstrumentStatus.IDLE

        await self.open()

    async def _execute(self, command: XPeelCommand) -> Reply:
        """
        Send `command` and wait for its reply.

        Raises:
          SerialCommunicationError: If the command cannot be sent or no reply arrives in time.
        """

        try:
            return await self.execute(command)
        except (TimeoutError, asyncio.TimeoutError):
            msg = (
                f"No complete response to '{command.message}' received within {command.timeout} s. "
                f"Check that the instrument is powered on and connected to '{self.port}'."
            )
            raise SerialCommunicationError(msg) from None
        except (CommandExecutionError, OSError) as error:
            msg = f"Failed to send '{command.message}' to the instrument on '{self.port}': {error}"
            raise SerialCommunicationError(msg) from error

    @contextlib.contextmanager
    def _operation(
        self,
        *allowed: InstrumentStatus,
        during: InstrumentStatus | None = None,
        after: InstrumentStatus | None = None,
    ) -> collections.abc.Iterator[None]:
        """
        Track the status around a command.

        Args:
          *allowed: The statuses the command requires.
          during: The status while the command runs, if it changes.
          after: The status once the command succeeded, if it changes.

        Raises:
          InvalidInstrumentStatusError: If the status is not one of `allowed`.
        """

        status = typing.cast(InstrumentStatus, self.status.current)
        if status not in allowed:
            expected = " or ".join(item.name for item in allowed)
            msg = f"The instrument status is {status.name}, but the command requires {expected}. {HINTS[status]}"
            raise InvalidInstrumentStatusError(msg)

        self._operations += 1
        if during is not None:
            self._set_state(during)

        try:
            yield
        except BaseException:
            self._set_state(InstrumentStatus.ERROR)
            raise
        finally:
            self._operations -= 1

        if after is not None:
            self._set_state(after)

    def _set_state(self, state: InstrumentStatus) -> None:
        self._state = state
        self._publish()

    def _publish(self) -> None:
        """Update `status` from the tracked state and the connection."""

        status = self._state if self._connected else InstrumentStatus.NOT_CONNECTED
        current = typing.cast(InstrumentStatus, self.status.current)
        if status != current:
            logger.info("Update the status from %s to %s.", current.name, status.name)
            self.status.update(status)
