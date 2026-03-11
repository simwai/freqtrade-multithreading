import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def maybe_export_benchmark(
    command: str, duration: float, mode: str, workers: int, config: Any
) -> None:
    path = config.get("performance", {}).get("export_benchmark")
    if not path:
        return

    now = datetime.now(timezone.utc)
    data = {
        "command": command,  # "backtesting" or "hyperopt"
        "parallel_mode": mode,
        "workers": workers,
        "duration_seconds": duration,
        "timestamp": now.isoformat(),
        "strategy": config.get("strategy"),
        "timeframe": config.get("timeframe"),
        "additional": {
            "pairs": config.get("exchange", {}).get("pair_whitelist"),
            "timerange": config.get("timerange"),
        },
    }

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Benchmark data exported to {path}")
    except Exception as e:
        logger.error(f"Failed to export benchmark data to {path}: {e}")
