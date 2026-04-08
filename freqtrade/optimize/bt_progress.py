from freqtrade.enums import BacktestState
from freqtrade.util.thread_local import ThreadLocalDescriptor


class BTProgress:
    _action = ThreadLocalDescriptor(lambda: BacktestState.STARTUP)
    _progress = ThreadLocalDescriptor(float)
    _max_steps = ThreadLocalDescriptor(float)

    def __init__(self):
        pass

    def init_step(self, action: BacktestState, max_steps: float):
        self._action = action
        self._max_steps = max_steps
        self._progress = 0

    def set_new_value(self, new_value: float):
        self._progress = new_value

    def increment(self):
        self._progress += 1

    @property
    def progress(self):
        """
        Get progress as ratio, capped to be between 0 and 1 (to avoid small calculation errors).
        """
        return max(
            min(round(self._progress / self._max_steps, 5) if self._max_steps > 0 else 0, 1), 0
        )

    @property
    def action(self):
        return str(self._action)
