import sys
import sysconfig
from unittest.mock import patch
from freqtrade.util.concurrency_env import is_free_threading_supported, is_gil_enabled, can_use_true_thread_parallelism

def test_is_free_threading_supported():
    with patch('sysconfig.get_config_var', return_value=1):
        assert is_free_threading_supported() is True
    with patch('sysconfig.get_config_var', return_value=0):
        assert is_free_threading_supported() is False
    with patch('sysconfig.get_config_var', return_value=None):
        assert is_free_threading_supported() is False

def test_is_gil_enabled():
    # Test on standard build
    if not hasattr(sys, '_is_gil_enabled'):
        assert is_gil_enabled() is True
    else:
        # On 3.13+ free-threaded build it might be True or False
        # We just check it returns a bool
        assert isinstance(is_gil_enabled(), bool)

def test_can_use_true_thread_parallelism():
    with patch('freqtrade.util.concurrency_env.is_free_threading_supported', return_value=True), \
         patch('freqtrade.util.concurrency_env.is_gil_enabled', return_value=False):
        assert can_use_true_thread_parallelism() is True

    with patch('freqtrade.util.concurrency_env.is_free_threading_supported', return_value=True), \
         patch('freqtrade.util.concurrency_env.is_gil_enabled', return_value=True):
        assert can_use_true_thread_parallelism() is False

    with patch('freqtrade.util.concurrency_env.is_free_threading_supported', return_value=False):
        assert can_use_true_thread_parallelism() is False
