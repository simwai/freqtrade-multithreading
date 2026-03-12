import sys
from freqtrade.util.concurrency_env import is_free_threading_supported, is_gil_enabled, can_use_true_thread_parallelism

def test_concurrency_env_detection():
    supported = is_free_threading_supported()
    gil_enabled = is_gil_enabled()
    can_parallel = can_use_true_thread_parallelism()
    assert isinstance(supported, bool)
    assert isinstance(gil_enabled, bool)
    assert isinstance(can_parallel, bool)

def test_is_gil_enabled_classic():
    if not hasattr(sys, "_is_gil_enabled"):
        assert is_gil_enabled() is True
