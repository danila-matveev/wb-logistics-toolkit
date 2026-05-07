from __future__ import annotations

import json
import time
import warnings
from pathlib import Path
from typing import Any

_DEFAULT_CACHE_DIR = Path(__file__).parent / "cache"
_STALE_SECONDS = 24 * 3600


def save_cache(
    cabinet: str,
    data: dict[str, Any],
    cache_dir: Path | str | None = None,
) -> None:
    """Persist Phase 1 results to JSON for downstream phases.

    Args:
        cabinet: Cabinet name used as filename prefix.
        data: Serialisable dict (output of run_analysis).
        cache_dir: Override default cache directory (used in tests).
    """
    directory = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    cache_file = directory / f"{cabinet}_latest.json"
    cache_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_cache(
    cabinet: str,
    cache_dir: Path | str | None = None,
) -> dict[str, Any] | None:
    """Load Phase 1 cache for a cabinet.

    Emits RuntimeWarning if cache is older than 24 hours.

    Returns:
        Parsed dict, or None if the cache file does not exist.
    """
    directory = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
    cache_file = directory / f"{cabinet}_latest.json"

    if not cache_file.exists():
        return None

    age_seconds = time.time() - cache_file.stat().st_mtime
    if age_seconds > _STALE_SECONDS:
        hours = age_seconds / 3600
        warnings.warn(
            f"Cache for cabinet '{cabinet}' is stale ({hours:.1f}h old). "
            "Re-run run_analysis.py to refresh.",
            RuntimeWarning,
            stacklevel=2,
        )

    return json.loads(cache_file.read_text(encoding="utf-8"))
