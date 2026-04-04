from __future__ import annotations

import pytest

from naia_relay.errors import TransportError
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
