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

import time

from ..const import ORDER_STATUS, ORDER_TYPE, SIDE, POSITION_EFFECT
from ..utils import id_gen
from ..utils.repr import property_repr, properties
from ..utils.logger import user_system_log


class Order(object):

    order_id_gen = id_gen(int(time.time()))

    __repr__ = property_repr

    def __init__(self):
        self._order_id = None
        self._calendar_dt = None
        self._trading_dt = None
        self._quantity = None
        self._order_book_id = None
        self._side = None
        self._position_effect = None
        self._message = None
        self._filled_quantity = None
        self._status = None
        self._frozen_price = None
        self._type = None
        self._avg_price = None
        self._transaction_cost = None

    @staticmethod
    def _enum_to_str(v):
        return v.name

    @staticmethod
    def _str_to_enum(enum_class, s):
        return enum_class.__members__[s]

    def get_state(self):
        return {
            'order_id': self._order_id,
            'calendar_dt': self._calendar_dt,
            'trading_dt': self._trading_dt,
            'order_book_id': self._order_book_id,
            'quantity': self._quantity,
            'side': self._enum_to_str(self._side),
            'position_effect': self._enum_to_str(self._position_effect) if self._position_effect is not None else None,
            'message': self._message,
            'filled_quantity': self._filled_quantity,
            'status': self._enum_to_str(self._status),
            'frozen_price': self._frozen_price,
            'type': self._enum_to_str(self._type),
        }

    def set_state(self, d):
        self._order_id = d['order_id']
        self._calendar_dt = d['calendar_dt']
        self._trading_dt = d['trading_dt']
        self._order_book_id = d['order_book_id']
        self._quantity = d['quantity']
        self._side = self._str_to_enum(SIDE, d['side'])
        if d['position_effect'] is None:
            self._position_effect = None
        else:
            self._position_effect = self._str_to_enum(POSITION_EFFECT, d['position_effect'])
        self._message = d['messages']
        self._filled_quantity = d['filled_quantity']
        self._status = self._str_to_enum(ORDER_STATUS, d['status'])
        self._frozen_price = d['frozen_price']
        self._type = self._str_to_enum(ORDER_TYPE, d['type'])

    @classmethod
    def __from_create__(cls, calendar_dt, trading_dt, order_book_id, quantity, side, style, position_effect):
        order = cls()
        order._order_id = next(order.order_id_gen)
        order._calendar_dt = calendar_dt
        order._trading_dt = trading_dt
        order._quantity = quantity
        order._order_book_id = order_book_id
        order._side = side
        order._position_effect = position_effect
        order._message = ""
        order._filled_quantity = 0
        order._status = ORDER_STATUS.PENDING_NEW
        if isinstance(style, LimitOrder):
            order._frozen_price = style.get_limit_price()
            order._type = ORDER_TYPE.LIMIT
        else:
            order._frozen_price = 0.
            order._type = ORDER_TYPE.MARKET
        order._avg_price = 0
        order._transaction_cost = 0
        return order

    @property
    def order_id(self):
        """
        [int] ?????????????????????id
        """
        return self._order_id

    @property
    def trading_datetime(self):
        """
        [datetime.datetime] ?????????????????????????????????????????????
        """
        return self._trading_dt

    @property
    def datetime(self):
        """
        [datetime.datetime] ??????????????????
        """
        return self._calendar_dt

    @property
    def quantity(self):
        """
        [int] ????????????
        """
        return self._quantity

    @property
    def unfilled_quantity(self):
        """
        [int] ?????????????????????
        """
        return self._quantity - self._filled_quantity

    @property
    def order_book_id(self):
        """
        [str] ????????????
        """
        return self._order_book_id

    @property
    def side(self):
        """
        [SIDE] ????????????
        """
        return self._side

    @property
    def position_effect(self):
        """
        [POSITION_EFFECT] ??????????????????????????????
        """
        return self._position_effect

    @property
    def message(self):
        """
        [str] ??????????????????????????????????????????????????????
        """
        return self._message

    @property
    def filled_quantity(self):
        """
        [int] ?????????????????????
        """
        return self._filled_quantity

    @property
    def status(self):
        """
        [ORDER_STATUS] ????????????
        """
        return self._status

    @property
    def price(self):
        """
        [float] ???????????????????????????????????????'?????????'?????????????????????
        """
        return 0 if self.type == ORDER_TYPE.MARKET else self._frozen_price

    @property
    def type(self):
        """
        [ORDER_TYPE] ????????????
        """
        return self._type

    @property
    def avg_price(self):
        """
        [float] ????????????
        """
        return self._avg_price

    @property
    def transaction_cost(self):
        """
        [float] ??????
        """
        return self._transaction_cost

    @property
    def frozen_price(self):
        """
        [float] ????????????
        """
        return self._frozen_price

    def is_final(self):
        return self._status not in {
            ORDER_STATUS.PENDING_NEW,
            ORDER_STATUS.ACTIVE,
            ORDER_STATUS.PENDING_CANCEL
        }

    def is_active(self):
        return self.status == ORDER_STATUS.ACTIVE

    def active(self):
        self._status = ORDER_STATUS.ACTIVE

    def set_pending_cancel(self):
        if not self.is_final():
            self._status = ORDER_STATUS.PENDING_CANCEL

    def fill(self, trade):
        quantity = trade.last_quantity
        assert self.filled_quantity + quantity <= self.quantity
        new_quantity = self._filled_quantity + quantity
        self._avg_price = (self._avg_price * self._filled_quantity + trade.last_price * quantity) / new_quantity
        self._transaction_cost += trade.commission + trade.tax
        self._filled_quantity = new_quantity
        if self.unfilled_quantity == 0:
            self._status = ORDER_STATUS.FILLED

    def mark_rejected(self, reject_reason):
        if not self.is_final():
            self._message = reject_reason
            self._status = ORDER_STATUS.REJECTED
            user_system_log.warn(reject_reason)

    def mark_cancelled(self, cancelled_reason, user_warn=True):
        if not self.is_final():
            self._message = cancelled_reason
            self._status = ORDER_STATUS.CANCELLED
            if user_warn:
                user_system_log.warn(cancelled_reason)

    def set_frozen_price(self, value):
        self._frozen_price = value

    def __simple_object__(self):
        return properties(self)


class OrderStyle(object):
    def get_limit_price(self):
        raise NotImplementedError


class MarketOrder(OrderStyle):
    __repr__ = ORDER_TYPE.MARKET.__repr__

    def get_limit_price(self):
        return None


class LimitOrder(OrderStyle):
    __repr__ = ORDER_TYPE.LIMIT.__repr__

    def __init__(self, limit_price):
        self.limit_price = float(limit_price)

    def get_limit_price(self):
        return self.limit_price
