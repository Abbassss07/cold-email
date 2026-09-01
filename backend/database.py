"""Small async-friendly data layer backed by Supabase Postgres.

The application originally used Motor/MongoDB directly.  This adapter keeps the
existing collection-oriented call sites readable while storing each document in
a real Postgres table.  Queries are evaluated in Python because the admin app is
bounded to a few thousand rows per view; writes still target rows by primary key.
"""
from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from typing import Any, AsyncIterator, Iterable

from supabase import Client, create_client


_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
            )
        _client = create_client(url, key)
    return _client


async def _execute(query):
    return await asyncio.to_thread(query.execute)


async def _fetch_all(table: str, page_size: int = 1000) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        response = await _execute(
            get_supabase().table(table).select("*").range(start, start + page_size - 1)
        )
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        start += page_size


def _nested_get(row: dict, dotted: str) -> Any:
    value: Any = row
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _matches_value(actual: Any, expected: Any) -> bool:
    if not isinstance(expected, dict):
        return actual == expected
    if "$exists" in expected:
        return (actual is not None) is bool(expected["$exists"])
    if "$regex" in expected:
        flags = re.IGNORECASE if "i" in expected.get("$options", "") else 0
        return re.search(str(expected["$regex"]), str(actual or ""), flags) is not None
    if "$in" in expected:
        return actual in expected["$in"]
    if "$ne" in expected:
        return actual != expected["$ne"]
    if "$gt" in expected:
        return actual is not None and actual > expected["$gt"]
    if "$gte" in expected:
        return actual is not None and actual >= expected["$gte"]
    return actual == expected


def _matches(row: dict, query: dict | None) -> bool:
    query = query or {}
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(row, branch) for branch in expected):
                return False
            continue
        if not _matches_value(_nested_get(row, key), expected):
            return False
    return True


def _apply_set(row: dict, updates: dict) -> dict:
    result = dict(row)
    for dotted, value in updates.items():
        parts = dotted.split(".")
        target = result
        for part in parts[:-1]:
            current = target.get(part)
            if not isinstance(current, dict):
                current = {}
                target[part] = current
            target = current
        target[parts[-1]] = value
    return result


@dataclass
class WriteResult:
    matched_count: int = 0
    deleted_count: int = 0


class QueryCursor:
    def __init__(self, collection: "Collection", query: dict | None):
        self.collection = collection
        self.query = query or {}
        self.sort_key: str | None = None
        self.sort_direction = 1
        self.max_rows: int | None = None

    def sort(self, key: str, direction: int):
        self.sort_key = key
        self.sort_direction = direction
        return self

    def limit(self, count: int):
        self.max_rows = count
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        rows = [r for r in await self.collection._rows() if _matches(r, self.query)]
        if self.sort_key:
            rows.sort(
                key=lambda r: (_nested_get(r, self.sort_key) is None,
                               _nested_get(r, self.sort_key)),
                reverse=self.sort_direction < 0,
            )
        cap = self.max_rows if self.max_rows is not None else length
        return rows[:cap] if cap is not None else rows


class AggregateCursor:
    def __init__(self, collection: "Collection", pipeline: list[dict]):
        self.collection = collection
        self.pipeline = pipeline
        self._rows: list[dict] | None = None
        self._index = 0

    async def _compute(self) -> list[dict]:
        rows = await self.collection._rows()
        for stage in self.pipeline:
            if "$match" in stage:
                rows = [r for r in rows if _matches(r, stage["$match"])]
            elif "$group" in stage:
                spec = stage["$group"]
                group_expr = spec.get("_id")
                if group_expr is None:
                    result: dict = {"_id": None}
                    for name, operation in spec.items():
                        if name == "_id":
                            continue
                        if "$avg" in operation:
                            field = operation["$avg"].lstrip("$")
                            values = [_nested_get(r, field) for r in rows]
                            values = [v for v in values if isinstance(v, (int, float))]
                            result[name] = sum(values) / len(values) if values else None
                    rows = [result]
                else:
                    field = str(group_expr).lstrip("$")
                    counts: dict[Any, int] = {}
                    for row in rows:
                        value = _nested_get(row, field)
                        counts[value] = counts.get(value, 0) + 1
                    rows = [{"_id": key, "n": count} for key, count in counts.items()]
        return rows

    def __aiter__(self) -> AsyncIterator[dict]:
        return self

    async def __anext__(self) -> dict:
        if self._rows is None:
            self._rows = await self._compute()
        if self._index >= len(self._rows):
            raise StopAsyncIteration
        row = self._rows[self._index]
        self._index += 1
        return row


class Collection:
    def __init__(self, table: str, primary_key: str = "id"):
        self.table = table
        self.primary_key = primary_key

    async def _rows(self) -> list[dict]:
        return await _fetch_all(self.table)

    async def insert_one(self, document: dict):
        await _execute(get_supabase().table(self.table).insert(document))
        return WriteResult(matched_count=1)

    async def insert_many(self, documents: Iterable[dict]):
        docs = list(documents)
        if docs:
            await _execute(get_supabase().table(self.table).insert(docs))
        return WriteResult(matched_count=len(docs))

    async def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        del projection
        for row in await self._rows():
            if _matches(row, query):
                return row
        return None

    def find(self, query: dict | None = None, projection: dict | None = None) -> QueryCursor:
        del projection
        return QueryCursor(self, query)

    async def count_documents(self, query: dict | None = None) -> int:
        return sum(1 for row in await self._rows() if _matches(row, query))

    async def update_one(self, query: dict, update: dict) -> WriteResult:
        rows = [row for row in await self._rows() if _matches(row, query)]
        if not rows:
            return WriteResult()
        row = rows[0]
        updated = _apply_set(row, update.get("$set", {}))
        pk = row[self.primary_key]
        payload = {k: v for k, v in updated.items() if k != self.primary_key}
        await _execute(
            get_supabase().table(self.table).update(payload).eq(self.primary_key, pk)
        )
        return WriteResult(matched_count=1)

    async def update_many(self, query: dict, update: dict) -> WriteResult:
        rows = [row for row in await self._rows() if _matches(row, query)]
        for row in rows:
            updated = _apply_set(row, update.get("$set", {}))
            pk = row[self.primary_key]
            payload = {k: v for k, v in updated.items() if k != self.primary_key}
            await _execute(
                get_supabase().table(self.table).update(payload).eq(self.primary_key, pk)
            )
        return WriteResult(matched_count=len(rows))

    async def delete_one(self, query: dict) -> WriteResult:
        row = await self.find_one(query)
        if not row:
            return WriteResult()
        await _execute(
            get_supabase().table(self.table).delete().eq(
                self.primary_key, row[self.primary_key]
            )
        )
        return WriteResult(deleted_count=1)

    def aggregate(self, pipeline: list[dict]) -> AggregateCursor:
        return AggregateCursor(self, pipeline)


async def get_setting(key: str, default: str = "") -> str:
    response = await _execute(
        get_supabase().table("app_settings").select("value").eq("key", key).limit(1)
    )
    if response.data:
        return str(response.data[0].get("value") or "")
    return default


async def get_settings_map() -> dict[str, str]:
    rows = await _fetch_all("app_settings")
    return {str(row["key"]): str(row.get("value") or "") for row in rows}


async def set_setting(key: str, value: str) -> None:
    await _execute(
        get_supabase().table("app_settings").upsert(
            {"key": key, "value": value}, on_conflict="key"
        )
    )


async def rpc(name: str, params: dict | None = None) -> Any:
    response = await _execute(get_supabase().rpc(name, params or {}))
    return response.data


async def storage_upload(path: str, data: bytes, content_type: str) -> None:
    bucket = get_supabase().storage.from_("app-files")
    await asyncio.to_thread(bucket.upload, path=path, file=data, file_options={
        "content-type": content_type, "upsert": "true"
    })


async def storage_download(path: str) -> bytes:
    bucket = get_supabase().storage.from_("app-files")
    return await asyncio.to_thread(bucket.download, path)


async def storage_remove(path: str) -> None:
    bucket = get_supabase().storage.from_("app-files")
    await asyncio.to_thread(bucket.remove, [path])


async def storage_info(path: str) -> dict | None:
    folder, _, filename = path.rpartition("/")
    bucket = get_supabase().storage.from_("app-files")
    items = await asyncio.to_thread(bucket.list, folder or None)
    for item in items or []:
        name = item.get("name") if isinstance(item, dict) else getattr(item, "name", "")
        if name == filename:
            return item if isinstance(item, dict) else item.__dict__
    return None
