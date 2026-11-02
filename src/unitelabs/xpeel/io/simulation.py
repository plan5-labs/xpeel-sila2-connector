import collections.abc
import typing

from unitelabs.bus.testing import MockTransport, create_mock_connection, stub_maker

P = typing.TypeVar("P")

ACK = b"*ack\r\n"
HOMING = b"*homing\r\n"
POWERON = b"*poweron\r\n"
READY = b"*ready:00,00,00\r\n"

REPLIES: dict[bytes, list[bytes]] = {
    **{
        f"*xpeel:{begin_peel_location}{adhesion_time}\r\n".encode(): [ACK, READY]
        for begin_peel_location in range(1, 10)
        for adhesion_time in range(1, 5)
    },
    b"*tapeleft\r\n": [ACK, b"*tape:26,24\r\n", READY],
    b"*reset\r\n": [ACK, HOMING, READY],
    b"*restart\r\n": [ACK, POWERON, HOMING, READY],
}
"""How the simulated instrument replies to each command it understands."""

STUBS = [stub_maker(request, reply) for request, reply in REPLIES.items()]


async def create_simulated_connection(
    protocol_factory: collections.abc.Callable[[], P], /, **kwargs
) -> tuple[MockTransport, P]:
    """
    Connect to a simulated instrument, which completes every command instantly and without error.

    Args:
      protocol_factory: A callable which returns the `Protocol` to connect.
      **kwargs: Ignored, the simulated instrument needs no connection settings.

    Returns:
      The transport to the simulated instrument and the connected protocol.
    """

    return await create_mock_connection(protocol_factory, stubs=STUBS)
