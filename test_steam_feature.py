"""
Smoke tests for the Steam library -> priority list feature.
Run: python test_steam_feature.py

Set STEAM_API_KEY and STEAM_ID64 environment variables (both from the same account)
to additionally run the live Steam Web API test.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from exceptions import SteamException
from steam import (
    API_KEY_URL,
    fetch_library,
    match_games,
    normalize_game_name,
    _parse_library_api,
)


def test_normalize() -> None:
    assert normalize_game_name("The Sims™ 4") == "sims 4"
    assert normalize_game_name("WARFRAME®") == "warframe"
    assert normalize_game_name("PUBG: BATTLEGROUNDS!") == "pubg battlegrounds"
    assert normalize_game_name("  Dead   by Daylight ") == "dead by daylight"
    assert normalize_game_name("The Elder Scrolls V: Skyrim") == "elder scrolls v skyrim"
    print("test_normalize OK")


def test_match() -> None:
    twitch_games = [
        "The Sims™ 4",
        "Warframe",
        "Counter-Strike 2",
        "PUBG: BATTLEGROUNDS",
        "Dead by Daylight",
    ]
    steam_games = [
        "The Sims 4",  # exact after normalization
        "WARFRAME®",  # exact after normalization
        "PUBG: BATTLEGROUNDS",  # exact
        "Counter-Strike 2: a made up sequel",  # containment, unique -> match
        "Dota 2",  # not a Twitch campaign game -> no match
        "Dead",  # unique containment -> match
    ]
    matched = match_games(steam_games, twitch_games)
    assert matched == [
        "The Sims™ 4",
        "Warframe",
        "Counter-Strike 2",
        "PUBG: BATTLEGROUNDS",
        "Dead by Daylight",
    ], matched
    # empty inputs
    assert match_games([], twitch_games) == []
    assert match_games(steam_games, []) == []
    # duplicates in twitch games are handled
    assert match_games(["Warframe"], ["Warframe", "Warframe"]) == ["Warframe"]
    # ambiguous containment -> no match
    assert match_games(["Dota"], ["Dota 2", "Dota Underlords"]) == []
    print("test_match OK")


def test_parse_api() -> None:
    data = {
        "response": {
            "game_count": 2,
            "games": [
                {"appid": 570, "name": "Dota 2"},
                {"appid": 730},  # no name -> skipped
                {"appid": 730, "name": "Counter-Strike 2"},
            ],
        }
    }
    assert _parse_library_api(data) == ["Dota 2", "Counter-Strike 2"]
    assert _parse_library_api({}) == []
    print("test_parse_api OK")


def test_fetch_library_errors() -> None:
    import asyncio

    import aiohttp

    class FakeSettings:
        def __init__(self, steam_id: str, steam_api_key: str):
            self.steam_id = steam_id
            self.steam_api_key = steam_api_key

    async def run() -> None:
        async with aiohttp.ClientSession() as session:
            # no Steam ID
            try:
                await fetch_library(session, FakeSettings("", ""))
            except SteamException as exc:
                assert "Steam ID" in str(exc)
            else:
                raise AssertionError("expected SteamException for an empty Steam ID")
            # no API key
            try:
                await fetch_library(session, FakeSettings("76561198000000000", ""))
            except SteamException as exc:
                assert API_KEY_URL in str(exc)
            else:
                raise AssertionError("expected SteamException for an empty API key")
            # invalid API key -> 403 -> helpful error
            try:
                await fetch_library(
                    session, FakeSettings("76561198000000000", "INVALID_KEY_123")
                )
            except SteamException as exc:
                assert "API key" in str(exc)
            else:
                raise AssertionError("expected SteamException for an invalid API key")

    asyncio.run(run())
    print("test_fetch_library_errors OK")


def test_fetch_library_live() -> None:
    """
    Live test against the Steam Web API - requires STEAM_API_KEY and STEAM_ID64
    (both belonging to the same account).
    """
    api_key = os.environ.get("STEAM_API_KEY")
    steam_id = os.environ.get("STEAM_ID64")
    if not api_key or not steam_id:
        print("test_fetch_library_live SKIPPED (no STEAM_API_KEY / STEAM_ID64 set)")
        return
    import asyncio

    import aiohttp

    class FakeSettings:
        steam_id = steam_id
        steam_api_key = api_key

    async def run() -> None:
        async with aiohttp.ClientSession() as session:
            library = await fetch_library(session, FakeSettings())
        assert isinstance(library, list) and len(library) > 0
        assert all(isinstance(name, str) and name for name in library)
        print(f"test_fetch_library_live OK ({len(library)} games, e.g. {library[:3]})")

    asyncio.run(run())


def test_translations() -> None:
    from translate import _

    for key in (
        "steam_id", "steam_api_key", "import_button", "import_started", "import_done", "import_none"
    ):
        value = _("gui", "settings", "steam", key)
        assert value and isinstance(value, str), key
    formatted = _("gui", "settings", "steam", "import_done").format(matched=3, added=2)
    assert "3" in formatted and "2" in formatted
    print("test_translations OK")


def test_settings_merge() -> None:
    from settings import default_settings

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "settings.json")
        # simulate a pre-existing settings file without the new keys
        path.write_text(json.dumps({"priority": ["Warframe"]}), encoding="utf8")
        from utils import json_load

        loaded = json_load(path, default_settings)
        assert loaded["priority"] == ["Warframe"]
        assert loaded["steam_id"] == ""
        assert loaded["steam_api_key"] == ""
        assert loaded["priority_mode"] is default_settings["priority_mode"]
    print("test_settings_merge OK")


if __name__ == "__main__":
    test_normalize()
    test_match()
    test_parse_api()
    test_fetch_library_errors()
    test_fetch_library_live()
    test_translations()
    test_settings_merge()
    print("ALL TESTS PASSED")
