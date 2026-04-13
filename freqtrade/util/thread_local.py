import threading

class ThreadLocalDescriptor:
    """
    Descriptor to isolate class variables per thread.
    Crucial for correctness on free-threaded Python when running multiple backtests.
    """
    def __init__(self, default_factory):
        self.default_factory = default_factory
        self.local = threading.local()

    def __get__(self, obj, objtype=None):
        if not hasattr(self.local, 'value'):
            self.local.value = self.default_factory()
        return self.local.value

    def __set__(self, obj, value):
        self.local.value = value
