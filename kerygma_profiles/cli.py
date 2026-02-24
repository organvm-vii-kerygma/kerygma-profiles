"""CLI for kerygma-profiles: list, show, validate profiles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kerygma_profiles.registry import ProfileRegistry
from kerygma_profiles.secrets import resolve_secret


def _default_profiles_dir() -> Path:
    """Resolve profiles directory relative to package root."""
    return Path(__file__).resolve().parent.parent / "profiles"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kerygma-profiles",
        description="Manage per-project social identity profiles",
    )
    parser.add_argument(
        "--profiles-dir", type=Path, default=None,
        help="Path to profiles directory",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List all profiles")

    show_p = sub.add_parser("show", help="Show profile details")
    show_p.add_argument("profile_id", help="Profile ID to show")

    validate_p = sub.add_parser("validate", help="Validate profiles")
    validate_p.add_argument(
        "profile_id", nargs="?",
        help="Profile ID (optional, validates all if omitted)",
    )

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    profiles_dir = args.profiles_dir or _default_profiles_dir()
    registry = ProfileRegistry()
    if profiles_dir.is_dir():
        registry.load_directory(profiles_dir)

    if args.command == "list":
        return _cmd_list(registry)
    elif args.command == "show":
        return _cmd_show(registry, args.profile_id)
    elif args.command == "validate":
        return cmd_validate(registry, args.profile_id)
    return 0


def _cmd_list(registry: ProfileRegistry) -> int:
    profiles = registry.list_profiles()
    if not profiles:
        print("No profiles found.")
        return 0
    for p in profiles:
        repos_str = ", ".join(p.repos) if p.repos else "(all)"
        print(f"  {p.profile_id}: {p.display_name} [{repos_str}]")
    return 0


def _cmd_show(registry: ProfileRegistry, profile_id: str) -> int:
    profile = registry.get(profile_id)
    if not profile:
        print(f"Profile '{profile_id}' not found.")
        return 1
    info = {
        "profile_id": profile.profile_id,
        "display_name": profile.display_name,
        "organ": profile.organ,
        "repos": profile.repos,
        "voice": profile.voice,
        "platforms": redact_secrets(profile.platforms),
        "channels": profile.channels,
        "rss_feed_url": profile.rss_feed_url,
    }
    print(json.dumps(info, indent=2))
    return 0


def redact_secrets(platforms: dict) -> dict:
    """Redact secret values in platform config for display."""
    redacted = {}
    for platform, creds in platforms.items():
        redacted[platform] = {}
        for key, value in creds.items():
            if any(s in key for s in ("token", "password", "key", "secret")):
                if value.startswith("op://") or value.startswith("env://"):
                    redacted[platform][key] = value
                elif value:
                    redacted[platform][key] = "***"
                else:
                    redacted[platform][key] = ""
            else:
                redacted[platform][key] = value
    return redacted


def cmd_validate(registry: ProfileRegistry, profile_id: str | None) -> int:
    if profile_id:
        profiles = [registry.get(profile_id)]
        profiles = [p for p in profiles if p is not None]
    else:
        profiles = registry.list_profiles()

    if not profiles:
        print("No profiles to validate.")
        return 1

    all_ok = True
    for p in profiles:
        errors: list[str] = []
        if not p.display_name:
            errors.append("missing display_name")
        if not p.platforms:
            errors.append("no platforms configured")
        for platform, creds in p.platforms.items():
            for key, value in creds.items():
                if value.startswith("op://") or value.startswith("env://"):
                    resolved = resolve_secret(value)
                    if not resolved:
                        errors.append(f"{platform}.{key}: unresolvable ({value})")
        if not p.channels:
            errors.append("no channels configured")

        if errors:
            all_ok = False
            print(f"  FAIL {p.profile_id}: {'; '.join(errors)}")
        else:
            print(f"  OK   {p.profile_id}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
