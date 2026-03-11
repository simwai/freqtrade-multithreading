import pytest
from unittest.mock import MagicMock, patch
from freqtrade.util.executor import select_parallel_mode, ExecutionMode, create_executor
from freqtrade.util.concurrency_env import ConcurrencyEnvironment
from freqtrade.enums import RunMode

def test_select_parallel_mode_auto_no_free_threading():
    env = MagicMock(spec=ConcurrencyEnvironment)
    env.can_use_true_thread_parallelism.return_value = False
    env.default_workers.return_value = 4
    config = {"runmode": RunMode.HYPEROPT, "hyperopt_jobs": 4}

    mode, workers = select_parallel_mode(config, env)

    assert mode == ExecutionMode.PROCESSES
    assert workers == 4

def test_select_parallel_mode_auto_with_free_threading():
    env = MagicMock(spec=ConcurrencyEnvironment)
    env.can_use_true_thread_parallelism.return_value = True
    env.default_workers.return_value = 4
    config = {"runmode": RunMode.HYPEROPT, "hyperopt_jobs": 4}

    mode, workers = select_parallel_mode(config, env)

    assert mode == ExecutionMode.THREADS
    assert workers == 4

def test_select_parallel_mode_threads_requested_not_available():
    env = MagicMock(spec=ConcurrencyEnvironment)
    env.can_use_true_thread_parallelism.return_value = False
    env.default_workers.return_value = 4
    env.logger = MagicMock()
    config = {
        "runmode": RunMode.HYPEROPT,
        "hyperopt_jobs": 4,
        "performance": {"parallel_mode": "threads"}
    }

    mode, workers = select_parallel_mode(config, env)

    assert mode == ExecutionMode.PROCESSES
    assert workers == 4
    assert env.logger.warning.called

def test_select_parallel_mode_freqai_disables_threads():
    env = MagicMock(spec=ConcurrencyEnvironment)
    env.can_use_true_thread_parallelism.return_value = True
    env.default_workers.return_value = 4
    config = {"freqai": {"enabled": True}}

    mode, workers = select_parallel_mode(config, env)

    assert mode == ExecutionMode.PROCESSES

def test_create_executor():
    from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

    exec_threads = create_executor(ExecutionMode.THREADS, 2)
    assert isinstance(exec_threads, ThreadPoolExecutor)
    exec_threads.shutdown()

    exec_procs = create_executor(ExecutionMode.PROCESSES, 2)
    assert isinstance(exec_procs, ProcessPoolExecutor)
    exec_procs.shutdown()
