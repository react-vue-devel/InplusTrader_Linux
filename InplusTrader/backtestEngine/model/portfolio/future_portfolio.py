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

from .base_portfolio import BasePortfolio
from ..dividend import Dividend
from ..position import Positions, PositionsClone, FuturePosition
from ...utils.repr import dict_repr


FuturePersistMap = {
    "_yesterday_portfolio_value": "_yesterday_portfolio_value",
    "_yesterday_units": "_yesterday_units",
    "_cash": "_cash",
    "_starting_cash": "_starting_cash",
    "_units": "_units",
    "_start_date": "_start_date",
    "_current_date": "_current_date",
    "_frozen_cash": "_frozen_cash",
    "_total_commission": "_total_commission",
    "_total_tax": "_total_tax",
    "_dividend_receivable": "_dividend_receivable",
    "_dividend_info": "_dividend_info",
    "_daily_transaction_cost": "_daily_transaction_cost",
    "_positions": "_positions",
}


class FuturePortfolioClone(object):
    __repr__ = dict_repr


class FuturePortfolio(BasePortfolio):
    def __init__(self, cash, start_date, account_type):
        super(FuturePortfolio, self).__init__(cash, start_date, account_type)
        self._daily_transaction_cost = 0
        self._positions = Positions(FuturePosition)
        self._portfolio_value = None

    def restore_from_dict_(self, portfolio_dict):
        self._cash = portfolio_dict['_cash']
        self._start_date = portfolio_dict['_start_date']
        self._positions.clear()
        self._dividend_info.clear()
        for persist_key, origin_key in six.iteritems(FuturePersistMap):
            if persist_key == "_dividend_info":
                for order_book_id, dividend_dict in six.iteritems(portfolio_dict[persist_key]):
                    self._dividend_info[order_book_id] = Dividend.__from_dict__(dividend_dict)
            elif persist_key == "_positions":
                for order_book_id, position_dict in six.iteritems(portfolio_dict[persist_key]):
                    self._positions[order_book_id] = FuturePosition.__from_dict__(position_dict)
            else:
                try:
                    setattr(self, origin_key, portfolio_dict[persist_key])
                except KeyError as e:
                    if persist_key in ["_yesterday_units", "_units"]:
                        # FIXME ???????????? persist_key ?????????error handling ?????????
                        setattr(self, origin_key, portfolio_dict["_starting_cash"])
                    else:
                        raise e

    def __to_dict__(self):
        p_dict = {}
        for persist_key, origin_key in six.iteritems(FuturePersistMap):
            if persist_key == "_dividend_info":
                p_dict[persist_key] = {oid: dividend.__to_dict__() for oid, dividend in six.iteritems(getattr(self, origin_key))}
            elif persist_key == "_positions":
                p_dict[persist_key] = {oid: position.__to_dict__() for oid, position in six.iteritems(getattr(self, origin_key))}
            else:
                p_dict[persist_key] = getattr(self, origin_key)
        return p_dict

    @property
    def positions(self):
        """
        ???dict???????????????????????????????????????????????????order_book_id????????????position???????????????
        """
        return self._positions

    @property
    def cash(self):
        """
        ???float???????????????
        """
        return self.portfolio_value - self.margin - self.daily_holding_pnl - self.frozen_cash

    @property
    def portfolio_value(self):
        """
        ???float??????????????????????????????+????????????
        """
        if self._portfolio_value is None:
            self._portfolio_value = self._yesterday_portfolio_value + self.daily_pnl

        return self._portfolio_value

    # @property
    # def _risk_cash(self):
    #     # ????????????
    #     risk_cash = self.cash if self.daily_holding_pnl > 0 else self.cash + self.daily_holding_pnl
    #     return risk_cash

    @property
    def buy_margin(self):
        """
        ???float??????????????????
        """
        # ????????????
        # TODO ?????????????????? T TF ????????????????????????????????????
        # TODO ?????????????????? ??????????????????????????????????????????
        return sum(position.buy_margin for position in six.itervalues(self.positions))

    @property
    def sell_margin(self):
        """
        ???float??????????????????
        """
        # ????????????
        return sum(position.sell_margin for position in six.itervalues(self.positions))

    @property
    def margin(self):
        """
        ???float?????????????????????
        """
        # ????????????
        return sum(position.margin for position in six.itervalues(self.positions))

    @property
    def daily_holding_pnl(self):
        """
        ???float?????????????????????
        """
        # ??????????????????
        return sum(position.daily_holding_pnl for position in six.itervalues(self.positions))

    @property
    def daily_realized_pnl(self):
        """
        ???float?????????????????????
        """
        # ??????????????????
        return sum(position.daily_realized_pnl for position in six.itervalues(self.positions))

    @property
    def daily_pnl(self):
        """
        ???float???????????????????????????????????? + ?????????????????? - ????????????
        """
        # ????????????
        return self.daily_realized_pnl + self.daily_holding_pnl - self._daily_transaction_cost

    def _clone(self):
        p = FuturePortfolioClone()
        for key in dir(self):
            if "__" in key:
                continue
            if key == "positions":
                ps = PositionsClone(FuturePosition)
                for order_book_id in self.positions:
                    ps[order_book_id] = self.positions[order_book_id]._clone()
                setattr(p, key, ps)
            else:
                setattr(p, key, getattr(self, key))
        return p
