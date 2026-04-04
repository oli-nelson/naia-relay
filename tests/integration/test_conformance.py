from __future__ import annotations

import pytest
from pydantic import ValidationError

from .helpers import (
    build_client_runtime,
    build_direct_runtime,
    build_host_runtime,
    stdio_round_trip,
)


@pytest.mark.asyncio
async def test_malformed_mcp_message_fails_cleanly() -> None:
    runtime = build_direct_runtime("stdio", "stdio")
    await runtime.start()

    with pytest.raises(ValidationError):
        await stdio_round_trip(runtime.handle_mcp_message, {"jsonrpc": "2.0", "id": 1})

    await runtime.stop()


@pytest.mark.asyncio
async def test_malformed_tep_message_fails_cleanly() -> None:
    runtime = build_direct_runtime("stdio", "stdio")
    await runtime.start()

    with pytest.raises(ValidationError):
        await stdio_round_trip(
            runtime.handle_tep_message,
            {"protocol": "tep", "version": "1.0", "message_type": "register_tools", "payload": {}},
        )

    await runtime.stop()


@pytest.mark.asyncio
async def test_malformed_rlp_message_fails_cleanly() -> None:
    host = build_host_runtime()
    await host.start()

    with pytest.raises(ValidationError):
        await stdio_round_trip(
            host.handle_rlp_message,
            {"protocol": "rlp", "version": "1.0", "message_type": "bind_session", "payload": {}},
        )

    await host.stop()


@pytest.mark.asyncio
async def test_unsupported_mcp_features_fail_explicitly_in_bridged_mode() -> None:
    host = build_host_runtime()
    client = build_client_runtime("stdio")
    await host.start()
    await client.start()

    async def requester(message: dict[str, object]) -> dict[str, object]:
        response = await stdio_round_trip(host.handle_rlp_message, message)
        assert response is not None
        return response

    await client.bind_via_requester(
        requester,
        host_session_id=host.session_id,
        host_relay_id=host.relay_id,
    )

    sampling = await stdio_round_trip(
        client.handle_mcp_message,
        {"jsonrpc": "2.0", "id": 1, "method": "sampling/createMessage"},
    )
    roots = await stdio_round_trip(
        client.handle_mcp_message,
        {"jsonrpc": "2.0", "id": 2, "method": "roots/list"},
    )
    completion = await stdio_round_trip(
        client.handle_mcp_message,
        {"jsonrpc": "2.0", "id": 3, "method": "completion/complete"},
    )

    await client.stop()
    await host.stop()

    assert sampling["error"]["code"] == -32601
    assert roots["error"]["code"] == -32601
    assert completion["error"]["code"] == -32601
