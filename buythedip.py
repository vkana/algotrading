import alpaca_trade_api as tradeapi
from alpaca_trade_api.stream import Stream
import datetime

ALPACA_API_KEY = "PKBT5L3P0ZLZ0H7XY3T8"
ALPACA_SECRET_KEY = "cE9ofJh0o2DHaRjec8ttZW0KuLLirIcQFnBpQjIu"


# Utility to truncate a float value to a certain number of decimal places.
# We'll use this to see if a "penny level" was crossed when we compare prices.
# This is necessary because a price can change by 1/100th of a penny, but we
# can only trade at full-penny increments.
def truncate(val, decimal_places):
    return int(val * 10**decimal_places) / 10**decimal_places


# The MartingaleTrader bets that streaks of increases or decreases in a stock's
# price are likely to break, and increases its bet each time it is wrong.
class BuytheDip(object):
    def __init__(self):
        self.key_id = ALPACA_API_KEY
        self.secret_key = ALPACA_SECRET_KEY
        self.base_url = 'https://paper-api.alpaca.markets'
        self.data_url = 'https://data.alpaca.markets/v2'
        self.symbol='SPY'
        self.current_order = None
        self.last_position = 0
        self.current_position = 0
        self.low=0
        self.high=0

        self.buy_qty = 10
        self.last_price = 0
        self.tick_size = 1
        self.tick_index = 0

        self.api = tradeapi.REST(
            self.key_id,
            self.secret_key,
            self.base_url
        )

        try:
            self.position = int(self.api.get_position(self.symbol).qty)
        except:
            # No position exists
            self.position = 0

    print(f'start')

    def start_trading(self):
        print(f'start trading')
        self.api.get_clock()
        conn = Stream(
            self.key_id,
            self.secret_key,
            base_url=self.base_url,
            data_feed='iex',
            websocket_params =  {'ping_interval': 30}) 
        
        async def handle_trade_updates (data):
            symbol = data.order['symbol']
            if symbol == self.symbol and data.event == 'fill':
                self.current_position = data.position_qty

        async def handle_trades(trade):
            self.process_current_tick(None, trade.price)
            
        #conn.subscribe_bars(handle_bar, self.symbol)
        conn.subscribe_trades(handle_trades, self.symbol)
        #conn.subscribe_trade_updates(handle_trade_updates)

        conn.run()

    def process_current_tick(self, tick_open, tick_close):
        if self.low == 0 or tick_close < self.low:
            self.low = tick_close
        
        if self.high == 0 or tick_close > self.high:
            self.high = tick_close
        
        #print(f'low: {self.low}, high: {self.high}')
        
        if tick_close < self.high - 0.10:
            self.current_order = self.api.submit_order(
                    self.symbol, self.buy_qty, 'buy',
                    'market', 'day', None, None, None, False
                )
            print(f'buying at {tick_close}, equity={self.api.get_account().equity}, low {self.low}, high {self.high}, current position: {self.api.get_position(self.symbol)}')   
            self.high = tick_close
            
        if tick_close > self.low + 0.10:
            self.current_order = self.api.submit_order(
                    self.symbol, self.buy_qty, 'sell',
                    'market', 'day', None, None, None, False
                )
            print(f'selling at {tick_close}, equity={self.api.get_account().equity}, low {self.low}, high {self.high}, current position: {self.api.get_position(self.symbol)}')  
            self.low = tick_close
        



        

        

if __name__ == '__main__':
    trader = BuytheDip()
    trader.start_trading()
