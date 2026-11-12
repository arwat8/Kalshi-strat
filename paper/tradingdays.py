"""Trading-day arithmetic (weekdays that are not CME/NYSE holidays)."""
import datetime as dt

from . import config as C

_HOL = {dt.date.fromisoformat(d) for d in C.MARKET_HOLIDAYS}


def is_trading_day(d):
    return d.weekday() < 5 and d not in _HOL


def add_trading_days(d, n):
    """The n-th trading day after date d."""
    k = 0
    while k < n:
        d += dt.timedelta(days=1)
        if is_trading_day(d):
            k += 1
    return d


def trading_days_between(a, b):
    """Number of trading days strictly after a, up to and including b (0 if b <= a)."""
    n, d = 0, a
    while d < b:
        d += dt.timedelta(days=1)
        if is_trading_day(d):
            n += 1
    return n
