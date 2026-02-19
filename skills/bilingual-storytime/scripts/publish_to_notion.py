#!/usr/bin/env python3
"""Publish a Markdown story to Notion.

Supports two targets:
- Create a new page inside a **database** (database_id)
- Create a new page under a **parent page** (page_id)

We intentionally keep formatting simple: title + paragraphs + bulleted lists.

Auth: pulls Notion token from `openclaw config` skills.entries.notion.apiKey.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.request

NOTION_VERSION = "2025-09-03"


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip() or "command failed")
    return p.stdout


def notion_token() -> str:
    raw = _run(["openclaw", "config", "get", "skills.entries.notion.apiKey", "--json"]).strip()
    return raw.strip().strip('"')


def req(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    url = "https://api.notion.com/v1" + path
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", f"Bearer {token}")
    r.add_header("Notion-Version", NOTION_VERSION)
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode("utf-8"))


def md_to_blocks(md: str) -> list[dict]:
    blocks: list[dict] = []
    for line in md.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        if line.startswith("# "):
            # ignore title here; handled as page title
            continue
        if line.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": line[3:].strip()}}]}})
            continue
        if line.startswith("- "):
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line[2:].strip()}}]}})
            continue
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": line}}]}})
    return blocks


def extract_title(md: str, fallback: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()[:120]
    return fallback


def normalize_id(raw: str) -> str:
    # Accept dashed/undashed UUID.
    raw = raw.strip()
    if re.fullmatch(r"[0-9a-fA-F]{32}", raw):
        return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}".lower()
    return raw


def main() -> int:
    ap = argparse.ArgumentParser()
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument("--database-id", help="Create a new page inside this Notion database")
    target.add_argument("--parent-page-id", help="Create a new page under this parent page")
    ap.add_argument("--md", required=True, help="Path to markdown story")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--property", default="Name", help="Title property name in the database (only for --database-id)")
    args = ap.parse_args()

    token = notion_token()

    md = open(args.md, "r", encoding="utf-8").read()
    title = extract_title(md, fallback=f"História bilíngue — {args.date}")
    blocks = md_to_blocks(md)

    if args.database_id:
        dbid = normalize_id(args.database_id)
        payload = {
            "parent": {"database_id": dbid},
            "properties": {
                args.property: {"title": [{"type": "text", "text": {"content": title}}]}
            },
            "children": blocks[:90],
        }
    else:
        pid = normalize_id(args.parent_page_id)
        payload = {
            "parent": {"type": "page_id", "page_id": pid},
            "properties": {
                "title": {"title": [{"type": "text", "text": {"content": title}}]}
            },
            "children": blocks[:90],
        }

    created = req("POST", "/pages", token, payload)
    print(created.get("url", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
