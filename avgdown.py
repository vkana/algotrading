import alpaca_trade_api as tradeapi
from alpaca_trade_api.stream import Stream

ALPACA_API_KEY = "PKTMZ2ABG2PNACMCEQW6"
ALPACA_SECRET_KEY = "Ketd8u3oXpsroCfTfT60vxnnq01BvELJgnCoJN4A"

class My(object):
    def __init__(self):
        self.key_id = ALPACA_API_KEY
        self.secret_key = ALPACA_SECRET_KEY
        self.base_url = 'https://paper-api.alpaca.markets'
        self.data_url = 'https://data.alpaca.markets/v2'
        self.stocks = 'TQQQ'
        self.target_price = 0.05
        self.qty = 10
        self.start_equity = 0
        self.last_equity = 0
        self.entry_price = 0
        self.qty_available = 0
        self.last_price = {} 
        self.increment = 10
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
            last_price = 0
        
        if last_price == 0 or price < last_price - self.target_price:
            try:
                self.api.submit_order(symbol, self.qty, 'buy', 'market', 'day')
                self.last_price[symbol] = price
                self.qty += self.increment
            except Exception as e:
                print(e)

        if self.qty_available > 0 and price > self.entry_price + self.target_price:
            try:
                self.api.submit_order(symbol, self.qty_available, 'sell', 'market', 'day')
                #reset
                self.last_price[symbol] = 0
                self.qty_available = 0
                self.qty = 1
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
                #self.positions[symbol] = float(data.position_qty)
                try:
                    position = self.api.get_position(symbol)
                    self.entry_price = round(float(position.avg_entry_price), 2)
                    self.qty_available = int(position.qty_available)
                except:
                    position = 0
                    self.entry_price = 0
                    self.qty_available = 0
                
                print(f'{side} {symbol} {price} {data.qty} total: {data.position_qty} avg_entry: {self.entry_price} {current_equity} day: {round(current_equity - self.last_equity, 2)} this_run: {round(current_equity - self.start_equity, 2)}')

        async def handle_bars(trade): #TBD
            print('handle_trades', trade.price)
            print(self.conn)

        async def handle_news(news): #TBD
            print('handle_trades', news)
        
        async def handle_crypto(crypto): #TBD
            print('handle_crypto', crypto)

        self.conn.subscribe_trades(handle_trades, self.stocks)
        self.conn.subscribe_trade_updates(handle_trade_updates)
        #self.conn.subscribe_news(handle_news, *self.stocks)
        #self.conn.subscribe_crypto_trades(handle_crypto, 'BTCUSD')

        self.conn.run()

        

if __name__ == '__main__':
    trader = My()
    trader.start_trading()