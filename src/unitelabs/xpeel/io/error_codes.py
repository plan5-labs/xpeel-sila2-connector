import enum


class ErrorCode(enum.IntEnum):
    """An error code the instrument reports in the `*ready` line that completes every command."""

    NO_ERROR = 0
    CONVEYOR_MOTOR_STALLED = 1
    ELEVATOR_MOTOR_STALLED = 2
    TAKE_UP_SPOOL_STALLED = 3
    SEAL_NOT_REMOVED = 4
    ILLEGAL_COMMAND = 5
    NO_PLATE_FOUND = 6
    OUT_OF_TAPE = 7
    PARAMETERS_NOT_SAVED = 8
    STOP_BUTTON_PRESSED = 9
    SEAL_SENSOR_UNPLUGGED = 10
    SEALS_LOW_ON_THE_ROLL = 20
    TAKE_UP_SPOOL_SPACE_LOW = 21
    EMERGENCY_STOP = 51
    CIRCUITRY_FAULT = 52

    @property
    def message(self) -> str:
        """The description of this code for the operator."""

        return MESSAGES[self]

    @property
    def is_warning(self) -> bool:
        """Whether the instrument still completed the command despite this code."""

        return self in (ErrorCode.SEALS_LOW_ON_THE_ROLL, ErrorCode.TAKE_UP_SPOOL_SPACE_LOW)


MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.NO_ERROR: "No error.",
    ErrorCode.CONVEYOR_MOTOR_STALLED: "Conveyor motor stalled.",
    ErrorCode.ELEVATOR_MOTOR_STALLED: "Elevator motor stalled.",
    ErrorCode.TAKE_UP_SPOOL_STALLED: "Take up spool stalled.",
    ErrorCode.SEAL_NOT_REMOVED: "Seal not removed.",
    ErrorCode.ILLEGAL_COMMAND: "Illegal command executed. Please contact the SiLA Server developer.",
    ErrorCode.NO_PLATE_FOUND: "No plate found.",
    ErrorCode.OUT_OF_TAPE: "Out of tape, or tape broke.",
    ErrorCode.PARAMETERS_NOT_SAVED: "Parameters not saved.",
    ErrorCode.STOP_BUTTON_PRESSED: "Stop button pressed while running.",
    ErrorCode.SEAL_SENSOR_UNPLUGGED: "Seal Sensor unplugged or broke.",
    ErrorCode.SEALS_LOW_ON_THE_ROLL: "Less than 30 seals left on the supply roll.",
    ErrorCode.TAKE_UP_SPOOL_SPACE_LOW: "Room for less than 30 seals on take up spool.",
    ErrorCode.EMERGENCY_STOP: (
        "Emergency Stop: Close the cover. If it is already closed, contact the manufacturer as there may be a "
        "hardware malfunction."
    ),
    ErrorCode.CIRCUITRY_FAULT: "Circuitry Fault Detected: Remove power.",
}
