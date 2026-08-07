"""SQLite repository built with SQLAlchemy Core and explicit upserts."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import OperationalError as SqlAlchemyOpError

from website_analyzer.models import AssetRecord, ComponentRecord, PageRecord, RequestRecord


class AnalysisRepository:
    """Thread-safe async facade over a local SQLite analysis database."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(
            f"sqlite:///{path}",
            future=True,
            connect_args={"timeout": 60.0, "check_same_thread": False},
        )
        with self._engine.begin() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA busy_timeout=60000;")
        metadata = MetaData()
        self.pages = Table("pages", metadata,
            Column("url", String, primary_key=True), Column("canonical_url", String, nullable=False),
            Column("title", Text), Column("status", Integer), Column("depth", Integer, nullable=False),
            Column("language", String), Column("meta_json", Text, nullable=False), Column("html_path", Text),
            Column("screenshot_path", Text), Column("discovered_at", String, nullable=False))
        self.assets = Table("assets", metadata,
            Column("url", String, primary_key=True), Column("local_path", Text, nullable=False),
            Column("content_type", String), Column("size", Integer, nullable=False), Column("sha256", String, nullable=False))
        self.requests = Table("requests", metadata,
            Column("id", Integer, primary_key=True, autoincrement=True), Column("url", Text, nullable=False),
            Column("method", String, nullable=False), Column("resource_type", String, nullable=False),
            Column("request_headers_json", Text, nullable=False), Column("request_body", Text), Column("status", Integer),
            Column("response_headers_json", Text, nullable=False), Column("content_type", String),
            Column("response_size", Integer), Column("timing_ms", String), Column("response_path", Text), Column("observed_at", String, nullable=False))
        self.components = Table("components", metadata,
            Column("id", Integer, primary_key=True, autoincrement=True), Column("page_url", Text, nullable=False),
            Column("kind", String, nullable=False), Column("selector", Text, nullable=False), Column("label", Text),
            Column("attributes_json", Text, nullable=False))
        self.edges = Table("edges", metadata,
            Column("source", Text, primary_key=True), Column("target", Text, primary_key=True), Column("label", Text))
        metadata.create_all(self._engine)

    async def save_page(self, record: PageRecord) -> None:
        values = record.json() | {"meta_json": json.dumps(record.meta)}
        values.pop("meta")
        await asyncio.to_thread(self._upsert, self.pages, values, ["url"])

    async def save_asset(self, record: AssetRecord) -> None:
        await asyncio.to_thread(self._upsert, self.assets, asdict(record), ["url"])

    async def save_request(self, record: RequestRecord) -> None:
        values = asdict(record)
        values["request_headers_json"] = json.dumps(values.pop("request_headers"))
        values["response_headers_json"] = json.dumps(values.pop("response_headers"))
        await asyncio.to_thread(self._insert, self.requests, values)

    async def save_components(self, records: Iterable[ComponentRecord]) -> None:
        rows = [{"page_url": r.page_url, "kind": r.kind, "selector": r.selector, "label": r.label,
                 "attributes_json": json.dumps(r.attributes)} for r in records]
        if rows:
            await asyncio.to_thread(self._insert_many, self.components, rows)

    async def save_edge(self, source: str, target: str, label: str | None = None) -> None:
        await asyncio.to_thread(self._upsert, self.edges, {"source": source, "target": target, "label": label}, ["source", "target"])

    async def all_pages(self) -> list[dict[str, object]]:
        return await asyncio.to_thread(self._fetch_all, self.pages)

    async def page_urls(self) -> set[str]:
        return {str(row["url"]) for row in await self.all_pages()}

    async def all_requests(self) -> list[dict[str, object]]:
        return await asyncio.to_thread(self._fetch_all, self.requests)

    async def all_edges(self) -> list[dict[str, object]]:
        return await asyncio.to_thread(self._fetch_all, self.edges)

    async def all_assets(self) -> list[dict[str, object]]:
        return await asyncio.to_thread(self._fetch_all, self.assets)

    async def close(self) -> None:
        """Release SQLite handles, useful for short-lived scripts and tests on Windows."""
        await asyncio.to_thread(self._engine.dispose)

    @staticmethod
    def _retry(fn: Callable[[], Any], max_attempts: int = 5) -> Any:
        for attempt in range(max_attempts):
            try:
                return fn()
            except (sqlite3.OperationalError, SqlAlchemyOpError) as err:
                if "locked" in str(err).lower() and attempt < max_attempts - 1:
                    time.sleep(0.1 * (2 ** attempt))
                else:
                    raise

    def _upsert(self, table: Table, values: dict[str, object], index: list[str]) -> None:
        def op() -> None:
            with self._engine.begin() as connection:
                statement = insert(table).values(**values)
                update = {key: statement.excluded[key] for key in values if key not in index}
                connection.execute(statement.on_conflict_do_update(index_elements=index, set_=update))
        self._retry(op)

    def _insert(self, table: Table, values: dict[str, object]) -> None:
        def op() -> None:
            with self._engine.begin() as connection:
                connection.execute(table.insert().values(**values))
        self._retry(op)

    def _insert_many(self, table: Table, values: list[dict[str, object]]) -> None:
        def op() -> None:
            with self._engine.begin() as connection:
                connection.execute(table.insert(), values)
        self._retry(op)

    def _fetch_all(self, table: Table) -> list[dict[str, object]]:
        def op() -> list[dict[str, object]]:
            with self._engine.connect() as connection:
                return [dict(row) for row in connection.execute(select(table)).mappings()]
        return self._retry(op)
