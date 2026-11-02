import dataclasses
import logging
import re

import typing_extensions as typing
from unitelabs.bus import Command, SerialCommand

from .error_codes import ErrorCode
from .errors import InstrumentErrorDetected, UnexpectedReturnValue

logger = logging.getLogger(__name__)

TIMEOUT = 90.0
"""Seconds to wait for the `*ready` line that completes a command; longer than the slowest peel."""

ACK = re.compile(r"\*ack")
"""The acknowledgement the instrument sends first in reply to every command."""

HOMING = re.compile(r"\*homing")
"""Sent once the elevator and conveyor start to move to their home positions."""

POWERON = re.compile(r"\*poweron")
"""Sent once the instrument has restarted."""

TAPE = re.compile(r"\*tape:([0-9]{2}),([0-9]{2})")
"""The tape left on the supply spool and the space left on the take-up spool, in tens of seals."""

READY = re.compile(r"\*ready:([0-9]{2}),([0-9]{2}),([0-9]{2})")
"""The line that completes every command, with the three latest error codes, latest first."""

_COMPLETION = re.compile(r"\*ready:[^\n]*\n")
_LINE_BREAKS = re.compile(r"[\r\n]+")


@dataclasses.dataclass(frozen=True)
class Reply:
    """
    The lines the instrument sent in reply to a command.

    Attributes:
      lines: The lines before the `*ready` line, e.g. `("*ack", "*homing")`.
      error_codes: The error codes of the `*ready` line, latest first.
    """

    lines: tuple[str, ...]
    error_codes: tuple[int, ...]

    @classmethod
    def parse(cls, text: str) -> "Reply":
        """
        Split a reply into its lines and the error codes of its `*ready` line.

        Lines may end in CR, LF or both: in reply to `*restart`, the instrument sends `*ack` and
        `*poweron` without an LF in between.

        Args:
          text: The reply, up to and including the `*ready` line.

        Returns:
          The parsed reply.

        Raises:
          UnexpectedReturnValue: If the `*ready` line is missing or malformed.
        """

        completion = _COMPLETION.search(text)
        ready = READY.fullmatch(completion.group().strip()) if completion else None
        if completion is None or ready is None:
            msg = f"The format of the completion response {text!r} is invalid."
            raise UnexpectedReturnValue(msg)

        lines = tuple(line.strip() for line in _LINE_BREAKS.split(text[: completion.start()]) if line.strip())

        return cls(lines=lines, error_codes=tuple(int(code) for code in ready.groups()))

    def match(self, *patterns: re.Pattern[str]) -> tuple[re.Match[str], ...]:
        """
        Match the lines before the `*ready` line against the expected ones.

        Args:
          *patterns: The expected lines, in order.

        Returns:
          The match of each line.

        Raises:
          UnexpectedReturnValue: If the instrument sent other lines than expected.
        """

        if len(self.lines) == len(patterns):
            matches = tuple(pattern.fullmatch(line) for pattern, line in zip(patterns, self.lines, strict=True))
            if all(matches):
                return typing.cast(tuple[re.Match[str], ...], matches)

        expected = [pattern.pattern.replace("\\", "") for pattern in patterns]
        msg = (
            "The received message does not match the expected value. "
            f"Expected the lines {expected}, but received {list(self.lines)}."
        )
        raise UnexpectedReturnValue(msg)

    def check_error_codes(self, *, treat_warnings_as_errors: bool = False) -> str:
        """
        Raise the latest error the `*ready` line reports, or else return its latest warning.

        Args:
          treat_warnings_as_errors: Whether to raise warnings like errors.

        Returns:
          The message of the latest warning, or an empty string if there is none.

        Raises:
          InstrumentErrorDetected: If the instrument reports an error, or a warning while
            `treat_warnings_as_errors` is set.
          UnexpectedReturnValue: If the instrument reports an unknown error code.
        """

        error: InstrumentErrorDetected | None = None
        warning = ""

        # oldest first, so that the latest code wins
        for value in reversed(self.error_codes):
            try:
                code = ErrorCode(value)
            except ValueError:
                msg = f"Unexpected error code {value:02d} returned from the instrument."
                raise UnexpectedReturnValue(msg) from None

            if code == ErrorCode.NO_ERROR:
                continue

            if code.is_warning and not treat_warnings_as_errors:
                logger.warning("Instrument warning %02d: %s", code, code.message)
                warning = code.message
            else:
                logger.error("Instrument error %02d: %s", code, code.message)
                error = InstrumentErrorDetected(f"Instrument error {code:02d}: {code.message}")

        if error is not None:
            raise error

        return warning


class XPeelCommand(SerialCommand):
    """
    A command for the instrument, whose reply ends with the `*ready` line.

    The instrument acknowledges every command with `*ack`, may report its progress, e.g. with
    `*homing`, and completes the command with `*ready:EE,EE,EE`. The reply is thus only complete
    once the `*ready` line has arrived.

    Args:
      message: The command without line break, e.g. `*reset`.
    """

    def __new__(cls, *args, **kwargs) -> "Command[str, str, Reply]":
        """Create the command, which parses its reply into a `Reply`."""

        return super().__new__(cls, *args, **kwargs).add_parser(Reply.parse)

    def __init__(self, message: str) -> None:
        super().__init__(message, timeout=TIMEOUT)

    @typing.override
    def _deserialize(self, response: bytes) -> str:
        return response.decode("ascii", errors="replace")

    @typing.override
    def _validate_response(self, data: bytes) -> bool:
        return _COMPLETION.search(data.decode("ascii", errors="replace")) is not None
