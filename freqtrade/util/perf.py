import time
from contextlib import contextmanager


@contextmanager
def measure_duration():
    start = time.perf_counter()
    yield lambda: time.perf_counter() - start
