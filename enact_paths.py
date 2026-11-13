"""Locate the sibling ``enact-agent`` checkout.

The overlay CSV is the only source of the real ``compiled_in_enact`` flags — the
workspace copy of the inventory claims every tool is compiled in. So the report
generator and the registry generator both need a checkout of ``enact-agent``.

Resolution order:

1. ``ENACT_AGENT_DIR`` — explicit override (absolute or relative to the cwd).
2. ``enact-agent`` as a sibling of this repository (the standard workspace
   layout: ``workspace/enact-tools`` + ``workspace/enact-agent``).
3. ``enact-agent`` inside this repository.
4. ``enact-agent`` in the current working directory or its parent.

Nothing here is machine-specific: the paths below are derived, never written
down.
"""
from __future__ import annotations

import os
from pathlib import Path

OVERLAY_RELATIVE = Path("overlays") / "enact" / "zeroclaw-tools-operations.csv"
REPO_ROOT = Path(__file__).resolve().parent


def candidate_dirs() -> list[Path]:
    """Every place a checkout of enact-agent might live, in priority order."""
    candidates: list[Path] = []

    env = os.environ.get("ENACT_AGENT_DIR")
    if env:
        candidates.append(Path(env).expanduser())

    candidates.extend(
        [
            REPO_ROOT.parent / "enact-agent",
            REPO_ROOT / "enact-agent",
            Path.cwd() / "enact-agent",
            Path.cwd().parent / "enact-agent",
        ]
    )
    return candidates


def enact_agent_dir() -> Path | None:
    """The enact-agent checkout, or None when it cannot be found."""
    seen: set[Path] = set()
    for candidate in candidate_dirs():
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if (resolved / OVERLAY_RELATIVE).is_file():
            return resolved
    return None


def overlay_csv() -> Path:
    """Path to the overlay operations CSV — the real compiled_in_enact flags."""
    found = enact_agent_dir()
    if found is None:
        tried = ", ".join(str(c) for c in candidate_dirs())
        raise FileNotFoundError(
            "Could not find an enact-agent checkout carrying "
            f"{OVERLAY_RELATIVE}. Set ENACT_AGENT_DIR to the checkout root. Tried: {tried}"
        )
    return found / OVERLAY_RELATIVE


def overlay_csv_optional() -> Path | None:
    """Same as :func:`overlay_csv`, but None instead of an exception."""
    found = enact_agent_dir()
    return found / OVERLAY_RELATIVE if found else None


if __name__ == "__main__":
    print(overlay_csv())
