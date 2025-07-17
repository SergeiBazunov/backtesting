import itertools, multiprocessing, os
import backtrader as bt
from datetime import datetime
import config
from run_backtest import get_datafeed
from strategies.ada_mfi import AdaMfiStrategy

# --- сколько процессов использовать (None или 0 = все доступные) ---
CPUS = 10

# --- сетка параметров для grid-поиска ---
param_grid = dict(
    tp_initial=[0.015, 0.02, 0.025],   # 1.5 – 2.5 %
    sl=[0.03, 0.04, 0.05],             # 3 – 5 %
    mfi_entry_level=[7, 10, 12],
    mfi_period=[8, 10, 14],
    scale_in_offset=[0.04, 0.06],
    tp_after_scale=[0.001, 0.005],
    position_value_usd=[config.POSITION_VALUE_USD],
)


def run_combo(params: dict) -> tuple[float, dict]:
    """Запускает один бэктест с заданными params; возвращает (final_value, params)"""
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(config.START_CASH)
    cerebro.broker.setcommission(commission=config.COMMISSION)

    # Данные только до TRAIN_END_DATE
    data = get_datafeed()
    end_date = datetime.strptime(config.TRAIN_END_DATE, "%Y-%m-%d")
    data._todate = end_date
    cerebro.adddata(data)

    cerebro.addstrategy(AdaMfiStrategy, **params)
    cerebro.run()
    return cerebro.broker.getvalue(), params


def main():
    # формируем список всех комбинаций
    names = list(param_grid.keys())
    combos = [dict(zip(names, vals)) for vals in itertools.product(*param_grid.values())]
    use_cpus = CPUS or multiprocessing.cpu_count()
    print(f"Комбинаций: {len(combos)} | Ядер: {use_cpus}")

    with multiprocessing.Pool(processes=use_cpus) as pool:
        results = pool.map(run_combo, combos)

    best_val, best_params = max(results, key=lambda x: x[0])

    print("\n=== ЛУЧШИЙ РЕЗУЛЬТАТ (train) ===")
    print(f"Финальная стоимость портфеля: {best_val:.2f}")
    print("Параметры:")
    for k, v in best_params.items():
        print(f"  {k} = {v}")


if __name__ == "__main__":
    # Windows requires 'spawn' start method; ensure it to avoid RuntimeError when optimize.py imported elsewhere
    if os.name == "nt":
        multiprocessing.set_start_method("spawn", force=True)
    main() 