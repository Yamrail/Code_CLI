#!/usr/bin/env python3
"""One explicit, optional OpenAI Responses connectivity probe (Python stdlib only).

Does nothing online unless --live is supplied and the foreground human confirms.
No retry, no model fallback, no credential logging, no cached login extraction.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = "https://api.openai.com/v1/responses"
FIXED_INPUT = "This is a synthetic YamRail judge connectivity probe. Reply exactly YR_JUDGE_API_OK."
EXPECTED_OUTPUT = "YR_JUDGE_API_OK"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def output_text(response: dict) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct:
        return direct
    chunks = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for block in item.get("content", []):
            if block.get("type") == "output_text" and isinstance(block.get("text"), str):
                chunks.append(block["text"])
    return "".join(chunks)


def persist(receipt: dict, destination: Path | None) -> None:
    if destination is None:
        return
    if destination.exists():
        raise ValueError("HOLD: refusing to overwrite an existing receipt")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="Actually make one optional API request")
    ap.add_argument("--model", default="gpt-6.1-sol")
    ap.add_argument("--out", type=Path, help="Write a new redacted receipt file (never overwrite)")
    args = ap.parse_args()

    if not args.live:
        print(json.dumps({"status": "NOT_EXECUTED", "reason": "No --live flag; zero provider calls", "model": args.model}))
        return 0

    if args.model != "gpt-6.1-sol":
        print(json.dumps({"status": "HOLD_MODEL_PIN", "model": args.model}))
        return 2

    print("Optional ONE-REQUEST external API operation. Provider billing/access may apply.")
    print("No judge API key is required for the three offline demo fixtures.")
    if input("Foreground human: type RUN to authorize exactly one request: ").strip() != "RUN":
        print(json.dumps({"status": "NOT_EXECUTED_HUMAN_DECLINED"}))
        return 2

    key = os.environ.get("OPENAI_API_KEY")
    source = "HOST_ENV_PRESENT" if key else "FOREGROUND_INPUT"
    if not key:
        key = getpass.getpass("Existing active OpenAI API secret (hidden; do not paste into agent chat): ")
    key = key.strip() if key else ""
    if not key:
        print(json.dumps({"status": "HOLD_CREDENTIAL_UNAVAILABLE"}))
        return 2

    body = json.dumps({
        "model": args.model,
        "input": FIXED_INPUT,
        "max_output_tokens": 1024,
        "store": False,
    }, separators=(",", ":")).encode("utf-8")
    request = Request(ENDPOINT, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key,
    })
    # The HTTP client must hold the credential in memory for this operation.
    # This script makes no guarantee about same-user process inspection or OS swap.
    receipt = {
        "schema": "yamrail.judge.one-shot-api-connectivity/1",
        "endpoint_host": "api.openai.com",
        "endpoint_path": "/v1/responses",
        "method": "POST",
        "model_requested": args.model,
        "credential_source": source,
        "secret_value_recorded": False,
        "request_body_sha256": sha(body),
        "request_count_max": 1,
        "retry_count": 0,
        "external_submission_authority": False,
    }
    start = time.monotonic()
    try:
        with urlopen(request, timeout=45) as response:
            raw = response.read(2 * 1024 * 1024)
            code = response.status
        result = json.loads(raw)
        visible = output_text(result).strip()
        returned = result.get("model")
        receipt.update({
            "http_status": code,
            "response_sha256": sha(raw),
            "response_id": result.get("id"),
            "model_returned": returned,
            "response_status": result.get("status"),
            "usage": result.get("usage"),
            "latency_ms": round((time.monotonic() - start) * 1000),
            "visible_output": visible[:256],
        })
        if (code == 200 and returned == args.model and result.get("status") == "completed"
                and visible == EXPECTED_OUTPUT):
            receipt["status"] = "PASS_LIVE_SINGLE_REQUEST"
        else:
            receipt["status"] = "HOLD_RESULT_CONTRACT_MISMATCH_NO_RETRY"
    except HTTPError as exc:
        # Read only to create a digest; do not print or persist the provider error body.
        data = exc.read(8192)
        receipt.update({
            "status": "HOLD_HTTP_ERROR_NO_RETRY", "http_status": exc.code,
            "response_body_sha256": sha(data),
            "latency_ms": round((time.monotonic() - start) * 1000),
        })
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        receipt.update({
            "status": "UNKNOWN_COMPLETION_NO_AUTOMATIC_RETRY",
            "latency_ms": round((time.monotonic() - start) * 1000),
        })
    finally:
        key = None
        request = None

    try:
        persist(receipt, args.out)
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "HOLD_RECEIPT_PERSISTENCE", "detail": type(exc).__name__}))
        return 2
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt["status"] == "PASS_LIVE_SINGLE_REQUEST" else 2


if __name__ == "__main__":
    sys.exit(main())
