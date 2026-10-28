"""
test_analyzer.py — Unit tests for the Followback analyzer.

Run from the project root:
  python -m pytest tests/ -v
  # or without pytest:
  python -m unittest discover -s tests -v
"""

import io
import json
import os
import sys
import unittest
import zipfile

# Allow importing from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from analyzer import (
    AnalyzerError,
    analyze_zip_bytes,
    compare_sets,
    extract_from_json,
    extract_from_html,
    normalize_username,
    parse_file_content,
    username_from_href,
)


# ── Helpers ───────────────────────────────────────────────────
def make_zip(files: dict[str, str]) -> bytes:
    """Create an in-memory ZIP archive from a dict of {path: content}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


def json_followers(usernames: list[str]) -> str:
    """Instagram JSON followers list format."""
    return json.dumps([
        {
            "string_list_data": [
                {"href": f"https://www.instagram.com/{u}/", "value": u, "timestamp": 1700000000}
            ]
        }
        for u in usernames
    ])


def json_following(usernames: list[str]) -> str:
    """Instagram JSON following list format (wrapped in object)."""
    return json.dumps({
        "relationships_following": [
            {
                "string_list_data": [
                    {"href": f"https://www.instagram.com/{u}/", "value": u, "timestamp": 1700000000}
                ]
            }
            for u in usernames
        ]
    })


def html_list(usernames: list[str]) -> str:
    """Simple Instagram-style HTML export."""
    links = "\n".join(
        f'<a href="https://www.instagram.com/{u}/">{u}</a>' for u in usernames
    )
    return f"<html><body>{links}</body></html>"


# ══════════════════════════════════════════════════════════════
# 1. Core comparison logic
# ══════════════════════════════════════════════════════════════
class TestCompareLogic(unittest.TestCase):

    def test_basic_correct_sets(self):
        """G − F = not_following_back; F − G = not_followed_back."""
        followers = {"alice", "charlie", "david"}
        following = {"alice", "bob", "charlie"}
        result = compare_sets(followers, following)

        self.assertEqual(result.not_following_back, ["bob"])
        self.assertEqual(result.not_followed_back,  ["david"])
        self.assertEqual(result.mutuals, 2)   # alice, charlie
        self.assertEqual(result.followers, 3)
        self.assertEqual(result.following, 3)

    def test_mutuals_excluded_from_both_lists(self):
        followers = {"alice", "bob", "carol"}
        following = {"alice", "bob", "dave"}
        result = compare_sets(followers, following)

        self.assertNotIn("alice", result.not_following_back)
        self.assertNotIn("bob",   result.not_following_back)
        self.assertNotIn("alice", result.not_followed_back)
        self.assertNotIn("bob",   result.not_followed_back)
        self.assertEqual(result.mutuals, 2)

    def test_empty_followers(self):
        result = compare_sets(set(), {"alice", "bob"})
        self.assertEqual(result.followers, 0)
        self.assertEqual(result.following, 2)
        self.assertEqual(result.not_following_back, ["alice", "bob"])
        self.assertEqual(result.not_followed_back,  [])

    def test_empty_following(self):
        result = compare_sets({"alice", "bob"}, set())
        self.assertEqual(result.following, 0)
        self.assertEqual(result.not_following_back, [])
        self.assertEqual(result.not_followed_back,  ["alice", "bob"])

    def test_both_empty(self):
        result = compare_sets(set(), set())
        self.assertEqual(result.followers, 0)
        self.assertEqual(result.following, 0)
        self.assertEqual(result.mutuals, 0)
        self.assertEqual(result.not_following_back, [])
        self.assertEqual(result.not_followed_back,  [])

    def test_everyone_mutual(self):
        users = {"alice", "bob", "carol"}
        result = compare_sets(users, users)
        self.assertEqual(result.mutuals, 3)
        self.assertEqual(result.not_following_back, [])
        self.assertEqual(result.not_followed_back,  [])

    def test_sorted_output(self):
        followers = {"zara", "anna"}
        following = {"zara", "mike"}
        result = compare_sets(followers, following)
        self.assertEqual(result.not_following_back, ["mike"])
        self.assertEqual(result.not_followed_back,  ["anna"])

    def test_duplicate_usernames_deduplicated(self):
        """Duplicates in the input sets must not produce duplicates in output."""
        # Sets already deduplicate, but ensure compare_sets handles dupes in inputs
        followers = {"alice", "alice", "bob"}  # sets deduplicate automatically
        following = {"alice", "alice"}
        result = compare_sets(followers, following)
        self.assertEqual(result.not_followed_back.count("bob"), 1)


# ══════════════════════════════════════════════════════════════
# 2. Username normalisation
# ══════════════════════════════════════════════════════════════
class TestNormalizeUsername(unittest.TestCase):

    def test_lowercase(self):
        self.assertEqual(normalize_username("Alice"), "alice")

    def test_strips_at(self):
        self.assertEqual(normalize_username("@alice"), "alice")

    def test_strips_whitespace(self):
        self.assertEqual(normalize_username("  alice  "), "alice")

    def test_valid_chars(self):
        self.assertEqual(normalize_username("alice.smith_99"), "alice.smith_99")

    def test_invalid_chars_rejected(self):
        self.assertIsNone(normalize_username("alice#smith"))
        self.assertIsNone(normalize_username("alice smith"))
        self.assertIsNone(normalize_username("alice/smith"))

    def test_too_long(self):
        self.assertIsNone(normalize_username("a" * 31))

    def test_non_string(self):
        self.assertIsNone(normalize_username(None))
        self.assertIsNone(normalize_username(123))

    def test_empty(self):
        self.assertIsNone(normalize_username(""))

    def test_case_insensitive_comparison(self):
        u1 = normalize_username("Alice")
        u2 = normalize_username("alice")
        self.assertEqual(u1, u2)


# ══════════════════════════════════════════════════════════════
# 3. username_from_href
# ══════════════════════════════════════════════════════════════
class TestUsernameFromHref(unittest.TestCase):

    def test_valid_instagram_url(self):
        self.assertEqual(username_from_href("https://www.instagram.com/alice/"), "alice")

    def test_without_trailing_slash(self):
        self.assertEqual(username_from_href("https://www.instagram.com/bob"), "bob")

    def test_non_instagram_url_rejected(self):
        self.assertIsNone(username_from_href("https://example.com/alice"))

    def test_sub_path_rejected(self):
        self.assertIsNone(username_from_href("https://www.instagram.com/alice/posts/"))

    def test_non_url_rejected(self):
        self.assertIsNone(username_from_href("not-a-url"))

    def test_none_rejected(self):
        self.assertIsNone(username_from_href(None))


# ══════════════════════════════════════════════════════════════
# 4. JSON parsing
# ══════════════════════════════════════════════════════════════
class TestExtractFromJSON(unittest.TestCase):

    def _parse(self, text: str):
        return extract_from_json(json.loads(text))

    def test_array_format(self):
        users = self._parse(json_followers(["alice", "bob"]))
        self.assertIn("alice", users)
        self.assertIn("bob", users)

    def test_object_format(self):
        users = self._parse(json_following(["carol", "dave"]))
        self.assertIn("carol", users)
        self.assertIn("dave", users)

    def test_case_normalized(self):
        data = json.dumps([{"string_list_data": [{"value": "Alice", "href": "", "timestamp": 0}]}])
        users = self._parse(data)
        self.assertIn("alice", users)

    def test_missing_value_key(self):
        data = json.dumps([{"string_list_data": [{"href": "https://www.instagram.com/alice/", "timestamp": 0}]}])
        users = self._parse(data)
        self.assertIn("alice", users)

    def test_empty_array(self):
        users = self._parse("[]")
        self.assertEqual(len(users), 0)

    def test_malformed_structure_graceful(self):
        data = json.dumps([{"unexpected_key": "value"}])
        users = self._parse(data)
        self.assertEqual(len(users), 0)


# ══════════════════════════════════════════════════════════════
# 5. HTML parsing
# ══════════════════════════════════════════════════════════════
class TestExtractFromHTML(unittest.TestCase):

    def test_valid_html_export(self):
        html = html_list(["alice", "bob"])
        users = extract_from_html(html)
        self.assertIn("alice", users)
        self.assertIn("bob", users)

    def test_non_instagram_links_ignored(self):
        html = '<a href="https://example.com/alice">alice</a>'
        users = extract_from_html(html)
        self.assertEqual(len(users), 0)

    def test_empty_html(self):
        users = extract_from_html("")
        self.assertEqual(len(users), 0)

    def test_malformed_html_graceful(self):
        html = "<a href=not-a-url>alice</a>"
        # Should not crash; may or may not extract
        users = extract_from_html(html)
        self.assertIsInstance(users, set)


# ══════════════════════════════════════════════════════════════
# 6. parse_file_content
# ══════════════════════════════════════════════════════════════
class TestParseFileContent(unittest.TestCase):

    def test_json_file(self):
        users = parse_file_content("followers_1.json", json_followers(["alice"]))
        self.assertIn("alice", users)

    def test_html_file(self):
        users = parse_file_content("following.html", html_list(["bob"]))
        self.assertIn("bob", users)

    def test_invalid_json_raises(self):
        with self.assertRaises(AnalyzerError):
            parse_file_content("followers_1.json", "{bad json")

    def test_empty_json_array_raises(self):
        with self.assertRaises(AnalyzerError):
            parse_file_content("followers_1.json", "[]")

    def test_unsupported_format_raises(self):
        with self.assertRaises(AnalyzerError):
            parse_file_content("followers_1.txt", "alice")


# ══════════════════════════════════════════════════════════════
# 7. ZIP analysis (analyze_zip_bytes)
# ══════════════════════════════════════════════════════════════
class TestAnalyzeZipBytes(unittest.TestCase):

    def _make_json_zip(self, followers_lists: dict[str, list[str]], following: list[str]) -> bytes:
        files = {}
        for path, users in followers_lists.items():
            files[path] = json_followers(users)
        files["connections/followers_and_following/following.json"] = json_following(following)
        return make_zip(files)

    def test_basic_json_analysis(self):
        z = self._make_json_zip(
            {"connections/followers_and_following/followers_1.json": ["alice", "charlie", "david"]},
            ["alice", "bob", "charlie"],
        )
        result = analyze_zip_bytes(z)
        self.assertEqual(result.not_following_back, ["bob"])
        self.assertEqual(result.not_followed_back,  ["david"])
        self.assertEqual(result.mutuals, 2)

    def test_multiple_follower_files_aggregated(self):
        z = self._make_json_zip(
            {
                "followers_1.json": ["alice", "bob"],
                "followers_2.json": ["carol", "dave"],
            },
            ["alice", "eve"],
        )
        result = analyze_zip_bytes(z)
        self.assertIn("bob",   result.not_followed_back)
        self.assertIn("carol", result.not_followed_back)
        self.assertIn("dave",  result.not_followed_back)
        self.assertIn("eve",   result.not_following_back)

    def test_nested_paths_supported(self):
        z = self._make_json_zip(
            {"connections/followers_and_following/followers_1.json": ["alice"]},
            ["alice", "bob"],
        )
        result = analyze_zip_bytes(z)
        self.assertEqual(result.not_following_back, ["bob"])

    def test_html_format_supported(self):
        files = {
            "followers_1.html": html_list(["alice", "bob"]),
            "following.html":   html_list(["alice", "charlie"]),
        }
        result = analyze_zip_bytes(make_zip(files))
        self.assertIn("charlie", result.not_following_back)
        self.assertIn("bob",     result.not_followed_back)

    def test_missing_followers_file_raises(self):
        z = make_zip({"following.json": json_following(["alice"])})
        with self.assertRaises(AnalyzerError) as ctx:
            analyze_zip_bytes(z)
        self.assertIn("followers", str(ctx.exception).lower())

    def test_missing_following_file_raises(self):
        z = make_zip({"followers_1.json": json_followers(["alice"])})
        with self.assertRaises(AnalyzerError) as ctx:
            analyze_zip_bytes(z)
        self.assertIn("following", str(ctx.exception).lower())

    def test_empty_zip_raises(self):
        z = make_zip({})
        with self.assertRaises(AnalyzerError):
            analyze_zip_bytes(z)

    def test_not_a_zip_raises(self):
        with self.assertRaises(AnalyzerError) as ctx:
            analyze_zip_bytes(b"not a zip file at all")
        self.assertIn("ZIP", str(ctx.exception))

    def test_corrupted_json_raises(self):
        z = make_zip({
            "followers_1.json": "{bad",
            "following.json":   json_following(["alice"]),
        })
        with self.assertRaises(AnalyzerError):
            analyze_zip_bytes(z)

    def test_path_traversal_rejected(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            # Manually craft a path-traversal entry
            info = zipfile.ZipInfo("../../etc/passwd")
            zf.writestr(info, "root:x:0:0")
            zf.writestr("followers_1.json", json_followers(["alice"]))
            zf.writestr("following.json",   json_following(["alice"]))
        with self.assertRaises(AnalyzerError) as ctx:
            analyze_zip_bytes(buf.getvalue())
        self.assertIn("path", str(ctx.exception).lower())

    def test_deduplication(self):
        # Same username appears in two follower files — should count once
        z = self._make_json_zip(
            {
                "followers_1.json": ["alice", "bob"],
                "followers_2.json": ["alice", "carol"],
            },
            ["alice"],
        )
        result = analyze_zip_bytes(z)
        self.assertEqual(result.followers, 3)   # alice, bob, carol
        self.assertEqual(result.mutuals, 1)      # alice

    def test_case_insensitive_matching(self):
        files = {
            "followers_1.json": json_followers(["Alice", "Bob"]),
            "following.json":   json_following(["alice", "Charlie"]),
        }
        result = analyze_zip_bytes(make_zip(files))
        # alice (lowercased) should be mutual
        self.assertEqual(result.mutuals, 1)
        self.assertIn("bob",     result.not_followed_back)
        self.assertIn("charlie", result.not_following_back)

    def test_max_upload_size_enforced(self):
        # Simulate oversized raw bytes (just check the guard in analyze_zip_bytes)
        oversized = b"PK\x03\x04" + b"\x00" * (101 * 1024 * 1024)
        with self.assertRaises(AnalyzerError) as ctx:
            analyze_zip_bytes(oversized)
        self.assertIn("large", str(ctx.exception).lower())


# ══════════════════════════════════════════════════════════════
# 8. CSV escaping
# ══════════════════════════════════════════════════════════════
class TestCSVEscaping(unittest.TestCase):
    """Test the comparator's toCSV equivalent via the compare_sets result."""

    def _csv(self, result):
        """Minimal CSV builder matching comparator.js toCSV logic."""
        def esc(val):
            s = str(val)
            if any(c in s for c in ',"\r\n'):
                return '"' + s.replace('"', '""') + '"'
            return s

        rows = [["Don't Follow You Back", "You Don't Follow Back"]]
        length = max(len(result.not_following_back), len(result.not_followed_back))
        for i in range(length):
            rows.append([
                result.not_following_back[i] if i < len(result.not_following_back) else "",
                result.not_followed_back[i]  if i < len(result.not_followed_back)  else "",
            ])
        return "\r\n".join(",".join(esc(c) for c in row) for row in rows)

    def test_basic_csv(self):
        result = compare_sets({"alice", "david"}, {"alice", "bob"})
        csv = self._csv(result)
        self.assertIn("bob", csv)
        self.assertIn("david", csv)

    def test_comma_in_username_escaped(self):
        # Unlikely in practice but must not break CSV structure
        result = compare_sets(set(), {"user,name"})
        csv = self._csv(result)
        self.assertIn('"user,name"', csv)

    def test_quote_in_username_escaped(self):
        result = compare_sets(set(), {'say"hi'})
        csv = self._csv(result)
        self.assertIn('"say""hi"', csv)

    def test_unequal_list_lengths(self):
        result = compare_sets({"a", "b", "c"}, {"x"})
        csv = self._csv(result)
        lines = csv.strip().split("\r\n")
        # Header + max(3, 1) rows = 4 lines
        self.assertEqual(len(lines), 4)


# ══════════════════════════════════════════════════════════════
# 9. ZIP safety limits (entry count & decompression bomb protection)
# ══════════════════════════════════════════════════════════════
class TestZipSafetyLimits(unittest.TestCase):

    def test_too_many_entries_raises(self):
        """Archives exceeding MAX_ENTRIES must be rejected."""
        import analyzer
        orig_max = analyzer.MAX_ENTRIES
        try:
            analyzer.MAX_ENTRIES = 5
            files = {f"file_{i}.txt": "content" for i in range(10)}
            files["followers_1.json"] = json_followers(["alice"])
            files["following.json"] = json_following(["alice"])
            z = make_zip(files)
            with self.assertRaises(AnalyzerError) as ctx:
                analyze_zip_bytes(z)
            self.assertIn("too many entries", str(ctx.exception).lower())
        finally:
            analyzer.MAX_ENTRIES = orig_max

    def test_uncompressed_size_limit_raises(self):
        """Archives with uncompressed content exceeding MAX_UNCOMPRESSED must be rejected."""
        import analyzer
        orig_max = analyzer.MAX_UNCOMPRESSED
        try:
            analyzer.MAX_UNCOMPRESSED = 50  # 50 bytes threshold for testing
            files = {
                "followers_1.json": json_followers(["alice"]),
                "following.json": json_following(["alice"]),
            }
            z = make_zip(files)
            with self.assertRaises(AnalyzerError) as ctx:
                analyze_zip_bytes(z)
            self.assertIn("unsafe size", str(ctx.exception).lower())
        finally:
            analyzer.MAX_UNCOMPRESSED = orig_max


# ══════════════════════════════════════════════════════════════
# 10. Flask API endpoints & response structure
# ══════════════════════════════════════════════════════════════
class TestFlaskAPI(unittest.TestCase):

    def setUp(self):
        try:
            from app import app
            app.config["TESTING"] = True
            self.client = app.test_client()
            self.flask_available = True
        except ImportError:
            self.flask_available = False

    def test_health_endpoint(self):
        if not self.flask_available:
            self.skipTest("Flask not installed")
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("mode"), "backend")

    def test_analyze_no_file(self):
        if not self.flask_available:
            self.skipTest("Flask not installed")
        res = self.client.post("/api/analyze")
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("error", data)

    def test_analyze_invalid_extension(self):
        if not self.flask_available:
            self.skipTest("Flask not installed")
        data = {"file": (io.BytesIO(b"test"), "data.txt")}
        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertIn(".zip", res.get_json().get("error"))

    def test_analyze_valid_zip(self):
        if not self.flask_available:
            self.skipTest("Flask not installed")
        files = {
            "connections/followers_and_following/followers_1.json": json_followers(["alice", "charlie", "david"]),
            "connections/followers_and_following/following.json": json_following(["alice", "bob", "charlie"]),
        }
        zip_bytes = make_zip(files)
        data = {"file": (io.BytesIO(zip_bytes), "export.zip")}
        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()

        # Check API contract
        self.assertTrue(json_data.get("success"))
        stats = json_data.get("statistics")
        self.assertEqual(stats["followers"], 3)
        self.assertEqual(stats["following"], 3)
        self.assertEqual(stats["mutuals"], 2)
        self.assertEqual(stats["not_following_back"], 1)
        self.assertEqual(stats["not_followed_back"], 1)
        self.assertEqual(json_data["not_following_back"], ["bob"])
        self.assertEqual(json_data["not_followed_back"], ["david"])

    def test_analyze_missing_followers_file(self):
        if not self.flask_available:
            self.skipTest("Flask not installed")
        files = {"following.json": json_following(["alice"])}
        zip_bytes = make_zip(files)
        data = {"file": (io.BytesIO(zip_bytes), "export.zip")}
        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json().get("success"))
        self.assertIn("followers", res.get_json().get("error").lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
