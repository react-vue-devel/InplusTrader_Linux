# -*- coding: utf-8 -*-
#
# Copyright 2017 Ricequant, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import six
from collections import defaultdict

from .base_account import BaseAccount
from ...events import EVENT
from ...environment import Environment
from ...utils.logger import user_system_log
from ...utils.i18n import gettext as _
from ...const import SIDE, ACCOUNT_TYPE


class StockAccount(BaseAccount):
    def __init__(self, total_cash, positions, backward_trade_set=set(), dividend_receivable=None, register_event=True):
        super(StockAccount, self).__init__(total_cash, positions, backward_trade_set, register_event)
        self._dividend_receivable = dividend_receivable if dividend_receivable else {}

    def register_event(self):
        event_bus = Environment.get_instance().event_bus
        event_bus.add_listener(EVENT.TRADE, self._on_trade)
        event_bus.add_listener(EVENT.ORDER_PENDING_NEW, self._on_order_pending_new)
        event_bus.add_listener(EVENT.ORDER_CREATION_REJECT, self._on_order_unsolicited_update)
        event_bus.add_listener(EVENT.ORDER_UNSOLICITED_UPDATE, self._on_order_unsolicited_update)
        event_bus.add_listener(EVENT.ORDER_CANCELLATION_PASS, self._on_order_unsolicited_update)
        event_bus.add_listener(EVENT.PRE_BEFORE_TRADING, self._before_trading)
        event_bus.add_listener(EVENT.SETTLEMENT, self._on_settlement)

    def get_state(self):
        return {
            'positions': {
                order_book_id: position.get_state()
                for order_book_id, position in six.iteritems(self._positions)
            },
            'frozen_cash': self._frozen_cash,
            'total_cash': self._total_cash,
            'backward_trade_set': list(self._backward_trade_set),
            'dividend_receivable': self._dividend_receivable,
        }

    def set_state(self, state):
        self._frozen_cash = state['frozen_cash']
        self._total_cash = state['total_cash']
        self._backward_trade_set = set(state['backward_trade_set'])
        self._dividend_receivable = state['dividend_receivable']
        self._positions.clear()
        for order_book_id, v in six.iteritems(state['positions']):
            position = self._positions.get_or_create(order_book_id)
            position.set_state(v)

    def fast_forward(self, orders, trades=list()):
        # ?????? Positions
        for trade in trades:
            if trade.exec_id in self._backward_trade_set:
                continue
            self._apply_trade(trade)
        # ?????? Frozen Cash
        self._frozen_cash = 0
        frozen_quantity = defaultdict(int)
        for o in orders:
            if o.is_final():
                continue
            if o.side == SIDE.BUY:
                self._frozen_cash += o.frozen_price * o.unfilled_quantity
            else:
                frozen_quantity[o.order_book_id] += o.unfilled_quantity
        for order_book_id, position in six.iteritems(self._positions):
            position.reset_frozen(frozen_quantity[order_book_id])

    def _on_trade(self, event):
        if event.account != self:
            return
        self._apply_trade(event.trade)

    def _apply_trade(self, trade):
        if trade.exec_id in self._backward_trade_set:
            return

        position = self._positions.get_or_create(trade.order_book_id)
        position.apply_trade(trade)
        self._total_cash -= trade.transaction_cost
        if trade.side == SIDE.BUY:
            self._total_cash -= trade.last_quantity * trade.last_price
            self._frozen_cash -= trade.frozen_price * trade.last_quantity
        else:
            self._total_cash += trade.last_price * trade.last_quantity
        self._backward_trade_set.add(trade.exec_id)

    def _on_order_pending_new(self, event):
        if event.account != self:
            return
        order = event.order
        position = self._positions.get_or_create(order.order_book_id)
        position.on_order_pending_new_(order)
        if order.side == SIDE.BUY:
            order_value = order.frozen_price * order.quantity
            self._frozen_cash += order_value

    def _on_order_unsolicited_update(self, event):
        if event.account != self:
            return

        order = event.order
        position = self._positions.get_or_create(order.order_book_id)
        position.on_order_cancel_(order)
        if order.side == SIDE.BUY:
            unfilled_value = order.unfilled_quantity * order.frozen_price
            self._frozen_cash -= unfilled_value

    def _before_trading(self, event):
        trading_date = Environment.get_instance().trading_dt.date()
        self._handle_dividend_payable(trading_date)
        if Environment.get_instance().config.base.handle_split:
            self._handle_split(trading_date)

    def _on_settlement(self, event):
        for position in list(self._positions.values()):
            order_book_id = position.order_book_id
            if position.is_de_listed() and position.quantity != 0:
                if Environment.get_instance().config.validator.cash_return_by_stock_delisted:
                    self._total_cash += position.market_value
                user_system_log.warn(
                    _(u"{order_book_id} is expired, close all positions by system").format(order_book_id=order_book_id)
                )
                self._positions.pop(order_book_id, None)
            elif position.quantity == 0:
                self._positions.pop(order_book_id, None)
            else:
                position.apply_settlement()

        self._backward_trade_set.clear()
        self._handle_dividend_book_closure(event.trading_dt.date())

    @property
    def type(self):
        return ACCOUNT_TYPE.STOCK

    def _handle_dividend_payable(self, trading_date):
        to_be_removed = []
        for order_book_id, dividend in six.iteritems(self._dividend_receivable):
            if dividend['payable_date'] == trading_date:
                to_be_removed.append(order_book_id)
                self._total_cash += dividend['quantity'] * dividend['dividend_per_share']
        for order_book_id in to_be_removed:
            del self._dividend_receivable[order_book_id]

    def _handle_dividend_book_closure(self, trading_date):
        for order_book_id, position in six.iteritems(self._positions):
            dividend = Environment.get_instance().data_proxy.get_dividend_by_book_date(order_book_id, trading_date)
            if dividend is None:
                continue

            dividend_per_share = dividend['dividend_cash_before_tax'] / dividend['round_lot']
            self._dividend_receivable[order_book_id] = {
                'quantity': position.quantity,
                'dividend_per_share': dividend_per_share,
                'payable_date': dividend['payable_date'].date()
            }

    def _handle_split(self, trading_date):
        for order_book_id, position in six.iteritems(self._positions):
            split = Environment.get_instance().data_proxy.get_split_by_ex_date(order_book_id, trading_date)
            if split is None:
                continue
            ratio = split['split_coefficient_to'] / split['split_coefficient_from']
            position.split_(ratio)

    @property
    def total_value(self):
        return self.market_value + self._total_cash

    @property
    def dividend_receivable(self):
        """
        [float] ????????????????????????????????????????????????????????????????????????????????????????????????
        """
        return sum(d['quantity'] * d['dividend_per_share'] for d in six.itervalues(self._dividend_receivable))
