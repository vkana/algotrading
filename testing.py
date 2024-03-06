from datetime import datetime, timedelta
from tarfile import RECORDSIZE
from alpaca.trading.client import TradingClient
import concurrent.futures
from threading import Event
import time
import constants
import pandas as pd

live = False

if live:
    key = constants.ALPACA_API_KEY_LIVE
    secret = constants.ALPACA_SECRET_KEY_LIVE
else:
    key = constants.ALPACA_API_KEY3
    secret = constants.ALPACA_SECRET_KEY3

trading_client = trading_client = TradingClient(key, secret, paper = not live)


def begin_trading():
    print('begin trading..')

def market_open(event):
    print('market-open')
    clock = trading_client.get_clock()
    next_open = clock.next_open - timedelta(hours = 5.5)
    now = datetime.now(tz=next_open.tzinfo)
    seconds = (next_open - now).total_seconds()
    if seconds > 0:
        print(f'Sleeping until pre-market open in {seconds}..')
        time.sleep(seconds)
    print('Market is now open..')
    begin_trading()

def market_close(event):
    print('market-close')
    clock = trading_client.get_clock()
    if clock.is_open:
        next_open = clock.next_open - timedelta(hours = 5.5)
        now = datetime.now(tz=next_open.tzinfo)
        seconds = (next_open - now).total_seconds()
        print(f'Sleeping until pre-market open in {seconds}..')
        time.sleep(seconds)
        print('pre-market is now open.. ')
        begin_trading()


def func2(event):
    now = datetime.now()
    end_time = datetime.now() + timedelta(seconds = 5)
    sleep_secs = (end_time - now).total_seconds()
    print(f'sleeping {sleep_secs} seconds')
    time.sleep(sleep_secs)

    print('close now')
    event.set()

def is_full_trading_day():
    REGULAR_TRADING_CLOSE = pd.Timestamp('16:00').time()
    clock = trading_client.get_clock()
    return clock.timestamp.date() == clock.next_close.date() and clock.next_close.time() == REGULAR_TRADING_CLOSE

    

def start():
    print('start..')

    trading_days = trading_client.get_clock()

    #a = [day.date for day in trading_days]

    print(is_full_trading_day())

    # event = Event()    
    # with concurrent.futures.ThreadPoolExecutor() as executor:
    #     executor.submit(market_open, event)
    #     #executor.submit(func2, event)


if __name__ == '__main__':
    print('main')
    start()