import json, logging, datetime
logger = logging.getLogger(__name__)
def maybe_export_benchmark(command, duration, mode, workers, config):
    path = config.get("performance", {}).get("export_benchmark")
    if not path: return
    data = {"command": command, "parallel_mode": str(mode), "workers": workers, "duration_seconds": duration, "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        with open(path, "w") as f: json.dump(data, f, indent=2)
    except Exception as e: logger.error(f"Failed to export benchmark: {e}")
