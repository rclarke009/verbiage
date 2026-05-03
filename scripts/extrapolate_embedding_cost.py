#!/usr/bin/env python3
"""
Pilot: sample local PDFs with the same extraction + chunk + metering as ingest (no OpenAI calls),
sum embedding_tokens_estimate, extrapolate to full corpus size and $ @ text-embedding-3-small.

Supports optional synthetic suffix to model OCR-derived text ("75 images" style char budget).

Run from project root:
  PYTHONPATH=. python scripts/extrapolate_embedding_cost.py --pdf-dir ./pdfs --max-files 20 --extrapolate-to 1000

See project cost notes for methodology; images in PDFs are not processed unless they become text.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _setup_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    return root


def main() -> int:
    root = _setup_path()

    parser = argparse.ArgumentParser(
        description="Extrapolate OpenAI embedding corpus cost from a PDF pilot sample."
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        help="Directory of PDFs (.pdf suffix); scanned non-recursively.",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        action="append",
        dest="pdfs",
        default=[],
        help="Individual PDF path (repeatable).",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=20,
        help="Max PDFs to process when using --pdf-dir (default 20).",
    )
    parser.add_argument(
        "--extrapolate-to",
        type=int,
        default=1000,
        help="Assume this many reports in full corpus for cost projection.",
    )
    parser.add_argument(
        "--price-per-m-tokens",
        type=float,
        default=0.02,
        help="USD per 1M embedding input tokens (text-embedding-3-small std tier default 0.02).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=800,
        help="Match ingest chunk_size (default 800).",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=100,
        help="Match ingest chunk_overlap (default 100).",
    )
    parser.add_argument(
        "--append-synthetic-chars",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Append N filler characters before chunking to model OCR/caption bulk text per report "
            "(e.g. 75 images × ~300 chars ≈ 22500)."
        ),
    )
    args = parser.parse_args()

    from app.chunking import chunk_text_chars
    from app.embedding_usage_estimate import embedding_metering
    from app.pdf_extract import extract_text_from_pdf

    paths: list[Path] = []
    if args.pdfs:
        paths.extend(args.pdfs)
    if args.pdf_dir:
        d = args.pdf_dir
        if not d.is_dir():
            print(f"MYDEBUG → not a directory: {d}", file=sys.stderr)
            return 2
        found = sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
        paths.extend(found[: max(0, args.max_files)])

    if not paths:
        parser.error("Provide --pdf-dir and/or one or more --pdf.")
        return 2

    filler = ""
    if args.append_synthetic_chars > 0:
        filler = "\n" + ("x" * args.append_synthetic_chars)

    total_chars = 0
    total_toks = 0
    processed = 0
    skipped = 0

    print(
        "file\tchars_extracted(+synth)\tnum_chunks\tembedding_chars_total\tembedding_tokens_estimate\tstatus",
        flush=True,
    )
    for p in paths:
        if not p.is_file():
            print(f"{p}\t-\t-\t-\t-\tmissing", flush=True)
            skipped += 1
            continue
        try:
            data = p.read_bytes()
            text = extract_text_from_pdf(data) + filler
            chunks = chunk_text_chars(text, args.chunk_size, args.chunk_overlap)
            contents = [c.content for c in chunks]
            ch, toks = embedding_metering(contents)
        except ValueError as e:
            print(
                f"{p}\t-\t-\t-\t-\textract_failed:{e}",
                flush=True,
            )
            skipped += 1
            continue

        extracted_len = len(text)
        processed += 1
        total_chars += ch
        total_toks += toks
        print(
            f"{p}\t{extracted_len}\t{len(chunks)}\t{ch}\t{toks}\tok",
            flush=True,
        )

    if processed == 0:
        print("MYDEBUG → no PDFs succeeded; nothing to extrapolate.", file=sys.stderr)
        return 1

    sample_avg_toks = total_toks / processed
    extrap_toks_total = sample_avg_toks * args.extrapolate_to
    extrap_usd = (extrap_toks_total / 1e6) * args.price_per_m_tokens

    print("", flush=True)
    print(f"pilot_processed={processed}", flush=True)
    print(f"pilot_skipped={skipped}", flush=True)
    print(f"pilot_total_embedding_tokens_estimate={total_toks}", flush=True)
    print(f"pilot_avg_embedding_tokens_per_report={sample_avg_toks:.1f}", flush=True)
    print(
        f"extrapolate_reports={args.extrapolate_to} "
        f"total_embedding_tokens_estimate={extrap_toks_total:.0f}",
        flush=True,
    )
    print(
        f"extrapolated_embedding_cost_usd @ ${args.price_per_m_tokens}/M ≈ "
        f"${extrap_usd:.4f}",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
