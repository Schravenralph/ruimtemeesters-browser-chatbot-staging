import asyncio
from unittest.mock import AsyncMock

from open_webui.utils.mcp.client import MCPClient


class TestMCPClientDisconnect:
    """Null-safe disconnect — regression guard for bugbot finding #3.

    Pre-fix: disconnect() called self.exit_stack.aclose() unconditionally,
    raising AttributeError when connect() bailed before line 60 assigned
    exit_stack. connect()'s except handler invokes disconnect() via
    asyncio.shield, so that AttributeError replaced whatever upstream error
    triggered the reconnect in the first place.
    """

    def test_disconnect_before_connect_does_not_raise(self):
        async def run():
            client = MCPClient()
            # exit_stack is None by construction
            assert client.exit_stack is None
            await client.disconnect()
            # idempotent: a second call is also safe
            await client.disconnect()

        asyncio.run(run())

    def test_disconnect_calls_aclose_when_present(self):
        async def run():
            client = MCPClient()
            mock_stack = AsyncMock()
            client.exit_stack = mock_stack
            client.session = object()
            await client.disconnect()
            mock_stack.aclose.assert_awaited_once()
            # state reset so a second disconnect is a no-op
            assert client.exit_stack is None
            assert client.session is None
            await client.disconnect()
            mock_stack.aclose.assert_awaited_once()  # still once

        asyncio.run(run())
