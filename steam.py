from __future__ import annotations

import json
import logging
import re
from collections import abc
from typing import TYPE_CHECKING

from exceptions import SteamException

if TYPE_CHECKING:
    import aiohttp
    from settings import Settings


logger = logging.getLogger("TwitchDrops.steam")

STEAM_ID64_PATTERN = re.compile(r"^\d{17}$")
# games like "The Sims™ 4" or "WARFRAME®" carry trademark symbols that Twitch doesn't
_TRADEMARK_PATTERN = re.compile(r"[™®©]")
_NON_WORD_PATTERN = re.compile(r"[^\w\s]")
_SPACES_PATTERN = re.compile(r"\s+")

# NOTE: the old anonymous community games list endpoint (games?xml=1)
# redirects to the login page now, so a Steam Web API key is required.
# Free keys are available at: https://store.steampowered.com/dev/apikey
API_KEY_URL = "https://store.steampowered.com/dev/apikey"


def normalize_game_name(name: str) -> str:
    """
    Normalize a game name for matching between Steam and Twitch.

    Casefolds the name, drops trademark symbols, punctuation and standalone articles,
    then collapses whitespace, e.g. "The Sims™ 4:" -> "sims 4".
    """
    name = _TRADEMARK_PATTERN.sub("", name.casefold())
    name = _NON_WORD_PATTERN.sub(" ", name)
    name = re.sub(r"\bthe\b", "", name)
    return _SPACES_PATTERN.sub(" ", name).strip()


def _unique_names(names: abc.Iterable[str]) -> list[str]:
    return list(dict.fromkeys(name.strip() for name in names if name.strip()))


def match_games(
    steam_games: abc.Iterable[str], twitch_games: abc.Iterable[str]
) -> list[str]:
    """
    Match Steam library game names against Twitch campaign game names.

    Returns the matched Twitch game names, preserving their original order.
    Matching is done on normalized names; if an exact match isn't found,
    a containment match is accepted, but only when it's unambiguous.
    """
    twitch_names: list[str] = _unique_names(twitch_games)
    by_normalized: dict[str, str] = {}
    for name in twitch_names:
        by_normalized.setdefault(normalize_game_name(name), name)
    matched: set[str] = set()
    for steam_name in _unique_names(steam_games):
        normalized = normalize_game_name(steam_name)
        if not normalized:
            continue
        exact = by_normalized.get(normalized)
        if exact is not None:
            matched.add(exact)
            continue
        # fallback: containment matching, e.g. "Dota 2" vs "Dota 2: Dead Reckoning"
        # only accept it when a single candidate matches, to avoid false positives
        candidates = {
            name
            for name in twitch_names
            if (
                len(normalized) >= 4
                and (candidate := normalize_game_name(name))
                and (normalized in candidate or candidate in normalized)
            )
        }
        if len(candidates) == 1:
            matched.add(candidates.pop())
    return [name for name in twitch_names if name in matched]


def _parse_library_api(data: dict) -> list[str]:
    """
    Parse the game names out of the GetOwnedGames Web API response.
    """
    return _unique_names(
        game["name"] for game in data.get("response", {}).get("games", []) if "name" in game
    )


async def _api_get_json(
    session: aiohttp.ClientSession, path: str, params: dict[str, str]
) -> dict:
    """
    Perform a GET request against the Steam Web API, with key error handling.
    """
    async with session.get(f"https://api.steampowered.com/{path}", params=params) as response:
        if response.status in (401, 403):
            raise SteamException(
                "Steam rejected the Web API key - make sure it's valid "
                f"(get a new one at {API_KEY_URL})"
            )
        if response.status != 200:
            raise SteamException(f"Steam Web API returned HTTP status {response.status}")
        try:
            return json.loads(await response.text())
        except json.JSONDecodeError as exc:
            raise SteamException("Steam Web API returned a malformed response") from exc


async def _resolve_vanity_url(
    session: aiohttp.ClientSession, api_key: str, vanity: str
) -> str:
    data = await _api_get_json(
        session,
        "ISteamUser/ResolveVanityURL/v1/",
        {"key": api_key, "vanityurl": vanity},
    )
    result = data.get("response", {})
    if result.get("success") != 1 or "steamid" not in result:
        raise SteamException(f"Failed to resolve Steam vanity URL: '{vanity}'")
    return result["steamid"]


async def fetch_library(session: aiohttp.ClientSession, settings: Settings) -> list[str]:
    """
    Fetch the user's Steam library via the official Steam Web API
    and return the list of owned game names.
    """
    steam_id: str = settings.steam_id.strip()
    if not steam_id:
        raise SteamException("No Steam ID set - fill in the Steam ID field first")
    api_key: str = settings.steam_api_key.strip()
    if not api_key:
        raise SteamException(
            "No Steam Web API key set - get a free key at " + API_KEY_URL
        )
    if not STEAM_ID64_PATTERN.match(steam_id):
        steam_id = await _resolve_vanity_url(session, api_key, steam_id)
    data = await _api_get_json(
        session,
        "IPlayerService/GetOwnedGames/v1/",
        {
            "key": api_key,
            "steamid": steam_id,
            "include_appinfo": "true",
            "include_played_free_games": "true",
        },
    )
    library = _parse_library_api(data)
    if not library:
        raise SteamException(
            "Steam returned an empty library - check that the Steam ID "
            "belongs to the account the API key was created for, "
            "and that its game details are set to public"
        )
    return library
