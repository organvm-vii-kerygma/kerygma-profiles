"""Profile registry for per-project social identity.

Loads YAML profile files from a directory and resolves which profile
applies to a given repository name. Falls back to _default if no
specific profile matches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("kerygma.profiles")


@dataclass
class ProjectProfile:
    """A project's social identity configuration."""

    profile_id: str
    display_name: str
    organ: str | None
    repos: list[str]
    voice: dict[str, Any]
    platforms: dict[str, dict[str, str]]
    channels: list[dict[str, Any]]
    calendar_events: list[dict[str, Any]]
    rss_feed_url: str = ""


class ProfileRegistry:
    """Registry of project profiles, loaded from YAML files."""

    def __init__(self) -> None:
        self._profiles: dict[str, ProjectProfile] = {}

    def load_directory(self, profiles_dir: Path) -> int:
        """Load all *.yaml profiles from a directory. Returns count loaded."""
        count = 0
        if not profiles_dir.is_dir():
            return count
        repo_owners: dict[str, str] = {}  # repo_name -> profile_id
        for yaml_file in sorted(profiles_dir.glob("*.yaml")):
            profile = self._load_profile(yaml_file)
            if profile:
                for repo in profile.repos:
                    if repo in repo_owners:
                        logger.warning(
                            "Repo '%s' claimed by both '%s' and '%s' — first wins",
                            repo, repo_owners[repo], profile.profile_id,
                        )
                    else:
                        repo_owners[repo] = profile.profile_id
                self._profiles[profile.profile_id] = profile
                count += 1
        return count

    def _load_profile(self, path: Path) -> ProjectProfile | None:
        """Parse a single YAML profile file into a ProjectProfile."""
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load profile %s: %s", path, exc)
            return None
        if not isinstance(raw, dict) or "profile_id" not in raw:
            return None

        calendar = raw.get("calendar", {})
        calendar_events = calendar.get("events", []) if isinstance(calendar, dict) else []

        return ProjectProfile(
            profile_id=raw["profile_id"],
            display_name=raw.get("display_name", raw["profile_id"]),
            organ=raw.get("organ"),
            repos=raw.get("repos", []),
            voice=raw.get("voice", {}),
            platforms=raw.get("platforms", {}),
            channels=raw.get("channels", []),
            calendar_events=calendar_events,
            rss_feed_url=raw.get("rss_feed_url", ""),
        )

    def resolve(self, repo_name: str) -> ProjectProfile:
        """Resolve a profile for a repo name.

        Searches all profiles' repos lists for a match. Falls back to _default.
        Raises KeyError if no match and no _default profile.
        """
        for profile in self._profiles.values():
            if repo_name in profile.repos:
                return profile
        default = self._profiles.get("_default")
        if default:
            return default
        raise KeyError(
            f"No profile matches repo '{repo_name}' and no _default profile loaded"
        )

    def get(self, profile_id: str) -> ProjectProfile | None:
        """Get a profile by its ID."""
        return self._profiles.get(profile_id)

    def list_profiles(self) -> list[ProjectProfile]:
        """List all loaded profiles."""
        return list(self._profiles.values())

    @property
    def total_profiles(self) -> int:
        return len(self._profiles)
