import json
from pathlib import Path

import httpx
import pytest
import respx

from url2obsidian.raindrop_client import RaindropClient, RaindropError

FIXTURES = Path(__file__).parent / "fixtures"
RAINDROP_BASE = "https://api.raindrop.io/rest/v1"


def _collections_response(name_to_id: dict[str, int]) -> dict:
    return {
        "result": True,
        "items": [{"_id": cid, "title": name} for name, cid in name_to_id.items()],
    }


@respx.mock
def test_list_unclipped_returns_items_from_inbox_collection():
    respx.get(f"{RAINDROP_BASE}/collections").mock(
        return_value=httpx.Response(
            200,
            json=_collections_response(
                {"Unclipped": 7001, "Clipped": 7002, "Failed": 7003}
            ),
        )
    )
    items_payload = json.loads((FIXTURES / "raindrop-list.json").read_text())
    respx.get(f"{RAINDROP_BASE}/raindrops/7001").mock(
        return_value=httpx.Response(200, json=items_payload)
    )

    client = RaindropClient(
        token="t",
        inbox_collection="Unclipped",
        clipped_collection="Clipped",
        failed_collection="Failed",
    )
    items = list(client.list_unclipped())
    assert len(items) >= 2
    assert items[0].url.startswith("http")
    assert items[0].id > 0


@respx.mock
def test_mark_clipped_moves_item_to_clipped_collection():
    respx.get(f"{RAINDROP_BASE}/collections").mock(
        return_value=httpx.Response(
            200,
            json=_collections_response(
                {"Unclipped": 7001, "Clipped": 7002, "Failed": 7003}
            ),
        )
    )
    route = respx.put(f"{RAINDROP_BASE}/raindrop/123").mock(
        return_value=httpx.Response(200, json={"result": True})
    )
    client = RaindropClient(
        token="t",
        inbox_collection="Unclipped",
        clipped_collection="Clipped",
        failed_collection="Failed",
    )
    client.mark_clipped(item_id=123, tag="clipped-2026-05-12")
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body["collection"]["$id"] == 7002
    assert "clipped-2026-05-12" in body["tags"]


@respx.mock
def test_unauthorized_raises():
    respx.get(f"{RAINDROP_BASE}/collections").mock(
        return_value=httpx.Response(
            401, json={"result": False, "errorMessage": "unauthorized"}
        )
    )
    with pytest.raises(RaindropError, match="unauth"):
        RaindropClient(
            token="bad",
            inbox_collection="Unclipped",
            clipped_collection="Clipped",
            failed_collection="Failed",
        )
