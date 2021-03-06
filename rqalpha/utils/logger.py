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

import traceback
import logbook
import better_exceptions
from logbook import Logger
from logbook.more import ColorizedStderrHandler

from .py2 import to_utf8, from_utf8

logbook.set_datetime_format("local")


# patch warn
logbook.base._level_names[logbook.base.WARNING] = 'WARN'


# better_exceptions hot patch
def format_exception(exc, value, tb):
    formatted, colored_source = better_exceptions.format_traceback(tb)

    if not str(value) and exc is AssertionError:
        value.args = (colored_source,)
    title = traceback.format_exception_only(exc, value)
    title = from_utf8(title[0].strip())
    full_trace = u'Traceback (most recent call last):\n{}{}\n'.format(formatted, title)

    return full_trace

better_exceptions.format_exception = format_exception


__all__ = [
    "user_log",
    "system_log",
]


DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.00"


def user_std_handler_log_formatter(record, handler):
    from ..environment import Environment
    try:
        dt = Environment.get_instance().calendar_dt.strftime(DATETIME_FORMAT)
    except Exception:
        dt = "0000-00-00"

    log = "{dt} {level} {msg}".format(
        dt=dt,
        level=record.level_name,
        msg=to_utf8(record.message),
    )
    return log


user_std_handler = ColorizedStderrHandler(bubble=True)
user_std_handler.formatter = user_std_handler_log_formatter


def formatter_builder(tag):
    def formatter(record, handler):

        log = "[{formatter_tag}] [{time}] {level}: {msg}".format(
            formatter_tag=tag,
            level=record.level_name,
            msg=to_utf8(record.message),
            time=record.time,
        )

        if record.formatted_exception:
            log += "\n" + record.formatted_exception
        return log
    return formatter


# loggers
# ????????????logger??????
user_log = Logger("user_log")
# ???????????????????????????
user_system_log = Logger("user_system_log")

# ???????????????????????????????????????
user_detail_log = Logger("user_detail_log")
# user_detail_log.handlers.append(ColorizedStderrHandler(bubble=True))

# ????????????
system_log = Logger("system_log")
system_log.handlers.append(ColorizedStderrHandler(bubble=True))

# ??????????????????
std_log = Logger("std_log")
std_log.handlers.append(ColorizedStderrHandler(bubble=True))


def user_print(*args, **kwargs):
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "")

    message = sep.join(map(str, args)) + end

    user_log.info(message)

