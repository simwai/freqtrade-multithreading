from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from enum import Enum
import logging
from .concurrency_env import ConcurrencyEnvironment
logger = logging.getLogger(__name__)
class ExecutionMode(str, Enum):
    THREADS = "threads"
    PROCESSES = "processes"
def select_parallel_mode(config, env: ConcurrencyEnvironment) -> tuple[ExecutionMode, int]:
    perf_cfg = config.get("performance", {})
    requested = perf_cfg.get("parallel_mode", "auto")
    workers = config.get("hyperopt_jobs") or perf_cfg.get("max_workers")
    if workers is None:
        workers = env.default_workers() if env.can_use_true_thread_parallelism() else 1
    if isinstance(workers, int) and workers <= 0:
        import os
        workers = max((os.cpu_count() or 1) + workers, 1)
    workers = max(int(workers), 1)
    if requested == "processes": return ExecutionMode.PROCESSES, workers
    if requested == "threads":
        if env.can_use_true_thread_parallelism(): return ExecutionMode.THREADS, workers
        logger.warning("parallel_mode='threads' requested but free-threaded Python is not available; falling back to processes.")
        return ExecutionMode.PROCESSES, workers
    if env.can_use_true_thread_parallelism(): return ExecutionMode.THREADS, workers
    return ExecutionMode.PROCESSES, workers
def create_executor(mode: ExecutionMode, max_workers: int):
    if mode == ExecutionMode.THREADS: return ThreadPoolExecutor(max_workers=max_workers)
    return ProcessPoolExecutor(max_workers=max_workers)
