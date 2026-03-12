import pytest
from freqtrade.util.executor import select_parallel_mode, ExecutionMode, create_executor
from freqtrade.util.concurrency_env import ConcurrencyEnvironment
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

class MockEnv(ConcurrencyEnvironment):
    def __init__(self, can_parallel=False):
        self._can_parallel = can_parallel
    def can_use_true_thread_parallelism(self):
        return self._can_parallel
    def default_workers(self):
        return 4

def test_select_parallel_mode_auto_no_free_thread():
    config = {}
    env = MockEnv(can_parallel=False)
    mode, workers = select_parallel_mode(config, env)
    assert mode == ExecutionMode.PROCESSES
    assert workers == 1

def test_select_parallel_mode_auto_with_free_thread():
    config = {}
    env = MockEnv(can_parallel=True)
    mode, workers = select_parallel_mode(config, env)
    assert mode == ExecutionMode.THREADS
    assert workers == 4

def test_create_executor():
    exec_t = create_executor(ExecutionMode.THREADS, 2)
    assert isinstance(exec_t, ThreadPoolExecutor)
    exec_t.shutdown()

    exec_p = create_executor(ExecutionMode.PROCESSES, 2)
    assert isinstance(exec_p, ProcessPoolExecutor)
    exec_p.shutdown()
