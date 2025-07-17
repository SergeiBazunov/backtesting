from pathlib import Path

# Общие параметры
SYMBOL = 'ADAUSDT'
TIMEFRAME_MINUTES = 30

# Размер позиции (фиксированное количество монет)
POSITION_SIZE = 100  # fallback, если POSITION_VALUE_USD = 0

# Если хотите задавать размер позиции в долларах (фиксированная стоимость сделки),
# укажите сумму ниже. Если 0 – будет использоваться POSITION_SIZE.
POSITION_VALUE_USD = 50

# При переводе доллара в количество монет округляем до указанного количества знаков.
POSITION_ROUND_DIGITS = 2

# Индикатор MFI
MFI_PERIOD = 10
MFI_ENTRY_LEVEL = 10  # вход, когда MFI <= 10

# Риск/прибыль первоначального входа
FIRST_ENTRY_OFFSET = 0.04   # лимит-ордер на -4 % от close
TP_INITIAL = 0.015          # тейк-профит +1.5 %
SL = 0.09                   # стоп-лосс -9 %

# Добор (только один)
SCALE_IN_OFFSET = 0.04      # ещё -4 % от цены первого входа
TP_AFTER_SCALE = 0.001      # +0.10 % от новой средней цены

# Прочее
MAX_ENTRIES_PER_DAY = 1
START_CASH = 500

# Комиссия брокера (доля от объёма)
COMMISSION = 0.001  # 0.1 %

# Логировать каждый бар (цена открытия + MFI)
LOG_EACH_BAR = True

# откуда начинать загрузку исторических данных при первом запуске
DATA_START_DATE = '2018-01-01'  # ISO-формат YYYY-MM-DD

# Диапазон для самого бэктеста (если None – используем весь доступный)
BACKTEST_START_DATE = '2023-01-01'  # например '2024-05-01'
BACKTEST_END_DATE = '2025-12-31'   # например '2024-07-01'

# Пути к данным
DATA_DIR = Path(__file__).parent / 'data'
DATA_FILE = DATA_DIR / f'{SYMBOL}-{TIMEFRAME_MINUTES}m.csv'

# Для разделения истории (оптимизация / проверка)
TRAIN_END_DATE = '2022-12-31' 

EXPIRATION_DAYS_MAIN_ORDER = 1 