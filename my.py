import alpaca_trade_api as tradeapi
from alpaca_trade_api.stream import Stream

ALPACA_API_KEY = "PKLPZUANOESGO4HXOEV6"
ALPACA_SECRET_KEY = "YC3ynGkI6rb5Q1MBYdGlYVlg7KHookKB8AqPwhpv"

class My(object):
    def __init__(self):
        self.key_id = ALPACA_API_KEY
        self.secret_key = ALPACA_SECRET_KEY
        self.base_url = 'https://paper-api.alpaca.markets'
        self.data_url = 'https://data.alpaca.markets/v2'
        self.stocks = ('AMD')
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
    
    def process_trade(self, symbol, price):
        try:
            last_price = float(self.last_price[symbol])
        except Exception as e:
            self.last_price[symbol] = price
            last_price = price
        
        if price < last_price - self.target_price:
            self.last_price[symbol] = price
            try:
                self.api.submit_order(symbol, self.qty, 'buy', 'market', 'day')
            except Exception as e:
                print(e)

        if price > last_price + self.target_price:
            self.last_price[symbol] = price
            try:
                self.api.submit_order(symbol, self.qty, 'sell', 'market', 'day')
            except Exception as e:
                print(e)
    
    def start_trading(self):
        print('start trading')
        self.last_equity = float(self.api.get_account().last_equity)
        self.start_equity = float(self.api.get_account().equity)
        #print([s.symbol for s in [asset for asset in self.api.list_assets(status="active") if asset.tradable]])
        
        async def handle_trades(trade):
            self.process_trade(trade.symbol, trade.price)
        
        async def handle_trade_updates(data):
            
            if data.event == 'fill':
                symbol = data.order['symbol']
                price = data.order['filled_avg_price']
                side = data.order['side']
                current_equity = float(self.api.get_account().equity)
                print(f'{side} {symbol} {price} {data.position_qty} {current_equity} day: {round(current_equity - self.last_equity, 2)} this_run: {round(current_equity - self.start_equity, 2)}')

        async def handle_bars(trade): #TBD
            print('handle_trades', trade.price)
            print(self.conn)

        async def handle_news(news): #TBD
            print('handle_trades', news)
        
        async def handle_crypto(crypto): #TBD
            print('handle_crypto', crypto)

        self.conn.subscribe_trades(handle_trades, *self.stocks)
        self.conn.subscribe_trade_updates(handle_trade_updates)
        #self.conn.subscribe_news(handle_news, *self.stocks)
        #self.conn.subscribe_crypto_trades(handle_crypto, 'BTCUSD')

        self.conn.run()

        

if __name__ == '__main__':
    trader = My()
    trader.start_trading()