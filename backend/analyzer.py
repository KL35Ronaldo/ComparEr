"""
analyzer.py — Core comparison logic for the Followback backend.

Pure functions: no Flask, no I/O, no state.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from html.parser import HTMLParser
from typing import NamedTuple

# ── Constants ─────────────────────────────────────────────────
MAX_ZIP_BYTES        = 100 * 1024 * 1024   # 100 MB compressed
MAX_UNCOMPRESSED     = 500 * 1024 * 1024   # 500 MB decompressed guard
MAX_ENTRIES          = 10_000

# Matches: followers.json, followers_1.json, followers_2.html, etc.
FOLLOWERS_FILE_RE    = re.compile(r"(?:^|[/\\])followers(?:_\d+)?\.(?:json|html)$", re.IGNORECASE)
FOLLOWING_FILE_RE    = re.compile(r"(?:^|[/\\])following\.(?:json|html)$", re.IGNORECASE)
INSTAGRAM_HOST_RE    = re.compile(r"^https?://(?:www\.)?instagram\.com/", re.IGNORECASE)
VALID_USERNAME_RE    = re.compile(r"^[\w.]{1,30}$")


# ── Result types ──────────────────────────────────────────────
class CompareResult(NamedTuple):
    followers:         int
    following:         int
    mutuals:           int
    not_following_back: list[str]   # G − F: user follows, they don't follow back
    not_followed_back:  list[str]   # F − G: they follow user, user doesn't follow them


class AnalyzerError(Exception):
    """Friendly, user-visible error with an optional HTTP status code."""
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ── Username normalisation ────────────────────────────────────
def normalize_username(raw: str | None) -> str | None:
    if not isinstance(raw, str):
        return None
    u = raw.strip().lower().lstrip("@")
    if VALID_USERNAME_RE.match(u):
        return u
    return None


def username_from_href(href: str | None) -> str | None:
    if not isinstance(href, str):
        return None
    if not INSTAGRAM_HOST_RE.match(href):
        return None
    try:
        from urllib.parse import urlparse
        parsed = urlparse(href)
        parts  = parsed.path.strip("/").split("/")
        if len(parts) != 1 or not parts[0]:
            return None
        return normalize_username(parts[0])
    except Exception:
        return None


# ── JSON parsing ──────────────────────────────────────────────
def extract_from_json(data: object) -> set[str]:
    results: set[str] = set()

    def process_entry(entry: object) -> None:
        if not isinstance(entry, dict):
            return
        # Format: { string_list_data: [{ value: "...", href: "...", timestamp: N }] }
        sld = entry.get("string_list_data")
        if isinstance(sld, list):
            for item in sld:
                if isinstance(item, dict):
                    u = normalize_username(item.get("value")) or username_from_href(item.get("href"))
                    if u:
                        results.add(u)
        # Flat format: { value: "username" }
        if isinstance(entry.get("value"), str):
            u = normalize_username(entry["value"])
            if u:
                results.add(u)
        # Flat format: { href: "..." }
        if isinstance(entry.get("href"), str):
            u = username_from_href(entry["href"])
            if u:
                results.add(u)

    if isinstance(data, list):
        for item in data:
            process_entry(item)
    elif isinstance(data, dict):
        for val in data.values():
            if isinstance(val, list):
                for item in val:
                    process_entry(item)
            else:
                process_entry(val)

    return results


# ── HTML parsing ──────────────────────────────────────────────
class _InstagramHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.usernames: set[str] = set()
        self._in_anchor = False
        self._current_href: str | None = None  # None = no href attr; "" = href present but empty

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            attr_dict = dict(attrs)
            # Distinguish "no href attribute" from "href attribute present but empty"
            self._current_href = attr_dict.get("href", None)
            if self._current_href is None:
                self._current_href = None   # no href at all
            else:
                self._current_href = self._current_href or ""
            self._in_anchor = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._in_anchor = False
            self._current_href = None

    def handle_data(self, data: str) -> None:
        if not self._in_anchor:
            return
        if self._current_href is not None:
            # href attribute exists — only use it if it's a valid Instagram URL
            u = username_from_href(self._current_href)
            if u:
                self.usernames.add(u)
            # Do NOT fall back to anchor text when a non-Instagram href is present
        else:
            # No href attribute at all — try anchor text as fallback
            u = normalize_username(data.strip())
            if u:
                self.usernames.add(u)


def extract_from_html(html: str) -> set[str]:
    parser = _InstagramHTMLParser()
    parser.feed(html)
    return parser.usernames


# ── Parse a single file's content ────────────────────────────
def parse_file_content(filename: str, content: str) -> set[str]:
    lower = filename.lower()
    if lower.endswith(".json"):
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise AnalyzerError(
                f'The file "{filename}" contains invalid JSON. It may be corrupted. ({e})'
            )
        users = extract_from_json(data)
        if not users:
            raise AnalyzerError(
                f'No recognizable account data found in "{filename}". The export format may be unsupported.'
            )
        return users

    if lower.endswith(".html") or lower.endswith(".htm"):
        users = extract_from_html(content)
        if not users:
            raise AnalyzerError(
                f'No recognizable account links found in "{filename}". The HTML format may be unsupported.'
            )
        return users

    raise AnalyzerError(f'Unsupported file format: "{filename}".')


# ── ZIP validation & discovery ────────────────────────────────
def validate_and_discover(zf: zipfile.ZipFile) -> tuple[list[str], list[str]]:
    """
    Walk archive entries, enforce safety limits, discover relevant files.
    Returns (follower_paths, following_paths).
    """
    follower_paths: list[str] = []
    following_paths: list[str] = []
    total_uncompressed = 0
    entry_count = 0

    for info in zf.infolist():
        entry_count += 1
        if entry_count > MAX_ENTRIES:
            raise AnalyzerError(
                "This archive contains too many entries. It may not be a valid Instagram export."
            )

        # Guard against path traversal
        norm = info.filename.replace("\\", "/")
        if ".." in norm.split("/") or norm.startswith("/"):
            raise AnalyzerError(
                f'Suspicious archive path detected: "{info.filename}". Processing stopped.'
            )

        total_uncompressed += info.file_size
        if total_uncompressed > MAX_UNCOMPRESSED:
            raise AnalyzerError(
                "The archive would expand to an unsafe size. It may be a ZIP bomb or an incorrect file."
            )

        if info.is_dir():
            continue

        name = norm.split("/")[-1]
        if FOLLOWERS_FILE_RE.search(name):
            follower_paths.append(info.filename)
        elif FOLLOWING_FILE_RE.search(name):
            following_paths.append(info.filename)

    if not follower_paths and not following_paths:
        raise AnalyzerError(
            "No followers or following files were found in this archive. "
            "Make sure you uploaded an Instagram data export ZIP (not extracted)."
        )

    if not follower_paths:
        raise AnalyzerError(
            "No followers file was found (e.g. followers_1.json). "
            "Please ensure you selected the complete Instagram data export."
        )

    if not following_paths:
        raise AnalyzerError(
            "No following file was found (e.g. following.json). "
            "Please ensure you selected the complete Instagram data export."
        )

    return follower_paths, following_paths


# ── Main analysis entry point ─────────────────────────────────
def analyze_zip_bytes(raw_bytes: bytes) -> CompareResult:
    """
    Analyze an Instagram export ZIP from raw bytes.
    Raises AnalyzerError for all user-visible problems.
    """
    if len(raw_bytes) > MAX_ZIP_BYTES:
        raise AnalyzerError(
            f"The file is too large ({len(raw_bytes) / 1024 / 1024:.1f} MB). "
            "Maximum supported size is 100 MB.",
            status=413,
        )

    # Validate ZIP magic bytes
    if len(raw_bytes) < 4 or raw_bytes[:4] != b"PK\x03\x04":
        raise AnalyzerError(
            "The uploaded file is not a valid ZIP archive. "
            "Please upload the original Instagram export ZIP."
        )

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
    except zipfile.BadZipFile:
        raise AnalyzerError(
            "Failed to open the ZIP archive. It may be corrupted or password-protected."
        )

    with zf:
        follower_paths, following_paths = validate_and_discover(zf)

        # Read & parse all follower files
        followers_set: set[str] = set()
        for path in follower_paths:
            content = zf.read(path).decode("utf-8", errors="replace")
            partial = parse_file_content(path.split("/")[-1], content)
            followers_set.update(partial)

        # Read & parse following file (take first match)
        following_content = zf.read(following_paths[0]).decode("utf-8", errors="replace")
        following_set = parse_file_content(following_paths[0].split("/")[-1], following_content)

    return compare_sets(followers_set, following_set)


# ── Set comparison ────────────────────────────────────────────
def compare_sets(followers: set[str], following: set[str]) -> CompareResult:
    """
    followers = F  (accounts that follow the user)
    following = G  (accounts the user follows)

    not_following_back = G − F  (user follows, they don't follow back)
    not_followed_back  = F − G  (they follow, user doesn't follow back)
    mutuals            = F ∩ G
    """
    not_following_back = sorted(following - followers)
    not_followed_back  = sorted(followers - following)
    mutuals            = len(followers & following)

    return CompareResult(
        followers=len(followers),
        following=len(following),
        mutuals=mutuals,
        not_following_back=not_following_back,
        not_followed_back=not_followed_back,
    )
