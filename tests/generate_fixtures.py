"""
generate_fixtures.py — Generates synthetic Instagram ZIP archives for manual & browser testing.
"""

import json
import os
import zipfile

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
os.makedirs(FIXTURES_DIR, exist_ok=True)


def json_followers(users: list[str]) -> str:
    return json.dumps([
        {
            "string_list_data": [
                {"href": f"https://www.instagram.com/{u}/", "value": u, "timestamp": 1700000000}
            ]
        }
        for u in users
    ], indent=2)


def json_following(users: list[str]) -> str:
    return json.dumps({
        "relationships_following": [
            {
                "string_list_data": [
                    {"href": f"https://www.instagram.com/{u}/", "value": u, "timestamp": 1700000010}
                ]
            }
            for u in users
        ]
    }, indent=2)


def html_page(users: list[str]) -> str:
    links = "\n".join(f'<a href="https://www.instagram.com/{u}/">{u}</a>' for u in users)
    return f"<!DOCTYPE html><html><body><div class=\"body-text\">\n{links}\n</div></body></html>"


def main():
    # 1. Standard JSON export
    # Followers: alice, charlie, david
    # Following: alice, bob, charlie
    # Expected: Don't Follow You Back: [bob], You Don't Follow Back: [david], Mutuals: [alice, charlie]
    with zipfile.ZipFile(os.path.join(FIXTURES_DIR, "synthetic_standard_json.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("connections/followers_and_following/followers_1.json", json_followers(["alice", "charlie", "david"]))
        z.writestr("connections/followers_and_following/following.json", json_following(["alice", "bob", "charlie"]))

    # 2. Standard HTML export
    with zipfile.ZipFile(os.path.join(FIXTURES_DIR, "synthetic_standard_html.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("followers_and_following/followers_1.html", html_page(["alice", "charlie", "david"]))
        z.writestr("followers_and_following/following.html", html_page(["alice", "bob", "charlie"]))

    # 3. Multiple numbered follower files
    with zipfile.ZipFile(os.path.join(FIXTURES_DIR, "synthetic_multi_followers.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("followers_1.json", json_followers(["alice", "david"]))
        z.writestr("followers_2.json", json_followers(["charlie", "eve"]))
        z.writestr("following.json", json_following(["alice", "bob", "charlie", "frank"]))

    # 4. Missing followers file (error test)
    with zipfile.ZipFile(os.path.join(FIXTURES_DIR, "synthetic_missing_followers.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("following.json", json_following(["alice", "bob"]))

    print(f"Successfully generated synthetic test ZIP fixtures in: {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
