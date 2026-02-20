#!/usr/bin/env python3

"""LLM-first statement parser.

Uses the OpenClaw model engine by invoking `openclaw agent --json`.
Returns strict JSON suitable for validation + SQLite insert.

No secrets are stored. PDF passwords are never sent to the model.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


SYSTEM_PROMPT = """You are a strict JSON extraction engine.

We will send the statement text in multiple chunks.
Acknowledge each chunk with exactly: OK

When asked to produce output, return ONLY valid JSON. No markdown. No explanations.

Schema:
{
  "statement": {
    "issuer": "string",
    "period_start": "YYYY-MM-DD|null",
    "period_end": "YYYY-MM-DD|null",
    "due_date": "YYYY-MM-DD|null",
    "total_minor": 0,
    "currency": "ISO-4217",
    "items": [
      {
        "posted_at": "YYYY-MM-DD|null",
        "description_raw": "string",
        "merchant_norm": "string|null",
        "amount_minor": 0,
        "currency": "ISO-4217",
        "direction": "outflow|inflow",
        "kind": "purchase|refund|fee|interest|adjustment|payment",
        "installment_n": null,
        "installment_total": null,
        "orig_amount_minor": null,
        "orig_currency": null,
        "fx_rate": null
      }
    ]
  }
}

Rules:
- Amounts are integers in minor units (e.g. cents).
- If a field is unknown, use null (not empty string) for nullable fields.
- IOF should be represented as a separate item with kind="fee" and direction="outflow".
- For domestic BRL purchases, orig_* and fx_rate should be null.
"""


@dataclass
class AgentResult:
    text: str


def run_openclaw_agent(message: str, session_id: str | None = None, timeout_s: int = 600) -> AgentResult:
    cmd = [
        "openclaw",
        "agent",
        "--json",
        "--thinking",
        "minimal",
        "--timeout",
        str(timeout_s),
        "--message",
        message,
    ]
    if session_id:
        cmd += ["--session-id", session_id]

    p = subprocess.run(cmd, check=True, capture_output=True, text=True)
    data = json.loads(p.stdout)

    # Extract assistant text from common OpenClaw CLI shapes.
    txt = None
    # Newer shape: result.payloads[0].text
    r = data.get("result")
    if isinstance(r, dict):
        payloads = r.get("payloads")
        if isinstance(payloads, list) and payloads:
            first = payloads[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                txt = first["text"]

    if txt is None:
        # Older/fallback shapes
        for key in ("text", "message", "reply", "output"):
            if isinstance(data.get(key), str):
                txt = data[key]
                break

    if txt is None:
        txt = json.dumps(data)

    return AgentResult(text=txt)


def chunk_text(s: str, max_chars: int = 12000) -> list[str]:
    chunks: list[str] = []
    i = 0
    while i < len(s):
        chunks.append(s[i : i + max_chars])
        i += max_chars
    return chunks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issuer", required=True)
    ap.add_argument("--text-file", required=True)
    ap.add_argument("--session-id", default=None)
    args = ap.parse_args()

    text = Path(args.text_file).read_text(encoding="utf-8", errors="replace")
    session_id = args.session_id or f"statement-copilot-{args.issuer}"

    # Prime the session with instructions
    run_openclaw_agent(SYSTEM_PROMPT + f"\n\nISSUER: {args.issuer}", session_id=session_id)

    # Send chunks, require OK
    for idx, ch in enumerate(chunk_text(text), 1):
        msg = f"CHUNK {idx}:\n" + ch + "\n\nReply only OK."
        run_openclaw_agent(msg, session_id=session_id)

    # Ask for final JSON
    final = run_openclaw_agent(
        "Now produce the JSON output according to the schema. Return ONLY JSON.",
        session_id=session_id,
        timeout_s=600,
    )

    print(final.text.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
