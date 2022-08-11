from sqlite3 import Timestamp
import alpaca_trade_api as tradeapi
import constants
from alpaca_trade_api.stream import Stream
import logging
import pandas as pd
from datetime import datetime
import time

class My(object):
    def __init__(self):
        self.key_id = constants.ALPACA_API_KEY
        self.secret_key = constants.ALPACA_SECRET_KEY
        self.base_url = constants.base_url
        self.data_url = constants.data_url
        self.stocks = ('SQQQ', 'TQQQ')
        self.last_price = {}
        self.positions = {}
        self.target_price = 0.05
        self.qty = 100
        self.start_equity = 0
        self.last_equity = 0


        self.api = tradeapi.REST(
            self.key_id,
            self.secret_key,
            self.base_url,
            'v2')
        
        self.conn = Stream(
            self.key_id,
            self.secret_key,
            base_url = self.base_url,
            data_feed = 'iex'
        )
    
    
    
    def start_trading(self):
        async def handle_quotes(quote):
            print('quote', quote.symbol, quote.bid_price, quote.ask_price, datetime.now().time().strftime('%H:%M:%S'), quote.timestamp.strftime('%H:%M:%S'))
        async def handle_trades(trade):
            print('***trade', trade.symbol, trade.price, datetime.now().time().strftime('%H:%M:%S'), trade.timestamp.strftime('%H:%M:%S'))
        
        self.conn.subscribe_quotes(handle_quotes, *self.stocks)
        self.conn.subscribe_trades(handle_trades, *self.stocks)

        self.conn.run()
        

if __name__ == '__main__':
    trader = My()
    trader.start_trading()