from datetime import datetime, timezone
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from pandas import DataFrame
from freqtrade.optimize.job_spec import BacktestJobSpec, BacktestResult

if TYPE_CHECKING:
    from freqtrade.optimize.backtesting import Backtesting

_DATA_REGISTRY: Dict[str, Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]] = {}

def register_data(data, processed):
    data_ref = str(id(data))
    _DATA_REGISTRY[data_ref] = (data, processed)
    return data_ref

def get_data_from_registry(data_ref):
    return _DATA_REGISTRY.get(data_ref, (None, None))

def run_single_backtest_job(job: BacktestJobSpec) -> BacktestResult:
    from freqtrade.optimize.backtesting import Backtesting
    from freqtrade.enums import BacktestState

    config = job.extra_context.get("config", {}).copy()
    config.update({
        "strategy": job.strategy_name,
        "timeframe": job.timeframe,
        "timerange": job.timerange
    })

    for path_key in ["user_data_dir", "extra_strat_path"]:
        if path := config.get(path_key):
            p = Path(path)
            if path_key == "user_data_dir": p = p / "strategies"
            if p.exists() and str(p) not in sys.path:
                sys.path.insert(0, str(p))

    _, processed = get_data_from_registry(job.data_ref)

    bt = Backtesting(config)
    bt.progress.init_step(BacktestState.BACKTEST, 0)

    if job.parameters:
        for k, v in job.parameters.items():
            if hasattr(bt.strategy, k):
                attr = getattr(bt.strategy, k)
                if hasattr(attr, 'value'): attr.value = v
                else: setattr(bt.strategy, k, v)

    if processed is None:
        data, _ = bt.load_bt_data()
        processed = bt.strategy.advise_all_indicators(data)

    backtest_start_time = datetime.now(timezone.utc)
    results = bt.backtest(
        processed=processed,
        start_date=job.extra_context.get("start_date"),
        end_date=job.extra_context.get("end_date")
    )

    results.update({
        "run_id": job.extra_context.get("run_ids", {}).get(job.strategy_name, ""),
        "backtest_start_time": int(backtest_start_time.timestamp()),
        "backtest_end_time": int(datetime.now(timezone.utc).timestamp()),
    })

    return BacktestResult(job=job, metrics={}, trades_count=results.get("total_trades", 0), raw_stats=results)
