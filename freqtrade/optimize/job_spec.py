from dataclasses import dataclass, field
from typing import Mapping, Any, Sequence, Optional

@dataclass(frozen=True)
class BacktestJobSpec:
    strategy_name: str
    parameters: Mapping[str, Any]
    pair_list: Sequence[str]
    timeframe: str
    timerange: str
    data_ref: str
    extra_context: Mapping[str, Any] = field(default_factory=dict)

@dataclass
class BacktestResult:
    job: BacktestJobSpec
    metrics: Mapping[str, float]
    trades_count: int
    raw_stats: Optional[Mapping[str, Any]] = None
