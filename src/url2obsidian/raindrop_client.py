from collections.abc import Iterable
from datetime import datetime

import httpx

from url2obsidian.models import Item

_BASE = "https://api.raindrop.io/rest/v1"
_PAGE_SIZE = 50


class RaindropError(RuntimeError):
    pass


class RaindropClient:
    def __init__(
        self,
        token: str,
        inbox_collection: str,
        clipped_collection: str,
        failed_collection: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._http = http_client or httpx.Client(
            base_url=_BASE,
            timeout=20.0,
            headers={"Authorization": f"Bearer {token}"},
        )
        self._inbox_name = inbox_collection
        self._clipped_name = clipped_collection
        self._failed_name = failed_collection
        names = self._resolve_collections()
        self._inbox_id = names[inbox_collection]
        self._clipped_id = names[clipped_collection]
        self._failed_id = names[failed_collection]

    def _resolve_collections(self) -> dict[str, int]:
        try:
            resp = self._http.get("/collections")
        except httpx.HTTPError as e:
            raise RaindropError(f"network error contacting raindrop: {e}") from e
        if resp.status_code in (401, 403):
            raise RaindropError("unauthorized: check your Raindrop token")
        resp.raise_for_status()
        data = resp.json()
        out: dict[str, int] = {}
        for item in data.get("items", []):
            out[item["title"]] = int(item["_id"])
        missing = [
            n for n in (self._inbox_name, self._clipped_name, self._failed_name) if n not in out
        ]
        if missing:
            raise RaindropError(f"collections not found: {missing}")
        return out

    def list_unclipped(self) -> Iterable[Item]:
        page = 0
        while True:
            resp = self._http.get(
                f"/raindrops/{self._inbox_id}",
                params={"perpage": _PAGE_SIZE, "page": page},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return
            for raw in items:
                yield Item(
                    id=int(raw["_id"]),
                    url=raw["link"],
                    title=raw.get("title", ""),
                    excerpt=raw.get("excerpt", ""),
                    tags=tuple(raw.get("tags", [])),
                    created=_parse_iso(raw.get("created")),
                )
            if len(items) < _PAGE_SIZE:
                return
            page += 1

    def mark_clipped(self, item_id: int, tag: str) -> None:
        self._move(item_id, target_collection_id=self._clipped_id, extra_tag=tag)

    def mark_failed(self, item_id: int, reason: str) -> None:
        self._move(
            item_id,
            target_collection_id=self._failed_id,
            extra_tag=f"clip-error:{reason}",
        )

    def _move(self, item_id: int, target_collection_id: int, extra_tag: str) -> None:
        resp = self._http.put(
            f"/raindrop/{item_id}",
            json={
                "collection": {"$id": target_collection_id},
                "tags": [extra_tag],
            },
        )
        if resp.status_code in (401, 403):
            raise RaindropError("unauthorized: check your Raindrop token")
        resp.raise_for_status()


def _parse_iso(raw: str | None) -> datetime:
    if not raw:
        return datetime.fromtimestamp(0)
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))
