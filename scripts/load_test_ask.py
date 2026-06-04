#!/usr/bin/env python3
"""
Fire concurrent POST /ask or /ask/stream requests to populate Grafana RAG metrics.

Requires a Supabase access token (same Bearer token the SPA sends).
Get one after sign-in: DevTools → Network → any API call → Authorization header,
or set VERBIAGE_LOAD_TEST_TOKEN in the environment.

Examples:
  python scripts/load_test_ask.py --token "$TOKEN" --count 20 --concurrency 3
  python scripts/load_test_ask.py --token "$TOKEN" --endpoint stream --count 15
  python scripts/load_test_ask.py --token "$TOKEN" --endpoint mix --count 30 --url http://localhost:8000

For HTTP-only panels (no RAG metrics), use --health instead of ask traffic.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import httpx

DEFAULT_QUESTIONS = [
    "Please provide text about storm damage to the roof.",
    "Please provide text about shingle damage from wind.",
    "Please provide text about hurricane damage to roofing.",
    "Please provide text about torn or missing shingles.",
    "Please provide text about hail damage to asphalt shingles.",
    "Please provide text about wind uplift and lifted shingles.",
]

DEFAULT_TIMEOUT = 180.0


@dataclass
class RunStats:
    status_codes: Counter[int] = field(default_factory=Counter)
    errors: Counter[str] = field(default_factory=Counter)
    durations_sec: list[float] = field(default_factory=list)


def _load_dotenv_token() -> str:
    root = Path(__file__).resolve().parent.parent
    dotenv = root / ".env"
    if not dotenv.exists():
        return ""
    for line in dotenv.read_text().splitlines():
        line = line.strip()
        if line.startswith("VERBIAGE_LOAD_TEST_TOKEN="):
            return line.split("=", 1)[1].strip().strip("'\"")
    return ""


def _resolve_token(explicit: str | None) -> str:
    token = (explicit or os.getenv("VERBIAGE_LOAD_TEST_TOKEN") or _load_dotenv_token()).strip()
    if not token:
        print(
            "Error: missing token. Pass --token, set VERBIAGE_LOAD_TEST_TOKEN, "
            "or add VERBIAGE_LOAD_TEST_TOKEN=... to .env",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def _pick_endpoint(mode: str, index: int) -> str:
    if mode == "ask":
        return "ask"
    if mode == "stream":
        return "stream"
    return "stream" if index % 2 else "ask"


async def _drain_sse(response: httpx.Response) -> None:
    async for _ in response.aiter_bytes():
        pass


async def _one_ask(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    token: str,
    question: str,
    endpoint: str,
    timeout: float,
    stats: RunStats,
    index: int,
) -> None:
    path = "/ask/stream" if endpoint == "stream" else "/ask"
    url = f"{base_url.rstrip('/')}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {"question": question}
    started = time.perf_counter()
    try:
        if endpoint == "stream":
            async with client.stream(
                "POST",
                url,
                json=body,
                headers=headers,
                timeout=timeout,
            ) as response:
                await _drain_sse(response)
                status = response.status_code
        else:
            response = await client.post(url, json=body, headers=headers, timeout=timeout)
            status = response.status_code
        stats.status_codes[status] += 1
        stats.durations_sec.append(time.perf_counter() - started)
        print(f"[{index:>4}] {endpoint:<6} HTTP {status}  {time.perf_counter() - started:.1f}s  {question[:50]}")
    except httpx.TimeoutException:
        stats.errors["timeout"] += 1
        print(f"[{index:>4}] {endpoint:<6} TIMEOUT after {time.perf_counter() - started:.1f}s", file=sys.stderr)
    except httpx.HTTPError as exc:
        stats.errors[type(exc).__name__] += 1
        print(f"[{index:>4}] {endpoint:<6} ERROR {exc}", file=sys.stderr)


async def _one_health(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    stats: RunStats,
    index: int,
    timeout: float,
) -> None:
    url = f"{base_url.rstrip('/')}/health/ready"
    started = time.perf_counter()
    try:
        response = await client.get(url, timeout=timeout)
        stats.status_codes[response.status_code] += 1
        stats.durations_sec.append(time.perf_counter() - started)
        print(f"[{index:>4}] health HTTP {response.status_code}  {time.perf_counter() - started:.2f}s")
    except httpx.HTTPError as exc:
        stats.errors[type(exc).__name__] += 1
        print(f"[{index:>4}] health ERROR {exc}", file=sys.stderr)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    weight = rank - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def _print_summary(stats: RunStats, *, total: int, elapsed: float) -> None:
    print("\n--- summary ---")
    print(f"requests: {total}")
    print(f"elapsed:  {elapsed:.1f}s")
    if stats.status_codes:
        print("status:  ", dict(sorted(stats.status_codes.items())))
    if stats.errors:
        print("errors:  ", dict(stats.errors))
    if stats.durations_sec:
        print(
            "latency: "
            f"p50={_percentile(stats.durations_sec, 0.50):.2f}s "
            f"p95={_percentile(stats.durations_sec, 0.95):.2f}s "
            f"max={max(stats.durations_sec):.2f}s"
        )
    if stats.status_codes.get(429):
        print(
            "note: 429 responses mean LLM_TOKEN_LIMIT was hit. "
            "Raise LLM_TOKEN_LIMIT in .env for heavier local load tests."
        )


async def _run(args: argparse.Namespace) -> int:
    stats = RunStats()
    started = time.perf_counter()
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)

    async with httpx.AsyncClient(limits=limits) as client:
        if args.health:
            sem = asyncio.Semaphore(args.concurrency)

            async def health_task(i: int) -> None:
                async with sem:
                    await _one_health(
                        client,
                        base_url=args.url,
                        stats=stats,
                        index=i,
                        timeout=args.timeout,
                    )

            await asyncio.gather(*(health_task(i) for i in range(1, args.count + 1)))
        else:
            token = _resolve_token(args.token)
            questions = args.question or DEFAULT_QUESTIONS
            sem = asyncio.Semaphore(args.concurrency)

            async def ask_task(i: int) -> None:
                async with sem:
                    endpoint = _pick_endpoint(args.endpoint, i)
                    question = questions[(i - 1) % len(questions)]
                    await _one_ask(
                        client,
                        base_url=args.url,
                        token=token,
                        question=question,
                        endpoint=endpoint,
                        timeout=args.timeout,
                        stats=stats,
                        index=i,
                    )

            await asyncio.gather(*(ask_task(i) for i in range(1, args.count + 1)))

    _print_summary(stats, total=args.count, elapsed=time.perf_counter() - started)
    return 0 if not stats.errors and stats.status_codes else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load-test Verbiage /ask and /ask/stream for Grafana observability."
    )
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument(
        "--token",
        default=None,
        help="Supabase access token (or VERBIAGE_LOAD_TEST_TOKEN env / .env)",
    )
    parser.add_argument("--count", type=int, default=20, help="Number of requests to send")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Max in-flight requests (default 3; watch LLM_TOKEN_LIMIT)",
    )
    parser.add_argument(
        "--endpoint",
        choices=("ask", "stream", "mix"),
        default="ask",
        help="Target endpoint: sync /ask, SSE /ask/stream, or alternate both",
    )
    parser.add_argument(
        "--question",
        action="append",
        help="Question to use (repeatable; defaults to built-in playbook-style set)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Per-request timeout in seconds (default {DEFAULT_TIMEOUT:.0f})",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Hit GET /health/ready instead (no auth; HTTP metrics only)",
    )
    parser.add_argument(
        "--shuffle",
        action="store_true",
        help="Randomize question order",
    )
    args = parser.parse_args()

    if args.count < 1:
        print("Error: --count must be at least 1", file=sys.stderr)
        sys.exit(1)
    if args.concurrency < 1:
        print("Error: --concurrency must be at least 1", file=sys.stderr)
        sys.exit(1)
    if args.question and args.shuffle:
        random.shuffle(args.question)

    try:
        raise SystemExit(asyncio.run(_run(args)))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
