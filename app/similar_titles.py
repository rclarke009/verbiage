"""
Fuzzy matching of proposed document names against existing titles (advisory duplicate check).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_EXT_RE = re.compile(r"\.(pdf|txt|doc|docx)$", re.IGNORECASE)

# Trailing/anywhere version token: v9, v10, V 10, v.10
_VERSION_RE = re.compile(r"\bv\.?\s*(\d+)\b", re.IGNORECASE)

_EXT_AT_END_RE = re.compile(r"\.([a-z0-9]+)$", re.IGNORECASE)

_FORMAT_BY_MIME = {
    "application/vnd.google-apps.document": "gdoc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/pdf": "pdf",
}
_FORMAT_BY_EXT = {"pdf": "pdf", "docx": "docx", "doc": "docx"}

# When the same report exists in several formats, keep the earliest in this list.
# Word/Google Docs extract to cleaner text than PDF (no layout/OCR loss), so they win.
FORMAT_PREFERENCE: tuple[str, ...] = ("gdoc", "docx", "pdf", "other")


def _file_format(f: dict, name_key: str = "name") -> str:
    """Normalized format key ('gdoc' | 'docx' | 'pdf' | 'other') for a file dict."""
    mime = (f.get("mimeType") or "").strip()
    if mime in _FORMAT_BY_MIME:
        return _FORMAT_BY_MIME[mime]
    m = _EXT_AT_END_RE.search((f.get(name_key) or "").strip())
    if m:
        return _FORMAT_BY_EXT.get(m.group(1).lower(), "other")
    return "other"


def _format_rank(fmt: str) -> int:
    try:
        return FORMAT_PREFERENCE.index(fmt)
    except ValueError:
        return len(FORMAT_PREFERENCE)


def normalize_for_similarity(s: str) -> str:
    s = (s or "").lower().strip()
    s = _EXT_RE.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s


def parse_base_and_version(name: str) -> tuple[str, int | None]:
    """
    Split a filename into (normalized base, version int).

    'Address 123 v10.pdf' -> ('address 123', 10). When no vN token is present,
    version is None and base is the fully normalized name. Comparing the int
    (not the string) is what makes v10 rank above v9.
    """
    stem = normalize_for_similarity(name)
    if not stem:
        return "", None
    version: int | None = None
    m = _VERSION_RE.search(stem)
    if m:
        version = int(m.group(1))
        stem = _VERSION_RE.sub(" ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem, version


def select_newest_versions(
    files: list[dict],
    *,
    name_key: str = "name",
    modified_key: str = "modifiedTime",
    id_key: str = "id",
) -> list[dict]:
    """
    Collapse same-named report versions down to the newest one.

    Files are grouped by normalized base name (name minus its extension and vN
    token). A group is collapsed only when at least one member carries a version
    token; the winner is the highest version, then most recent modifiedTime, then
    largest id (deterministic).

    For no-version groups we still avoid ingesting the same report twice in
    different file formats: when a base name appears as both, say, a .docx and a
    .pdf, only the preferred-format file(s) are kept (see FORMAT_PREFERENCE).
    Multiple files of that same top format are all kept, so genuinely distinct
    files that merely share a name are never silently dropped. Output order
    follows first appearance in the input.
    """
    groups: dict[str, list[tuple[int | None, dict]]] = {}
    order: list[str] = []
    extras: list[dict] = []  # ungroupable (empty base) — always kept

    for f in files:
        base, version = parse_base_and_version(f.get(name_key) or "")
        if not base:
            extras.append(f)
            continue
        if base not in groups:
            groups[base] = []
            order.append(base)
        groups[base].append((version, f))

    winners: list[dict] = []
    for base in order:
        members = groups[base]
        if not any(version is not None for version, _ in members):
            files_in_group = [f for _, f in members]
            best_rank = min(_format_rank(_file_format(f, name_key)) for f in files_in_group)
            winners.extend(
                f
                for f in files_in_group
                if _format_rank(_file_format(f, name_key)) == best_rank
            )
            continue
        _, best = max(
            members,
            key=lambda vf: (
                vf[0] if vf[0] is not None else -1,
                vf[1].get(modified_key) or "",
                vf[1].get(id_key) or "",
            ),
        )
        winners.append(best)

    return winners + extras


def similarity_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def find_similar_titles(
    proposed: str,
    doc_rows: list[tuple[str, str | None]],
    *,
    min_ratio: float = 0.82,
    limit: int = 5,
) -> list[tuple[str, str | None, float]]:
    """
    Return up to `limit` matches (doc_id, title, score) with score >= min_ratio.
    Compares normalized proposed string to each document's title, or doc_id if title empty.
    """
    norm_prop = normalize_for_similarity(proposed)
    if not norm_prop:
        return []
    matches: list[tuple[str, str | None, float]] = []
    for doc_id, title in doc_rows:
        label = (title or "").strip() or doc_id
        norm_label = normalize_for_similarity(label)
        if not norm_label:
            continue
        score = 1.0 if norm_prop == norm_label else similarity_ratio(norm_prop, norm_label)
        if score >= min_ratio:
            matches.append((doc_id, title, round(score, 4)))
    matches.sort(key=lambda x: (-x[2], (x[1] or x[0]).lower()))
    return matches[:limit]
