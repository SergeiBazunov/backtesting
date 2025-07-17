import backtrader as bt
import config
from strategies.ada_mfi import AdaMfiStrategy
from pathlib import Path


def ensure_data():
    """Проверяем наличие CSV, при отсутствии пробуем скачать через binance_historical_data."""
    path = config.DATA_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        return path

    print(f"CSV-файл {path} не найден. Пытаюсь скачать данные c Binance…")
    try:
        from binance_historical_data import BinanceDataDownloader

        downloader = BinanceDataDownloader()
        # скачиваем свечи (kline) в CSV
        downloader.download_kline(
            symbol=config.SYMBOL,
            interval=f"{config.TIMEFRAME_MINUTES}m",
            start_str="2018-01-01",
            save_dir=str(path.parent),
        )
    except Exception as exc:
        print("Автоматическая загрузка не удалась:", exc)
        print("Скачайте файл самостоятельно и положите его по указанному пути.")
        raise SystemExit(1)

    if not path.exists():
        raise SystemExit("Файл не появился, прекращаю работу.")
    return path


def get_datafeed():
    csv_path = ensure_data()
    data = bt.feeds.GenericCSVData(
        dataname=str(csv_path),
        timeframe=bt.TimeFrame.Minutes,
        compression=config.TIMEFRAME_MINUTES,
        dtformat=2,  # Binance timestamp в миллисекундах
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,
        header=0,
    )
    return data


def main():
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(config.START_CASH)
    cerebro.addstrategy(AdaMfiStrategy)
    cerebro.adddata(get_datafeed())

    # Анализаторы
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='dd')

    print('Начальная стоимость портфеля: %.2f' % cerebro.broker.getvalue())
    results = cerebro.run()
    print('Конечная стоимость портфеля: %.2f' % cerebro.broker.getvalue())

    # Быстрая статистика
    trades = results[0].analyzers.trades.get_analysis()
    print('Всего закрытых сделок:', trades.total.closed)

    try:
        cerebro.plot(style='candlestick')
    except Exception:
        pass


if __name__ == '__main__':
    main() 