import backtrader as bt
import config
from strategies.ada_mfi import AdaMfiStrategy
from run_backtest import get_datafeed


def main():
    cerebro = bt.Cerebro()

    # Данные (можно ограничить до TRAIN_END_DATE)
    data = get_datafeed()
    cerebro.adddata(data)

    cerebro.broker.setcash(config.START_CASH)

    # Сетки параметров для оптимизации
    param_grid = dict(
        first_entry_offset=[0.03, 0.04, 0.05],
        tp_initial=[0.01, 0.015, 0.02],
        scale_in_offset=[0.03, 0.04, 0.05],
    )

    cerebro.optstrategy(AdaMfiStrategy, **param_grid)

    # Анализатор прибыли (финальное value)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    print('Запускаю оптимизацию…')
    results = cerebro.run(maxcpus=0)  # 0 = все доступные CPU

    # Выбираем стратегию с максимальным значением портфеля
    best_val, best_params = -1, None
    for res_list in results:
        strat = res_list[0]
        final_val = strat.broker.getvalue()
        if final_val > best_val:
            best_val = final_val
            best_params = strat.params

    print('=== Лучший результат ===')
    print('Итоговый портфель:', best_val)
    print('Параметры:', dict(best_params._getkwargs()))


if __name__ == '__main__':
    main() 