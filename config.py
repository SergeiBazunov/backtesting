from pathlib import Path

# Общие параметры
SYMBOL = 'ADAUSDT'
TIMEFRAME_MINUTES = 30

# Размер позиции (фиксированное количество монет)
POSITION_SIZE = 100  # исправьте при необходимости

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
START_CASH = 10_000

# Пути к данным
DATA_DIR = Path(__file__).parent / 'data'
DATA_FILE = DATA_DIR / f'{SYMBOL}-{TIMEFRAME_MINUTES}m.csv'

# Для разделения истории (оптимизация / проверка)
TRAIN_END_DATE = '2023-01-01' 