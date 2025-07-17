import backtrader as bt
import config
from datetime import date
from indicators.mfi import MFI
import math


class HorizontalLevel(bt.Indicator):
    """Горизонтальная линия на подграфике индикатора."""

    lines = ('level',)
    params = (('value', 0.0),)
    plotinfo = dict(subplot=False)
    plotlines = dict(level=dict(ls='--', color='gray'))

    def __init__(self):
        # будем обновлять значение каждый бар в next()
        pass

    def next(self):
        self.lines.level[0] = float(self.p.value)


class TradeLevels(bt.Indicator):
    """Отрисовывает текущие уровни Entry / SL / TP на ценовом графике."""

    lines = ('entry', 'stop', 'tp')
    params = ()  # без лишних параметров, чтобы plotting не ломался

    plotinfo = dict(subplot=False, plotname='Trade levels', plotlinelabels=True)
    plotlines = dict(
        entry=dict(color='yellow', ls='--'),
        stop=dict(color='red', ls='--'),
        tp=dict(color='green', ls='--'),
    )

    def __init__(self):
        self.addminperiod(1)

    def next(self):
        s = self._owner  # ссылка на стратегию, в контексте которой создан индикатор
        if s.position:
            self.lines.entry[0] = s.cur_entry if s.cur_entry is not None else math.nan
            self.lines.stop[0] = s.cur_sl if s.cur_sl is not None else math.nan
            self.lines.tp[0] = s.cur_tp if s.cur_tp is not None else math.nan
        else:
            self.lines.entry[0] = math.nan
            self.lines.stop[0] = math.nan
            self.lines.tp[0] = math.nan


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
        # Логировка
        log_each_bar=config.LOG_EACH_BAR,
        # Параметр больше не нужен – первый вход теперь рыночный
        # expiration_days_main_order=config.EXPIRATION_DAYS_MAIN_ORDER,
    )

    def __init__(self):
        # Пытаемся использовать встроенный индикатор, иначе fallback на SimpleMFI
        try:
            self.mfi = bt.indicators.MoneyFlowIndex(self.data, period=self.p.mfi_period)
        except Exception:
            self.mfi = MFI(self.data, period=self.p.mfi_period)

        # Ссылки на ордера, чтобы удобно управлять
        self.order_main = None
        self.order_tp = None
        self.order_sl = None
        self.order_scale = None

        self.first_avg_price = None  # цена первого входа
        self.last_trade_day = None  # чтобы не больше 1 входа в день

        # текущие уровни для индикатора TradeLevels
        self.cur_entry = None
        self.cur_tp = None
        self.cur_sl = None

        self.last_exit_bar = None  # номер бара, на котором закрылась предыдущая сделка

        # --- визуализация ---
        # горизонтальная линия уровня MFI
        HorizontalLevel(
            self.mfi,
            value=self.p.mfi_entry_level,
            plotname=f'Level {self.p.mfi_entry_level}',
            plotmaster=self.mfi,
        )

        # уровни TradeLevels на основном графике
        TradeLevels(self.data)

    # ------------------------------------------------------------
    def log(self, txt):
        dt = self.data.datetime.datetime(0)
        print(f'{dt.isoformat()}  {txt}')

    # ------------------------------------------------------------
    def next(self):
        """Вызывается на каждой новой свече"""

        # --- подробный лог цен и MFI ---
        # if self.p.log_each_bar:
        #     pos = self.position.size
        #     pending = sum(1 for o in (self.order_main, self.order_scale)
        #                     if o is not None and o.status in (o.Submitted, o.Accepted))
        #     self.log(f'Pos {int(pos):>4}  Pend {pending}  Open {self.data.open[0]:.4f}  MFI {self.mfi[0]:.2f}')

        # если уже в позиции – ничего не делаем
        if self.position or self.order_main:
            return

        current_day: date = self.data.datetime.date(0)
        if self.last_trade_day == current_day:
            return  # лимит 1 вход в день

        # Условие входа: MFI <= 10
        if self.mfi[0] <= self.p.mfi_entry_level:
            self.log('ENTRY market')
            self.order_main = self.buy(size=self.p.position_size)  # рыночный ордер

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

                # уровни для отрисовки
                self.cur_entry = self.first_avg_price
                self.cur_tp = tp_price
                self.cur_sl = sl_price

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
                # Если к моменту исполнения лимитки позиция уже закрыта (например, TP сработал тем же баром),
                # игнорируем этот ордер, чтобы не открывать новую сделку поверх закрытой.
                if self.last_exit_bar is not None and len(self) == self.last_exit_bar:
                    self.log('SCALE-IN ignored – executed on same bar as exit')
                    # позиция снова открылась, закрываем её немедленно
                    if self.position:
                        self.close()
                    self._clear_order_ref(order)
                    return

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

                # обновляем уровни
                self.cur_entry = new_avg
                self.cur_tp = tp_price
                self.cur_sl = sl_price

            # 3) Тейк-профит
            elif order == self.order_tp:
                self.log(f'TAKE-PROFIT hit  PnL={order.executed.pnl:.2f}')

                if self.order_sl:
                    self.cancel(self.order_sl)
                if self.order_scale:
                    self.cancel(self.order_scale)

                # запомним, на каком баре произошёл выход
                self.last_exit_bar = len(self)
                # _reset_state вызовем в notify_trade, когда позиция действительно обнулится

            # 4) Стоп-лосс
            elif order == self.order_sl:
                self.log(f'STOP-LOSS hit  PnL={order.executed.pnl:.2f}')

                if self.order_tp:
                    self.cancel(self.order_tp)
                if self.order_scale:
                    self.cancel(self.order_scale)

                self.last_exit_bar = len(self)
                # позиция должна быть уже закрыта стоп-лоссом;
                # если всё же что-то осталось открытым, обработаем это позже в notify_trade
                # окончательная очистка будет в notify_trade

    # ------------------------------------------------------------
    def _reset_state(self):
        """Очистка всех ссылок после закрытия позиции"""
        self.order_main = None
        self.order_tp = None
        self.order_sl = None
        self.order_scale = None
        self.first_avg_price = None
        # order_main_day был убран
        self.cur_entry = None
        self.cur_tp = None
        self.cur_sl = None
        self.last_exit_bar = None

    def _clear_order_ref(self, order):
        if order == self.order_main:
            self.order_main = None
        elif order == self.order_tp:
            self.order_tp = None
        elif order == self.order_sl:
            self.order_sl = None
        elif order == self.order_scale:
            self.order_scale = None 
        # no extra reference cleanup needed

    # ------------------------------------------------------------
    def notify_trade(self, trade):
        """Финальный колбэк после закрытия позиции."""
        if trade.isclosed:
            self.log(f'TRADE closed  Gross {trade.pnl:.2f}')
            self._reset_state()

    # ------------------------------------------------------------
    def stop(self):
        """В самом конце теста: закрываем открытую позицию и отменяем все ордера."""

        # отмена висящих ордеров
        for o in (self.order_main, self.order_scale, self.order_tp, self.order_sl):
            if o is not None:
                try:
                    self.cancel(o)
                except Exception:
                    pass

        # если всё-таки осталась открытая позиция – фиксируем по последней цене
        if self.position:
            self.log('Force close open position at final bar')
            self.close() 