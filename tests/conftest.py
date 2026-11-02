import collections.abc
import typing

import pytest

from unitelabs.xpeel.io import XPeelProtocol

pytest_plugins = ["unitelabs.bus.testing.fixtures"]

Replies = dict[bytes, bytes | list[bytes]]

OpenXPeel = typing.Callable[..., typing.Awaitable[XPeelProtocol]]


@pytest.fixture
async def open_xpeel(mk_stubbed_protocol) -> collections.abc.AsyncGenerator[OpenXPeel, None]:
    """Open an `XPeelProtocol` to a mocked instrument that sends the given replies to the given requests."""

    protocols: list[XPeelProtocol] = []

    async def _open_xpeel(replies: Replies | None = None, **kwargs) -> XPeelProtocol:
        protocol = mk_stubbed_protocol(XPeelProtocol, replies, port="/dev/ttyXPEEL", **kwargs)
        await protocol.open()
        protocols.append(protocol)

        return protocol

    yield _open_xpeel

    for protocol in protocols:
        protocol.close()
