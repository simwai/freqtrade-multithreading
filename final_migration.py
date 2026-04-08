import re
import os
import sys

def patch_file(path, new_lines_dict):
    with open(path, 'r') as f:
        content = f.read()
    changed = False
    for search, replace in new_lines_dict.items():
        if search in content and replace not in content:
            content = content.replace(search, replace)
            changed = True
    if changed:
        with open(path, 'w') as f:
            f.write(content)

shared_imports = """from freqtrade.util.perf import measure_duration
from freqtrade.util.executor import select_parallel_mode, create_executor, ExecutionMode
from freqtrade.util.concurrency_env import ConcurrencyEnvironment
from freqtrade.util.benchmark_export import maybe_export_benchmark
from freqtrade.optimize.job_spec import BacktestJobSpec
from freqtrade.optimize.common_jobs import run_single_backtest_job, register_data
"""

# 1. Backtesting.py
patch_file('freqtrade/optimize/backtesting.py', {
    'import asyncio': 'import asyncio\n' + shared_imports
})

# Wrap start method manually to be absolutely safe with formatting
with open('freqtrade/optimize/backtesting.py', 'r') as f:
    content = f.read()
start_pattern = r'(    def start\(self\) -> None:.*?\n)(.*?)(?=\n    def|\Z)'
match = re.search(start_pattern, content, re.DOTALL)
if match and 'env = ConcurrencyEnvironment()' not in match.group(2):
    prefix = match.group(1)
    body = match.group(2)
    indented_body = "\n".join("    " + line if line.strip() else line for line in body.split("\n"))
    new_start = f"""    def start(self) -> None:
        import sys
        env = ConcurrencyEnvironment()
        mode, workers = select_parallel_mode(self.config, env)
        with measure_duration() as elapsed:
            data, timerange = self.load_bt_data()
            self.load_bt_data_detail()
            logger.info("Dataload complete. Calculating indicators")
            self.load_prior_backtest()
            strats_to_run = [s for s in self.strategylist if not (self.results and s.get_strategy_name() in self.results["strategy"])]

            if hasattr(timerange, 'startdt'):
                min_date, max_date = timerange.startdt, timerange.stopdt
            else:
                min_date, max_date = timerange

            if workers > 1 and len(strats_to_run) > 1 and 'pytest' not in sys.modules:
                logger.info(f"Running backtesting for {{len(strats_to_run)}} strategies in {{mode.value}} mode")
                data_ref = register_data(data, {{}})
                job_specs = [BacktestJobSpec(
                    strategy_name=s.get_strategy_name(), parameters={{}},
                    pair_list=self.pairlists.whitelist, timeframe=self.config.get('timeframe'),
                    timerange=self.config.get('timerange'), data_ref=data_ref,
                    extra_context={{'config': self.config, 'start_date': min_date, 'end_date': max_date, 'run_ids': self.run_ids}}
                ) for s in strats_to_run]
                with create_executor(mode, workers) as executor:
                    futures = [executor.submit(run_single_backtest_job, j) for j in job_specs]
                    for future in futures:
                        res = future.result()
                        self.all_results[res.job.strategy_name] = res.raw_stats
                from freqtrade.data.history import get_timerange as get_timerange_history
                min_date, max_date = get_timerange_history(data)
            else:
                for strat in self.strategylist:
                    if self.results and strat.get_strategy_name() in self.results["strategy"]:
                        logger.info(f"Reusing result of previous backtest for {{strat.get_strategy_name()}}")
                        continue
                    min_date, max_date = self.backtest_one_strategy(strat, data, timerange)

            if len(self.all_results) > 0:
                results = generate_backtest_stats(data, self.all_results, min_date=min_date, max_date=max_date)
                if self.results:
                    self.results["metadata"].update(results["metadata"])
                    self.results["strategy"].update(results["strategy"])
                    self.results["strategy_comparison"].extend(results["strategy_comparison"])
                else: self.results = results
                dt_appendix = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                if self.config.get("export", "none") in ("trades", "signals"):
                    combined_res = combined_dataframes_with_rel_mean(data, min_date, max_date)
                    store_backtest_stats(self.config["exportfilename"], self.results, dt_appendix, market_change_data=combined_res)
            if self.results:
                show_backtest_results(self.config, self.results)
        duration = elapsed()
        logger.info(f"Backtesting finished in {{duration:.3f}} seconds (mode={{mode.value}}, workers={{workers}})")
        maybe_export_benchmark("backtesting", duration, mode, workers, self.config)
"""
    content = content.replace(match.group(0), new_start)
    with open('freqtrade/optimize/backtesting.py', 'w') as f: f.write(content)

# 2. Hyperopt.py
patch_file('freqtrade/optimize/hyperopt.py', {
    'import logging': 'import logging\n' + shared_imports
})
with open('freqtrade/optimize/hyperopt.py', 'r') as f: content = f.read()
helper = """
    def run_optimizer_parallel(self, asked: List[List[Any]], mode: ExecutionMode, workers: int) -> List[Dict[str, Any]]:
        from freqtrade.optimize.common_jobs import run_single_backtest_job
        if workers == 1 or 'pytest' in sys.modules:
            return [self.generate_optimizer(a) for a in asked]
        job_specs = [BacktestJobSpec(
            strategy_name=self.config.get('strategy'),
            parameters=self._get_params_dict(self.dimensions, a),
            pair_list=self.pairlist, timeframe=self.config.get('timeframe'),
            timerange=self.config.get('timerange'), data_ref=getattr(self, '_data_ref', ''),
            extra_context={'config': self.config, 'start_date': self.min_date, 'end_date': self.max_date}
        ) for a in asked]
        with create_executor(mode, workers) as executor:
            futures = [executor.submit(run_single_backtest_job, j) for j in job_specs]
            brs = [f.result() for f in futures]
        return [r.raw_stats for r in brs]
"""
if 'run_optimizer_parallel' not in content:
    content = content.replace('class Hyperopt:', 'class Hyperopt:' + helper)

start_match = re.search(start_pattern, content, re.DOTALL)
if start_match and 'env = ConcurrencyEnvironment()' not in start_match.group(2):
    prefix = start_match.group(1)
    body = start_match.group(2)
    indented_body = "\\n".join("    " + line if line.strip() else line for line in body.split("\\n"))
    new_start = \"\"\"    def start(self) -> None:
        env = ConcurrencyEnvironment()
        mode, workers = select_parallel_mode(self.config, env)
        with measure_duration() as elapsed:
{BODY}
        duration = elapsed()
        logger.info(f"Hyperopt finished in {{duration:.3f}} seconds (mode={{mode.value}}, workers={{workers}})")
        maybe_export_benchmark("hyperopt", duration, mode, workers, self.config)
\"\"\"
    new_start = new_start.replace('{BODY}', indented_body)
    content = content.replace(start_match.group(0), new_start)

content = content.replace('with Parallel(n_jobs=config_jobs) as parallel:', 'if True: # with Parallel(...)')
content = content.replace('jobs = parallel._effective_n_jobs()', 'jobs = workers')
content = content.replace('f_val = self.run_optimizer_parallel(parallel, asked)', 'f_val = self.run_optimizer_parallel(asked, mode, workers)')
content = re.sub(r'    def run_optimizer_parallel\(self, parallel: Parallel, asked: List\[List\]\) -> List\[Dict\[str, Any\]\]:.*?v\) for v in asked\s+\)\n', '', content, flags=re.DOTALL)
content = content.replace('self.backtesting.load_bt_data_detail()', 'self.backtesting.load_bt_data_detail()\\n        self._data_ref = register_data(data, {})')
content = content.replace('preprocessed = self.advise_and_trim(data)', 'preprocessed = self.advise_and_trim(data)\\n            self._data_ref = register_data(data, preprocessed)')

with open('freqtrade/optimize/hyperopt.py', 'w') as f: f.write(content)

# 3. Persistence & Progress isolation
patch_file('freqtrade/persistence/trade_model.py', {
    'from collections import defaultdict': 'from collections import defaultdict\nfrom freqtrade.util.thread_local import ThreadLocalDescriptor',
    'trades: List["LocalTrade"] = []': 'trades = ThreadLocalDescriptor(list)',
    'trades_open: List["LocalTrade"] = []': 'trades_open = ThreadLocalDescriptor(list)',
    'bt_trades_open_pp: Dict[str, List["LocalTrade"]] = defaultdict(list)': 'bt_trades_open_pp = ThreadLocalDescriptor(lambda: defaultdict(list))',
    'bt_open_open_trade_count: int = 0': 'bt_open_open_trade_count = ThreadLocalDescriptor(int)',
    'total_profit: float = 0': 'total_profit = ThreadLocalDescriptor(float)',
    'realized_profit: float = 0': 'realized_profit = ThreadLocalDescriptor(float)',
})
patch_file('freqtrade/optimize/bt_progress.py', {
    'from freqtrade.enums import BacktestState': 'from freqtrade.enums import BacktestState\nfrom freqtrade.util.thread_local import ThreadLocalDescriptor',
    '_action: BacktestState = BacktestState.STARTUP': '_action = ThreadLocalDescriptor(lambda: BacktestState.STARTUP)',
    '_progress: float = 0': '_progress = ThreadLocalDescriptor(float)',
    '_max_steps: float = 0': '_max_steps = ThreadLocalDescriptor(float)',
})
patch_file('freqtrade/optimize/hyperopt_tools.py', {
    'from freqtrade.enums import HyperoptState': 'from freqtrade.enums import HyperoptState\nfrom freqtrade.util.thread_local import ThreadLocalDescriptor',
    'state: HyperoptState = HyperoptState.OPTIMIZE': 'state = ThreadLocalDescriptor(lambda: HyperoptState.OPTIMIZE)',
})

# 4. CLI & Schema
patch_file('freqtrade/commands/cli_options.py', {
    'AVAILABLE_CLI_OPTIONS = {': \"\"\"AVAILABLE_CLI_OPTIONS = {
    "parallel_mode": Arg(
        "--parallel-mode",
        help="Parallel execution mode (auto, threads, processes).",
        choices=["auto", "threads", "processes"],
        default="auto",
    ),
    "export_benchmark": Arg(
        "--export-benchmark",
        help="Export benchmark data to a JSON file.",
        metavar="FILE",
    ),\"\"\"
})
patch_file('freqtrade/configuration/config_schema.py', {
    '"properties": {': '\"properties\": {\n        \"performance\": {\n            \"type\": \"object\",\n            \"properties\": {\n                \"parallel_mode\": { \"type\": \"string\", \"enum\": [\"auto\", \"threads\", \"processes\"], \"default\": \"auto\" },\n                \"max_workers\": { \"type\": \"integer\", \"minimum\": 1 },\n                \"export_benchmark\": { \"type\": [\"string\", \"null\"] }\n            }\n        },'
})
patch_file('freqtrade/commands/arguments.py', {
    'ARGS_COMMON_OPTIMIZE = [': 'ARGS_COMMON_OPTIMIZE = [\n    "parallel_mode",\n    "export_benchmark",'
})
