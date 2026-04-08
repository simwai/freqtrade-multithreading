import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

def maybe_export_benchmark(command: str, duration: float, mode: Any, workers: int, config: Dict[str, Any]):
    perf_cfg = config.get("performance", {})
    path = perf_cfg.get("export_benchmark") or config.get("export_benchmark")
    if not path:
        return

    now = datetime.now(timezone.utc)
    data = {
        "command": command,
        "parallel_mode": str(mode),
        "workers": workers,
        "duration_seconds": duration,
        "timestamp": now.isoformat(),
        "strategy": config.get("strategy"),
        "timeframe": config.get("timeframe"),
        "additional": {
            "pairs": config.get("exchange", {}).get("pair_whitelist") or config.get("pairs"),
            "timerange": config.get("timerange"),
        },
    }

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Benchmark exported to {path}")
    except Exception as e:
        logger.error(f"Failed to export benchmark to {path}: {e}")
