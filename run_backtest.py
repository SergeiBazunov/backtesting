import backtrader as bt
import config
from strategies.ada_mfi import AdaMfiStrategy
from pathlib import Path

# авто-загрузка истории через python-binance
import pandas as pd
from binance import Client as BinanceClient
import time
from datetime import datetime, timezone


def ensure_data():
    """Гарантируем наличие CSV; если файла нет — скачиваем свечи через REST Binance."""
    path = config.DATA_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        return path

    print(f"CSV-файл {path} не найден. Скачиваю данные из Binance …")
    try:
        client = BinanceClient()  # public endpoints

        # --- выбираем интервал Binance в зависимости от нужного таймфрейма ---
        INTERVAL_MAP = {
            1:  client.KLINE_INTERVAL_1MINUTE,
            3:  client.KLINE_INTERVAL_3MINUTE,
            5:  client.KLINE_INTERVAL_5MINUTE,
            15: client.KLINE_INTERVAL_15MINUTE,
            30: client.KLINE_INTERVAL_30MINUTE,
            60: client.KLINE_INTERVAL_1HOUR,
            120: client.KLINE_INTERVAL_2HOUR,
            240: client.KLINE_INTERVAL_4HOUR,
            360: client.KLINE_INTERVAL_6HOUR,
            480: client.KLINE_INTERVAL_8HOUR,
            720: client.KLINE_INTERVAL_12HOUR,
            1440: client.KLINE_INTERVAL_1DAY,
        }

        interval = INTERVAL_MAP.get(config.TIMEFRAME_MINUTES)
        if interval is None:
            raise ValueError(f"Unsupported TIMEFRAME_MINUTES={config.TIMEFRAME_MINUTES}. "
                             "Добавьте его в INTERVAL_MAP в run_backtest.py")

        limit = 1000  # максимум, который отдаёт API за запрос
        ms_per_candle = config.TIMEFRAME_MINUTES * 60_000

        start_ts = int(pd.to_datetime(config.DATA_START_DATE).tz_localize('UTC').timestamp() * 1000)
        now_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        total_ms = now_ts - start_ts

        all_klines = []
        current_ts = start_ts

        while current_ts < now_ts:
            klines = client.get_klines(
                symbol=config.SYMBOL,
                interval=interval,
                startTime=current_ts,
                limit=limit,
            )

            if not klines:
                break

            all_klines.extend(klines)

            # следующий запрос начнётся после последней полученной свечи
            current_ts = klines[-1][0] + ms_per_candle

            pct = (current_ts - start_ts) / total_ms * 100
            print(f"\rЗагружено: {pct:5.1f}%  свечей: {len(all_klines):>7}", end="", flush=True)

            time.sleep(0.2)  # небольшая пауза, чтобы не упереться в лимит

        print()  # перенос строки после прогресса

        if not all_klines:
            raise RuntimeError("Binance вернул пустые данные")

        columns = [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "num_trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ]
        df = pd.DataFrame(all_klines, columns=columns)
        df["open_time"] //= 1000  # переводим в секунды
        df["close_time"] //= 1000
        df.to_csv(path, index=False, header=False)
    except Exception as exc:
        print("Не получилось скачать данные:", exc)
        print("Скачайте файл вручную и положите его по указанному пути.")
        raise SystemExit(1)

    return path


def get_datafeed():
    csv_path = ensure_data()
    data = bt.feeds.GenericCSVData(
        dataname=str(csv_path),
        timeframe=bt.TimeFrame.Minutes,
        compression=config.TIMEFRAME_MINUTES,
        dtformat=2,  # Binance timestamp в миллисекундах (секунды после //=1000)
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,
        fromdate=datetime.strptime(config.BACKTEST_START_DATE, '%Y-%m-%d') if config.BACKTEST_START_DATE else None,
        todate=datetime.strptime(config.BACKTEST_END_DATE, '%Y-%m-%d') if config.BACKTEST_END_DATE else None,
    )
    return data


def main():
    cerebro = bt.Cerebro()
    cerebro.broker.set_coc(True)  # cheat-on-close – исполнение close() на текущем баре
    cerebro.broker.setcash(config.START_CASH)
    cerebro.broker.setcommission(commission=config.COMMISSION)
    cerebro.addstrategy(AdaMfiStrategy)
    cerebro.adddata(get_datafeed())

    # Анализаторы
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='dd')

    

    

    results = cerebro.run()

    # --- вывод начальных параметров ---
    print('\n===== Параметры теста =====')
    print(f"Депозит              : {config.START_CASH}")
    if config.POSITION_VALUE_USD:
        print(f"Размер позиции       : {config.POSITION_VALUE_USD}$ (конвертируется в монеты при входе)")
    else:
        print(f"Размер позиции       : {config.POSITION_SIZE}")
    print(f"MFI period           : {config.MFI_PERIOD}")
    print(f"MFI entry level      : {config.MFI_ENTRY_LEVEL}")
    print(f"TP initial           : {config.TP_INITIAL*100:.2f}%")
    print(f"SL                   : {config.SL*100:.2f}%")
    print(f"TP after scale       : {config.TP_AFTER_SCALE*100:.2f}%")
    print(f"Max entries per day  : {config.MAX_ENTRIES_PER_DAY}")
    print(f"Комиссия брокера     : {config.COMMISSION*100:.2f}%")
    print(f"Период теста         : {config.BACKTEST_START_DATE} → {config.BACKTEST_END_DATE}")
    
    # print('Начальная стоимость портфеля: %.2f' % cerebro.broker.getvalue())
    print('Конечная стоимость портфеля: %.2f' % cerebro.broker.getvalue())

    # Быстрая статистика
    trades = results[0].analyzers.trades.get_analysis()
    closed = trades.get('total', {}).get('closed', 0)
    won_total = trades.get('won', {}).get('total', 0)
    win_pnl = trades.get('won', {}).get('pnl', {}).get('total', 0.0)
    lost_total = trades.get('lost', {}).get('total', 0)
    loss_pnl = trades.get('lost', {}).get('pnl', {}).get('total', 0.0)

    net_pnl = win_pnl + loss_pnl  # loss_pnl уже отрицательный
    profitability = (won_total / closed * 100) if closed else 0.0
    profit_factor = (abs(win_pnl) / abs(loss_pnl)) if loss_pnl != 0 else float('inf')

    dd_info = results[0].analyzers.dd.get_analysis()
    max_dd_pct = dd_info.get('max', {}).get('drawdown', 0.0)

    print("\n===== Итоговая статистика =====")
    print(f"Всего закрытых сделок : {closed}")
    print(f"Плюсовых сделок       : {won_total} | Суммарная прибыль : {win_pnl:.2f}")
    print(f"Минусовых сделок      : {lost_total} | Суммарный убыток  : {loss_pnl:.2f}")
    print(f"Net PnL               : {net_pnl:.2f}")
    print(f"Процент прибыльных    : {profitability:.1f}%")
    print(f"Profit Factor         : {profit_factor:.2f}")
    print(f"Макс. просадка        : {max_dd_pct:.2f}%")

    import matplotlib.pyplot as plt
    try:
        cerebro.plot(style='candlestick')
        plt.show()
    except Exception as e:
        print('Не удалось отобразить интерактивный график:', e)
        try:
            figs = cerebro.plot(style='candlestick')
            if figs:
                figs[0][0].savefig('backtest_plot.png')
                print('График сохранён в файл backtest_plot.png')
        except Exception as _:
            pass


if __name__ == '__main__':
    main() 