from __future__ import annotations

import pytest

from naia_relay.errors import TransportError
from naia_relay.protocols.mcp import MCPHandler
from naia_relay.protocols.tep import TEPHandler
from naia_relay.registry import RegistryStore
from naia_relay.transports import HttpTransportAdapter, HttpTransportConfig


@pytest.mark.asyncio
async def test_http_transport_round_trip_with_injected_requester() -> None:
    captured: list[dict[str, object]] = []

    async def requester(message: dict[str, object]) -> dict[str, object]:
        captured.append(message)
        return {"status": "ok"}

    adapter = HttpTransportAdapter(
        HttpTransportConfig(base_url="http://example.invalid"), requester=requester
    )
    await adapter.start()
    response = await adapter.round_trip({"hello": "http"})
    await adapter.stop()

    assert captured == [{"hello": "http"}]
    assert response == {"status": "ok"}


@pytest.mark.asyncio
async def test_http_transport_rejects_non_object_response() -> None:
    async def requester(message: dict[str, object]) -> dict[str, object]:
        return []  # type: ignore[return-value]

    adapter = HttpTransportAdapter(
        HttpTransportConfig(base_url="http://example.invalid"), requester=requester
    )
    await adapter.start()

    with pytest.raises(TransportError):
        await adapter.round_trip({"hello": "http"})


@pytest.mark.asyncio
async def test_http_transport_receive_is_not_supported() -> None:
    async def requester(message: dict[str, object]) -> dict[str, object]:
        return {"status": "ok"}

    adapter = HttpTransportAdapter(
        HttpTransportConfig(base_url="http://example.invalid"), requester=requester
    )
    await adapter.start()

    with pytest.raises(TransportError):
        await adapter.receive()


@pytest.mark.asyncio
async def test_http_transport_surfaces_timeout_or_request_failures() -> None:
    async def requester(message: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("timeout")

    adapter = HttpTransportAdapter(
        HttpTransportConfig(base_url="http://example.invalid"), requester=requester
    )
    await adapter.start()

    with pytest.raises(TransportError):
        await adapter.round_trip({"hello": "http"})


@pytest.mark.asyncio
async def test_mcp_over_http_non_streaming_round_trip() -> None:
    registry = RegistryStore(mode="authoritative")
    handler = MCPHandler(registry=registry)

    async def requester(message: dict[str, object]) -> dict[str, object]:
        response = await handler.handle_message(message)
        assert response is not None
        return response

    adapter = HttpTransportAdapter(
        HttpTransportConfig(base_url="http://example.invalid"), requester=requester
    )
    await adapter.start()
    response = await adapter.round_trip(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        }
    )

    assert response["result"]["protocolVersion"] == "2025-03-26"


@pytest.mark.asyncio
async def test_tep_over_http_non_streaming_round_trip() -> None:
    handler = TEPHandler(registry=RegistryStore(mode="authoritative"))

    async def requester(message: dict[str, object]) -> dict[str, object]:
        return await handler.handle_message(message)

    adapter = HttpTransportAdapter(
        HttpTransportConfig(base_url="http://example.invalid"), requester=requester
    )
    await adapter.start()
    response = await adapter.round_trip(
        {
            "protocol": "tep",
            "version": "1.0",
            "message_type": "register_executor",
            "message_id": "msg_1",
            "session_id": "sess_1",
            "payload": {"executor_id": "nvim", "display_name": "Neovim"},
        }
    )

    assert response["payload"]["status"] == "ok"
