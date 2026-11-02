class SerialCommunicationError(Exception):
    """Failed to perform serial communication with the instrument."""


class UnexpectedReturnValue(Exception):
    """Received unexpected return value from the instrument."""


class InvalidInstrumentStatusError(Exception):
    """The instrument is not in a valid status to accept the specified command."""


class InstrumentErrorDetected(Exception):
    """Received any error codes from the instrument."""


COMMAND_ERRORS: list[type[Exception]] = [
    SerialCommunicationError,
    UnexpectedReturnValue,
    InvalidInstrumentStatusError,
    InstrumentErrorDetected,
]
"""The errors every instrument command can raise."""
