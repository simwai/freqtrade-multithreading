import logging
from typing import Any, Dict, Optional, List
from copy import deepcopy
from datetime import datetime, timezone

from freqtrade.constants import Config
from freqtrade.optimize.job_spec import BacktestJobSpec, BacktestResult

logger = logging.getLogger(__name__)

# Module-level registry for data sharing
_DATA_REGISTRY: Dict[str, Any] = {}


def register_data(key: str, data: Any) -> str:
    """
    Register data in the global registry.
    """
    _DATA_REGISTRY[key] = data
    return key


def resolve_data(key: str) -> Any:
    """
    Resolve data from the global registry.
    """
    return _DATA_REGISTRY.get(key)


def run_single_backtest_job(
    job: BacktestJobSpec,
    config: Config,
    exchange: Optional[Any] = None
) -> BacktestResult:
    """
    Run a single backtest job. Safe to call from threads/processes.
    """
    from freqtrade.optimize.backtesting import Backtesting
    from freqtrade.configuration import TimeRange
    from freqtrade.resolvers import StrategyResolver
    from freqtrade.data.history import get_timerange
    from freqtrade.optimize.hyperopt_tools import HyperoptTools
    from freqtrade.resolvers.hyperopt_resolver import HyperOptLossResolver
    from freqtrade.optimize.optimize_reports import generate_strategy_stats
    from freqtrade.misc import deep_merge_dicts
    from freqtrade.optimize.backtest_caching import get_strategy_run_id
    import joblib

    job_config = deepcopy(config)
    job_config['strategy'] = job.strategy_name
    if job.timerange:
        job_config['timerange'] = job.timerange
    if job.timeframe:
        job_config['timeframe'] = job.timeframe
    if job.pair_list:
        job_config['exchange']['pair_whitelist'] = job.pair_list

    # Initialize Backtesting instance
    bt = Backtesting(job_config, exchange=exchange)

    # Resolve data
    data = resolve_data(job.data_ref)

    # If data is a string, it might be a path to a pickle file (Hyperopt optimization)
    if isinstance(data, str) and data.endswith('.pkl'):
        # For Hyperopt, we use joblib to load the data, potentially with mmap
        data = joblib.load(data, mmap_mode="r")

    if data is None:
        # Load data if not resolved (e.g. in PROCESS mode and not using pickle)
        data, timerange = bt.load_bt_data()
    else:
        timerange = TimeRange.parse_timerange(job.timerange)

    # Apply parameters
    strat = bt.strategylist[0]
    bt._set_strategy(strat)

    is_hyperopt = job.extra_context and job.extra_context.get('is_hyperopt')

    if is_hyperopt:
        params_dict = job.parameters
        # Similar logic to Hyperopt.generate_optimizer
        if HyperoptTools.has_space(job_config, "buy"):
            for attr_name, attr in strat.enumerate_parameters("buy"):
                if attr.optimize:
                    attr.value = params_dict[attr_name]
        if HyperoptTools.has_space(job_config, "sell"):
            for attr_name, attr in strat.enumerate_parameters("sell"):
                if attr.optimize:
                    attr.value = params_dict[attr_name]
        if HyperoptTools.has_space(job_config, "protection"):
            for attr_name, attr in strat.enumerate_parameters("protection"):
                if attr.optimize:
                    attr.value = params_dict[attr_name]

        if HyperoptTools.has_space(job_config, "roi"):
            # We need the custom_hyperopt instance or just generate it here
            from freqtrade.optimize.hyperopt_auto import HyperOptAuto
            custom_hyperopt = HyperOptAuto(job_config)
            strat.minimal_roi = custom_hyperopt.generate_roi_table(params_dict)

        if HyperoptTools.has_space(job_config, "stoploss"):
            strat.stoploss = params_dict["stoploss"]

        if HyperoptTools.has_space(job_config, "trailing"):
            from freqtrade.optimize.hyperopt_auto import HyperOptAuto
            custom_hyperopt = HyperOptAuto(job_config)
            d = custom_hyperopt.generate_trailing_params(params_dict)
            strat.trailing_stop = d["trailing_stop"]
            strat.trailing_stop_positive = d["trailing_stop_positive"]
            strat.trailing_stop_positive_offset = d["trailing_stop_positive_offset"]
            strat.trailing_only_offset_is_reached = d["trailing_only_offset_is_reached"]

        if HyperoptTools.has_space(job_config, "trades"):
            updated_max_open_trades = (
                int(params_dict["max_open_trades"])
                if (params_dict["max_open_trades"] != -1 and params_dict["max_open_trades"] != 0)
                else float("inf")
            )
            strat.max_open_trades = updated_max_open_trades
            job_config["max_open_trades"] = updated_max_open_trades

        # Handle analyze_per_epoch if needed
        if job.extra_context.get('analyze_per_epoch'):
            data = strat.advise_all_indicators(data)
            # We don't trim here as Backtesting.backtest will do it

    # Run backtest
    backtest_start_time = datetime.now(timezone.utc)

    # We need min_date and max_date for backtest call
    # They should be derived from data after trimming startup candles
    from freqtrade.data.converter import trim_dataframes
    trimmed_tmp = trim_dataframes(data, timerange, bt.required_startup)
    min_date, max_date = get_timerange(trimmed_tmp)

    bt_results = bt.backtest(
        processed=data, start_date=min_date, end_date=max_date
    )
    backtest_end_time = datetime.now(timezone.utc)
    bt_results.update(
        {
            "run_id": get_strategy_run_id(strat),
            "backtest_start_time": int(backtest_start_time.timestamp()),
            "backtest_end_time": int(backtest_end_time.timestamp()),
        }
    )

    if is_hyperopt:
        # Calculate loss and other hyperopt specific metrics
        market_change = job.extra_context.get('market_change', 0.0)
        strat_stats = generate_strategy_stats(
            bt.pairlists.whitelist,
            strat.get_strategy_name(),
            bt_results,
            min_date,
            max_date,
            market_change=market_change,
            is_hyperopt=True,
        )

        custom_hyperoptloss = HyperOptLossResolver.load_hyperoptloss(job_config)

        MAX_LOSS = 100000
        trade_count = strat_stats["total_trades"]
        loss = MAX_LOSS
        if trade_count >= job_config.get("hyperopt_min_trades", 1):
            loss = custom_hyperoptloss.hyperopt_loss_function(
                results=bt_results["results"],
                trade_count=trade_count,
                min_date=min_date,
                max_date=max_date,
                config=job_config,
                processed=data,
                backtest_stats=strat_stats,
            )

        # Prepare params_details and params_not_optimized
        from freqtrade.optimize.hyperopt_auto import HyperOptAuto
        custom_hyperopt = HyperOptAuto(job_config)
        # Note: This is slightly simplified as we don't have the full Hyperopt instance here
        # but params_dict already has what's needed.

        results_explanation = HyperoptTools.format_results_explanation_string(
            strat_stats, job_config["stake_currency"]
        )

        not_optimized = strat.get_no_optimize_params()
        # simplified not_optimized details

        return BacktestResult(
            job=job,
            metrics={
                "loss": loss,
                "params_dict": params_dict,
                "results_metrics": strat_stats,
                "results_explanation": results_explanation,
                "total_profit": strat_stats["profit_total"],
            },
            trades_count=trade_count
        )

    return BacktestResult(
        job=job,
        metrics=bt_results,
        trades_count=len(bt_results['results']) if 'results' in bt_results else 0,
        results={
            'all_results': {job.strategy_name: bt_results},
            'processed_dfs': bt.processed_dfs,
            'rejected_df': bt.rejected_df,
        }
    )
