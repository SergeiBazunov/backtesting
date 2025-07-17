import backtrader as bt
import config
from datetime import date


class AdaMfiStrategy(bt.Strategy):
    """Стратегия по описанию: одна основная заявка + один добор с переносом TP."""

    params = dict(
        # Индикатор
        mfi_period=config.MFI_PERIOD,
        mfi_entry_level=config.MFI_ENTRY_LEVEL,
        # Ордерная логика
        first_entry_offset=config.FIRST_ENTRY_OFFSET,
        tp_initial=config.TP_INITIAL,
        sl=config.SL,
        scale_in_offset=config.SCALE_IN_OFFSET,
        tp_after_scale=config.TP_AFTER_SCALE,
        # Позиция
        position_size=config.POSITION_SIZE,
        # Ограничения
        max_entries_per_day=config.MAX_ENTRIES_PER_DAY,
    )

    def __init__(self):
        # Индикатор MFI
        self.mfi = bt.indicators.MFI(self.data, period=self.p.mfi_period)

        # Ссылки на ордера, чтобы удобно управлять
        self.order_main = None
        self.order_tp = None
        self.order_sl = None
        self.order_scale = None

        self.first_avg_price = None  # цена первого входа
        self.last_trade_day = None  # чтобы не больше 1 входа в день

    # ------------------------------------------------------------
    def log(self, txt):
        dt = self.data.datetime.datetime(0)
        print(f'{dt.isoformat()}  {txt}')

    # ------------------------------------------------------------
    def next(self):
        """Вызывается на каждой новой свече"""
        if self.position or self.order_main:
            return  # уже есть позиция или стоит лимитка

        current_day: date = self.data.datetime.date(0)
        if self.last_trade_day == current_day:
            return  # лимит 1 вход в день

        # Условие входа: MFI <= 10
        if self.mfi[0] <= self.p.mfi_entry_level:
            entry_price = self.data.close[0] * (1 - self.p.first_entry_offset)
            self.log(f'Place ENTRY limit {entry_price:.4f}')
            self.order_main = self.buy(
                exectype=bt.Order.Limit,
                price=entry_price,
                size=self.p.position_size,
            )

    # ------------------------------------------------------------
    def notify_order(self, order):
        if order.status in (order.Submitted, order.Accepted):
            return  # ордер ещё не исполнен

        # Обработка отменённых / отклонённых
        if order.status in (order.Canceled, order.Margin, order.Rejected):
            self._clear_order_ref(order)
            return

        # --- Исполнение ордера ---
        if order.status == order.Completed:
            # 1) Основной вход
            if order == self.order_main:
                self.first_avg_price = order.executed.price
                self.log(f'ENTRY filled @ {self.first_avg_price:.4f}')

                # Ставим TP и SL
                tp_price = self.first_avg_price * (1 + self.p.tp_initial)
                sl_price = self.first_avg_price * (1 - self.p.sl)

                self.order_tp = self.sell(
                    exectype=bt.Order.Limit,
                    price=tp_price,
                    size=self.p.position_size,
                )
                self.order_sl = self.sell(
                    exectype=bt.Order.Stop,
                    price=sl_price,
                    size=self.p.position_size,
                )

                # Лимитка на добор
                scale_price = self.first_avg_price * (1 - self.p.scale_in_offset)
                self.order_scale = self.buy(
                    exectype=bt.Order.Limit,
                    price=scale_price,
                    size=self.p.position_size,
                )

                # отметим, что сегодня уже заходили
                self.last_trade_day = self.data.datetime.date(0)

            # 2) Добор
            elif order == self.order_scale:
                scale_fill = order.executed.price
                self.log(f'SCALE-IN filled @ {scale_fill:.4f}')

                # Отменяем старые TP/SL
                if self.order_tp:
                    self.cancel(self.order_tp)
                if self.order_sl:
                    self.cancel(self.order_sl)

                # Новый TP и SL для полного объёма
                new_avg = (self.first_avg_price + scale_fill) / 2  # две одинаковые части
                tp_price = new_avg * (1 + self.p.tp_after_scale)
                sl_price = self.first_avg_price * (1 - self.p.sl)  # стоп не двигается

                total_size = self.p.position_size * 2
                self.order_tp = self.sell(
                    exectype=bt.Order.Limit,
                    price=tp_price,
                    size=total_size,
                )
                self.order_sl = self.sell(
                    exectype=bt.Order.Stop,
                    price=sl_price,
                    size=total_size,
                )

            # 3) Тейк-профит
            elif order == self.order_tp:
                self.log(f'TAKE-PROFIT hit  PnL={order.executed.pnl:.2f}')
                self._reset_state()

            # 4) Стоп-лосс
            elif order == self.order_sl:
                self.log(f'STOP-LOSS hit  PnL={order.executed.pnl:.2f}')
                self._reset_state()

    # ------------------------------------------------------------
    def _reset_state(self):
        """Очистка всех ссылок после закрытия позиции"""
        self.order_main = None
        self.order_tp = None
        self.order_sl = None
        self.order_scale = None
        self.first_avg_price = None

    def _clear_order_ref(self, order):
        if order == self.order_main:
            self.order_main = None
        elif order == self.order_tp:
            self.order_tp = None
        elif order == self.order_sl:
            self.order_sl = None
        elif order == self.order_scale:
            self.order_scale = None 