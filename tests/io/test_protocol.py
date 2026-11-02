import asyncio
import sys

import pytest

from unitelabs.xpeel.io import (
    InstrumentErrorDetected,
    InstrumentStatus,
    InvalidInstrumentStatusError,
    SerialCommunicationError,
    TapeLeft,
    UnexpectedReturnValue,
    XPeelProtocol,
)
from unitelabs.xpeel.io.simulation import STUBS

ACK = b"*ack\r\n"
HOMING = b"*homing\r\n"
POWERON = b"*poweron\r\n"
READY = b"*ready:00,00,00\r\n"

XPEEL = b"*xpeel:41\r\n"


def statuses(subscription) -> list[InstrumentStatus]:
    values = []
    while not subscription.empty():
        values.append(subscription.get_nowait())
    return values


class TestOpen:
    async def test_not_connected_before_open(self):
        xpeel = XPeelProtocol(port="/dev/ttyXPEEL")

        assert xpeel.status.current == InstrumentStatus.NOT_CONNECTED

    async def test_idle_after_open(self, open_xpeel):
        xpeel = await open_xpeel()

        assert xpeel.status.current == InstrumentStatus.IDLE

    async def test_not_connected_after_connection_lost(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [ACK, READY]})

        xpeel.transport.abort()
        await asyncio.sleep(0)

        assert xpeel.status.current == InstrumentStatus.NOT_CONNECTED
        with pytest.raises(InvalidInstrumentStatusError, match="NOT_CONNECTED"):
            await xpeel.xpeel(4, 1)

    async def test_raises_if_serial_port_does_not_open(self, monkeypatch):
        monkeypatch.setattr("unitelabs.xpeel.io.protocol.OPEN_TIMEOUT", 0.1)
        xpeel = XPeelProtocol(port="/dev/does-not-exist")

        try:
            with pytest.raises(SerialCommunicationError, match="/dev/does-not-exist"):
                await xpeel.open_instrument()
        finally:
            xpeel.close()

        assert xpeel.status.current == InstrumentStatus.NOT_CONNECTED


class TestXPeel:
    async def test_sends_parameters(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [ACK, READY]})

        assert await xpeel.xpeel(4, 1) == ""

        xpeel.transport.mock.assert_called_once_with(XPEEL)

    async def test_is_running_until_completed(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [ACK, READY]})
        subscription = xpeel.status.subscribe()

        await xpeel.xpeel(4, 1)

        assert statuses(subscription) == [InstrumentStatus.RUNNING, InstrumentStatus.IDLE]

    async def test_returns_warning(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [ACK, b"*ready:20,00,00\r\n"]})

        assert await xpeel.xpeel(4, 1) == "Less than 30 seals left on the supply roll."
        assert xpeel.status.current == InstrumentStatus.IDLE

    async def test_returns_latest_warning(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [ACK, b"*ready:21,20,00\r\n"]})

        assert await xpeel.xpeel(4, 1) == "Room for less than 30 seals on take up spool."

    async def test_raises_warning_if_treated_as_error(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [ACK, b"*ready:20,00,00\r\n"]}, treat_warnings_as_errors=True)

        with pytest.raises(InstrumentErrorDetected, match="Less than 30 seals"):
            await xpeel.xpeel(4, 1)

        assert xpeel.status.current == InstrumentStatus.ERROR

    async def test_raises_error(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [ACK, b"*ready:04,00,00\r\n"]})

        with pytest.raises(InstrumentErrorDetected, match=r"^Instrument error 04: Seal not removed\.$"):
            await xpeel.xpeel(4, 1)

        assert xpeel.status.current == InstrumentStatus.ERROR

    async def test_raises_latest_error(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [ACK, b"*ready:06,04,20\r\n"]})

        with pytest.raises(InstrumentErrorDetected, match="No plate found"):
            await xpeel.xpeel(4, 1)

    async def test_raises_error_before_checking_the_reply(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: b"*ready:05,00,00\r\n"})

        with pytest.raises(InstrumentErrorDetected, match="Illegal command"):
            await xpeel.xpeel(4, 1)

    async def test_raises_on_unknown_error_code(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [ACK, b"*ready:99,00,00\r\n"]})

        with pytest.raises(UnexpectedReturnValue, match="Unexpected error code 99"):
            await xpeel.xpeel(4, 1)

        assert xpeel.status.current == InstrumentStatus.ERROR

    async def test_raises_on_malformed_ready(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [ACK, b"*ready:0A,00,00\r\n"]})

        with pytest.raises(UnexpectedReturnValue, match="completion response"):
            await xpeel.xpeel(4, 1)

    async def test_raises_on_unexpected_line(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [b"*nak\r\n", READY]})

        with pytest.raises(UnexpectedReturnValue, match=r"Expected the lines \['\*ack'\], but received \['\*nak'\]"):
            await xpeel.xpeel(4, 1)

        assert xpeel.status.current == InstrumentStatus.ERROR

    async def test_accepts_reply_in_chunks(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [b"*ac", b"k\r\n*rea", b"dy:00,00,", b"00\r\n"]})

        assert await xpeel.xpeel(4, 1) == ""

    async def test_raises_without_reply(self, open_xpeel, monkeypatch):
        monkeypatch.setattr("unitelabs.xpeel.io.commands.TIMEOUT", 0.05)
        xpeel = await open_xpeel({})

        with pytest.raises(SerialCommunicationError, match=r"No complete response to '\*xpeel:41'"):
            await xpeel.xpeel(4, 1)

        assert xpeel.status.current == InstrumentStatus.ERROR

    async def test_requires_idle(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [ACK, b"*ready:04,00,00\r\n"]})
        with pytest.raises(InstrumentErrorDetected):
            await xpeel.xpeel(4, 1)

        with pytest.raises(InvalidInstrumentStatusError, match="status is ERROR, but the command requires IDLE"):
            await xpeel.xpeel(4, 1)

        assert xpeel.status.current == InstrumentStatus.ERROR

    async def test_rejects_commands_while_running(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: ACK})
        running = asyncio.ensure_future(xpeel.xpeel(4, 1))
        await asyncio.sleep(0.01)

        assert xpeel.is_busy
        with pytest.raises(InvalidInstrumentStatusError, match="status is RUNNING"):
            await xpeel.reset()

        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running

        assert not xpeel.is_busy
        assert xpeel.status.current == InstrumentStatus.ERROR


class TestTapeLeft:
    async def test_returns_tape_left(self, open_xpeel):
        xpeel = await open_xpeel({b"*tapeleft\r\n": [ACK, b"*tape:26,04\r\n", READY]})

        assert await xpeel.tapeleft() == TapeLeft(
            supply_spool_remaining=260, take_up_spool_remaining=40, warning_message=""
        )

    async def test_keeps_status(self, open_xpeel):
        xpeel = await open_xpeel({b"*tapeleft\r\n": [ACK, b"*tape:26,04\r\n", READY]})
        subscription = xpeel.status.subscribe()

        await xpeel.tapeleft()

        assert statuses(subscription) == []

    async def test_returns_warning(self, open_xpeel):
        xpeel = await open_xpeel({b"*tapeleft\r\n": [ACK, b"*tape:02,26\r\n", b"*ready:20,00,00\r\n"]})

        tape = await xpeel.tapeleft()

        assert tape.warning_message == "Less than 30 seals left on the supply roll."

    @pytest.mark.parametrize("tape", [b"*tape:2,04\r\n", b"*tape:26\r\n", b"*tape:ab,04\r\n"])
    async def test_raises_on_malformed_tape(self, open_xpeel, tape):
        xpeel = await open_xpeel({b"*tapeleft\r\n": [ACK, tape, READY]})

        with pytest.raises(UnexpectedReturnValue):
            await xpeel.tapeleft()

        assert xpeel.status.current == InstrumentStatus.ERROR

    async def test_raises_on_missing_tape(self, open_xpeel):
        xpeel = await open_xpeel({b"*tapeleft\r\n": [ACK, READY]})

        with pytest.raises(UnexpectedReturnValue):
            await xpeel.tapeleft()


class TestReset:
    async def test_homes(self, open_xpeel):
        xpeel = await open_xpeel({b"*reset\r\n": [ACK, HOMING, READY]})
        subscription = xpeel.status.subscribe()

        assert await xpeel.reset() == ""

        assert statuses(subscription) == [InstrumentStatus.RUNNING, InstrumentStatus.IDLE]

    async def test_raises_on_missing_homing(self, open_xpeel):
        xpeel = await open_xpeel({b"*reset\r\n": [ACK, READY]})

        with pytest.raises(UnexpectedReturnValue, match="homing"):
            await xpeel.reset()


class TestRestart:
    async def test_restarts(self, open_xpeel):
        xpeel = await open_xpeel({b"*restart\r\n": [ACK, POWERON, HOMING, READY]})
        subscription = xpeel.status.subscribe()

        assert await xpeel.restart() == ""

        assert statuses(subscription) == []

    async def test_accepts_poweron_without_line_feed(self, open_xpeel):
        xpeel = await open_xpeel({b"*restart\r\n": [b"*ack\r*poweron\r\n", HOMING, READY]})

        assert await xpeel.restart() == ""

    async def test_clears_error(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [ACK, b"*ready:09,00,00\r\n"], b"*restart\r\n": [ACK, POWERON, HOMING, READY]})
        with pytest.raises(InstrumentErrorDetected, match="Stop button pressed"):
            await xpeel.xpeel(4, 1)

        await xpeel.restart()

        assert xpeel.status.current == InstrumentStatus.IDLE

    async def test_keeps_error_if_it_fails(self, open_xpeel):
        xpeel = await open_xpeel({XPEEL: [ACK, b"*ready:51,00,00\r\n"], b"*restart\r\n": b"*ready:51,00,00\r\n"})
        with pytest.raises(InstrumentErrorDetected):
            await xpeel.xpeel(4, 1)

        with pytest.raises(InstrumentErrorDetected, match="Emergency Stop"):
            await xpeel.restart()

        assert xpeel.status.current == InstrumentStatus.ERROR


class TestSimulator:
    async def test_completes_every_command(self):
        xpeel = XPeelProtocol(port="/dev/ttyXPEEL")
        await xpeel.open_simulator()

        try:
            assert await xpeel.xpeel(9, 4) == ""
            assert await xpeel.tapeleft() == TapeLeft(260, 240, "")
            assert await xpeel.reset() == ""
            assert await xpeel.restart() == ""
        finally:
            xpeel.close()


@pytest.mark.skipif(sys.platform == "win32", reason="The mock serial device requires a pty.")
class TestSerialPort:
    async def test_completes_commands(self, serial_device):
        serial_device.stubs = STUBS
        xpeel = XPeelProtocol(port=serial_device.port)
        await xpeel.open_instrument()

        try:
            assert xpeel.status.current == InstrumentStatus.IDLE
            assert await xpeel.xpeel(3, 2) == ""
            assert await xpeel.tapeleft() == TapeLeft(260, 240, "")
            assert await xpeel.restart() == ""
        finally:
            xpeel.close()
