"""Apify client helpers for CV-Pilot job scraping.

Encapsulates CLI interaction with the ``apify`` tool: actor cost queries,
actor invocation, and dataset parsing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Optional

import typer

from _lib.errors import CV_PilotError


def check_apify_cli() -> None:
    """Raise ``typer.Exit(1)`` if the ``apify`` CLI is not on PATH."""
    if shutil.which("apify") is None:
        typer.echo(
            json.dumps({
                "ok": False,
                "error": "Apify CLI not found on PATH. Install it and configure APIFY_TOKEN.",
                "code": "APIFY_CLI_MISSING",
            }, ensure_ascii=False),
            err=True,
        )
        raise typer.Exit(code=1)


def actor_cost(actor: str, count: int) -> float:
    """Query the Apify API for the actor's real-time price and compute total cost."""
    proc = subprocess.run(
        ["apify", "actors", "info", actor, "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        typer.echo(
            json.dumps({
                "ok": False,
                "error": f"apify actors info failed: {proc.stderr.strip() or proc.stdout.strip()}",
                "code": "APIFY_INFO_FAILED",
            }, ensure_ascii=False),
            err=True,
        )
        raise typer.Exit(code=1)
    info = json.loads(proc.stdout)
    pricing = info.get("currentPricingInfo") or (info.get("pricingInfos") or [{}])[0] or info
    events = (pricing.get("pricingPerEvent") or {}).get("actorChargeEvents") or {}
    item = float(events.get("apify-default-dataset-item", {}).get("eventPriceUsd") or 0)
    start = float(events.get("apify-actor-start", {}).get("eventPriceUsd") or 0)
    return round(count * item + start, 6)


def parse_dataset(stdout: str) -> list[dict]:
    """Parse Apify dataset output (JSON array or NDJSON fallback)."""
    text = stdout.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "data"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []
    except json.JSONDecodeError:
        items: list[dict] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return items


def call_actor(actor: str, actor_input: dict) -> list[dict]:
    """Invoke an Apify actor and return the parsed dataset."""
    proc = subprocess.run(
        ["apify", "call", actor, "--input", json.dumps(actor_input),
         "--silent", "--output-dataset"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        typer.echo(
            json.dumps({
                "ok": False,
                "error": f"apify call failed: {proc.stderr.strip() or proc.stdout.strip()}",
                "code": "APIFY_CALL_FAILED",
            }, ensure_ascii=False),
            err=True,
        )
        raise typer.Exit(code=1)
    return parse_dataset(proc.stdout)


def persist_jobs(jobs: list, query_py: str) -> Optional[dict]:
    """Persist a batch of normalized jobs via ``query.py job insert-batch``."""
    from _lib.models import JobInsert  # avoid circular at module level

    if not jobs:
        return None
    payload = [j.model_dump() for j in jobs]
    import sys
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as tf:
        json.dump(payload, tf, ensure_ascii=False)
        tmp_path = tf.name
    try:
        proc = subprocess.run(
            [sys.executable, query_py, "job", "insert-batch", "--file", tmp_path],
            capture_output=True, text=True, encoding="utf-8",
        )
        if proc.returncode != 0:
            typer.echo(
                json.dumps({
                    "ok": False,
                    "error": f"query.py insert-batch failed: {proc.stderr.strip() or proc.stdout.strip()}",
                    "code": "PERSIST_FAILED",
                }, ensure_ascii=False),
                err=True,
            )
            raise typer.Exit(code=1)
        return json.loads(proc.stdout)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
