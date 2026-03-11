from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from enum import Enum
from typing import Any, Tuple

from freqtrade.util.concurrency_env import ConcurrencyEnvironment


class ExecutionMode(str, Enum):
    THREADS = "threads"
    PROCESSES = "processes"


def is_thread_mode_allowed_for_config(config: Any) -> bool:
    # Example: disable threads when FreqAI is enabled
    if config.get("freqai", {}).get("enabled", False):
        return False
    return True


def select_parallel_mode(config: Any, env: ConcurrencyEnvironment) -> Tuple[ExecutionMode, int]:
    from freqtrade.enums import RunMode
    perf_cfg = config.get("performance", {})
    requested = perf_cfg.get("parallel_mode", "auto")

    # Default workers: hyperopt uses all cores, backtesting defaults to 1 (sequential)
    # unless explicitly specified via max_workers or user_workers.
    runmode = config.get("runmode")
    if runmode == RunMode.HYPEROPT or str(runmode) == "hyperopt":
        default_workers = env.default_workers()
    else:
        default_workers = 1

    workers = perf_cfg.get("max_workers") or config.get("user_workers") or config.get("hyperopt_jobs") or default_workers

    if requested == "processes":
        return ExecutionMode.PROCESSES, workers

    if requested == "threads":
        if env.can_use_true_thread_parallelism() and is_thread_mode_allowed_for_config(config):
            return ExecutionMode.THREADS, workers

        reason = "free-threaded Python is not available"
        if not is_thread_mode_allowed_for_config(config):
            reason = "it is not allowed for the current configuration (e.g. FreqAI is enabled)"

        env.logger.warning(
            f"parallel_mode='threads' requested but {reason}; "
            "falling back to processes."
        )
        return ExecutionMode.PROCESSES, workers

    # auto mode:
    # On free-threaded Python, use threads.
    # On standard CPython, use processes if workers > 1, else sequential.
    if env.can_use_true_thread_parallelism() and is_thread_mode_allowed_for_config(config):
        return ExecutionMode.THREADS, workers

    return ExecutionMode.PROCESSES, workers


def create_executor(mode: ExecutionMode, max_workers: int):
    if mode == ExecutionMode.THREADS:
        return ThreadPoolExecutor(max_workers=max_workers)
    return ProcessPoolExecutor(max_workers=max_workers)
