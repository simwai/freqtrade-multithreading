from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence


@dataclass(frozen=True)
class BacktestJobSpec:
    strategy_name: str
    parameters: Mapping[str, Any]
    pair_list: Sequence[str]
    timeframe: str
    timerange: Optional[str]  # Changed to Optional
    data_ref: str  # key/id used to resolve data
    extra_context: Optional[Mapping[str, Any]] = None


@dataclass
class BacktestResult:
    job: BacktestJobSpec
    metrics: Mapping[str, Any]  # profit, sharpe, drawdown, etc.
    trades_count: int
    results: Any = None  # Full results dataframe or similar
