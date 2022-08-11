from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data import StockDataStream
import constants
import time

initial_qty = 5

class Position(object):
    def __init__(self):
        self.qty = initial_qty
        self.entry_price = 0
        self.qty_available = 0
        self.last_price = 0


class My(object):
    def __init__(self):
        self.key_id = constants.ALPACA_API_KEY2
        self.secret_key = constants.ALPACA_SECRET_KEY2
        self.stocks = ('TQQQ', 'SQQQ')
        self.positions = {}
        self.target_price = 0.05
        self.start_equity = 0
        self.last_equity = 0
        self.live = False

        if self.live:
            self.key_id = constants.ALPACA_API_KEY_LIVE
            self.secret_key = constants.ALPACA_SECRET_KEY_LIVE

        self.trading_client = TradingClient(self.key_id, self.secret_key, paper= not self.live)
        self.stock_stream = StockDataStream(self.key_id, self.secret_key)    
            
    
    def process_trade(self, symbol, price):
        last_price = float(self.positions[symbol].last_price)
        position = self.positions[symbol]
        
        if last_price == 0 or price < last_price - self.target_price:
            if float(self.trading_client.get_account().regt_buying_power) < price * position.qty:
                print(f'{symbol} {price} {position.entry_price} {position.qty} No buying power. Skipping..')
                return
            
            try:
                self.trading_client.submit_order(MarketOrderRequest(symbol=symbol, 
                                                                    qty=position.qty, 
                                                                    side=OrderSide.BUY, 
                                                                    time_in_force=TimeInForce.DAY))
                time.sleep(0.5)
                #trade update steps start
                account = self.trading_client.get_account()
                position = self.positions[symbol]
                new_position = self.trading_client.get_open_position(symbol)
                position.entry_price = float(new_position.avg_entry_price)
                position.qty_available = int(new_position.qty)
                print(f'{symbol} {price} {position.entry_price} {position.qty_available}')
                #trade update steps end
                position.last_price = price
                position.qty *= 2
            except Exception as e:
                print(symbol, price, position.entry_price, position.qty,  e)
            return
        
        if position.qty_available > 0 and price > position.entry_price + self.target_price:
            try:
                #self.api.submit_order(symbol, position.qty_available, 'sell', 'market', 'day')
                self.trading_client.close_position(symbol)
                time.sleep(0.5)
                #trade update steps start
                account = self.trading_client.get_account()
                position = self.positions[symbol]
                new_position = self.trading_client.get_open_position(symbol)
                position.entry_price = float(new_position.avg_entry_price)
                position.qty_available = int(new_position.qty)
                print(f'{symbol} {price} {position.entry_price} {position.qty_available}')
                #trade update steps end
                #reset
                position.last_price = 0
                position.qty_available = 0
                position.qty = initial_qty
            except Exception as e:
                print(symbol, e)
    
    def start_trading(self):
        print(f'Start trading.. live={self.live}')
        account = self.trading_client.get_account()
        self.last_equity = float(account.last_equity)
        self.start_equity = float(account.equity)
        #print([s.symbol for s in [asset for asset in self.api.list_assets(status="active") if asset.tradable]])
        for symbol in self.stocks:
            self.positions[symbol] = Position()
            position = self.positions[symbol]
            try:
                acct_position = self.trading_client.get_open_position(symbol)
                position.entry_price = round(float(acct_position.avg_entry_price), 2)
                position.qty_available = int(acct_position.qty)
                position.qty = position.qty_available
            except:
                position.entry_price = 0
                position.qty_available = 0

        async def handle_trades(trade):
            self.process_trade(trade.symbol, trade.price)
        
        async def handle_trade_updates(data):
            if data.event == 'fill' or data.event == 'partial_fill':
                symbol = data.order['symbol']
                price = data.order['filled_avg_price']
                side = data.order['side']
                account = self.trading_client.get_account()
                current_equity = float(account.equity)
                #self.positions[symbol] = float(data.position_qty)
                position = self.positions[symbol]
                try:
                    acct_position = self.trading_client.get_open_position(symbol)
                    position.entry_price = round(float(acct_position.avg_entry_price), 2)
                    position.qty_available = int(acct_position.qty)
                    
                except:
                    position.entry_price = 0
                    position.qty_available = 0
                
                print(f'{side} {symbol} {price} / {position.entry_price} qty: {data.qty} / {position.qty_available} eq: {current_equity} PnL: ${round(current_equity - self.start_equity, 2)} / ${round(current_equity - self.last_equity, 2)}')

        async def handle_bars(trade): #TBD
            print('handle_trades', trade.price)
            print(self.conn)

        async def handle_news(news): #TBD
            print('handle_trades', news)
        
        async def handle_crypto(crypto): #TBD
            print('handle_crypto', crypto)

        self.stock_stream.subscribe_trades(handle_trades, *self.stocks)
        #self.stock_stream.subscribe_trade_updates(handle_trade_updates)
        # #self.conn.subscribe_news(handle_news, *self.stocks)
        # #self.conn.subscribe_crypto_trades(handle_crypto, 'BTCUSD')
        

        self.stock_stream.run()

        

if __name__ == '__main__':
    trader = My()
    trader.start_trading()