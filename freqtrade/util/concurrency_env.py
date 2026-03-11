import logging
import os
import sys
import sysconfig

logger = logging.getLogger(__name__)


def is_free_threading_supported() -> bool:
    # Build-time capability: free-threaded build exposes Py_GIL_DISABLED
    flag = sysconfig.get_config_var("Py_GIL_DISABLED")
    return bool(flag)


def is_gil_enabled() -> bool:
    # Runtime GIL status (3.13+/3.14+ free-threaded builds)
    check = getattr(sys, "_is_gil_enabled", None)
    if callable(check):
        return check()
    # On classic builds we assume the GIL exists and is enabled
    return True


def can_use_true_thread_parallelism() -> bool:
    return is_free_threading_supported() and not is_gil_enabled()


class ConcurrencyEnvironment:
    def __init__(self, logger_=logger):
        self.logger = logger_

    def default_workers(self) -> int:
        # Keep current behavior based on CPU count
        return os.cpu_count() or 1

    def can_use_true_thread_parallelism(self) -> bool:
        return can_use_true_thread_parallelism()
