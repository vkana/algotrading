from alpaca.trading.client import TradingClient
from alpaca.data.live import StockDataStream
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import MarketOrderRequest, ClosePositionRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import constants
from datetime import datetime, timedelta 
import time
import threading


initial_qty = 10
exp = [1<<exponent for exponent in range(20)]

class Position(object):
    def __init__(self):
        self.qty = initial_qty
        self.entry_price = 0
        self.qty_available = 0
        self.last_price = 0


class My(object):
    def __init__(self):
        self.key_id = constants.ALPACA_API_KEY4
        self.secret_key = constants.ALPACA_SECRET_KEY4
        self.base_url = constants.base_url
        self.stocks = ('TQQQ', 'SQQQ','BBBY')
        self.positions = {}
        self.target_price = 0.05
        self.start_equity = 0
        self.last_equity = 0
        self.live = False
        self.now = ''
        self.last_order_time = None

        if self.live:
            self.base_url = constants.base_url_live
            self.key_id = constants.ALPACA_API_KEY_LIVE
            self.secret_key = constants.ALPACA_SECRET_KEY_LIVE

        
        self.trading_client = TradingClient(self.key_id, self.secret_key, paper = not self.live)
        self.ws = StockDataStream(self.key_id, self.secret_key)
        self.ts = TradingStream(self.key_id, self.secret_key, paper = not self.live)
    
    def process_trade(self, symbol, bid_price, ask_price):
        
        position = self.positions[symbol]
        last_price = position.last_price
        diff = 0
        try:
            diff = exp.index(position.qty/10) / 100
        except:
            pass

        #print(f'diff={diff}')
        
        if last_price == 0 or ask_price < last_price - self.target_price - diff:
            #print(f'{symbol} buy condition {last_price} == 0 or  {ask_price}  < {last_price - self.target_price - diff}')
            if float(self.trading_client.get_account().regt_buying_power) < ask_price * position.qty:
                print(f'{self.now} {symbol} {ask_price} {position.entry_price} {position.qty} No buying power. Skipping..')
                #avoid get_account call repeatedly
                position.last_price = ask_price
                return
            
            try:
                position.last_price = ask_price
                self.last_order_time = datetime.now()
                self.trading_client.submit_order(order_data=MarketOrderRequest(symbol=symbol, qty=position.qty, side=OrderSide.BUY, time_in_force=TimeInForce.DAY))
            except Exception as e:
                print(symbol, ask_price, position.entry_price, position.qty,  e)
                print('after exception -', symbol, position.last_price)
            return
        
        if position.qty_available > 0 and bid_price > position.entry_price + self.target_price:
            #print(f'{symbol} sell condition {position.qty_available} > 0 and  {bid_price} > {position.entry_price + self.target_price}')
            try:
                #self.trading_client.submit_order(symbol, position.qty_available, 'sell', 'market', 'day')
                self.last_order_time = datetime.now()
                self.trading_client.close_position(symbol, close_options=ClosePositionRequest(percentage=100))
                #reset
                position.last_price = 0
                position.qty_available = 0
                position.qty = initial_qty
            except Exception as e:
                print(symbol, e)

    def check_market_open(self):
        clock = self.trading_client.get_clock()
        
        if self.live and not clock.is_open:
            next_open = clock.next_open
            now = datetime.now(tz=next_open.tzinfo)
            secs = (next_open - now).total_seconds()
            print('sleeping until market open..')
            time.sleep(secs)

    def start_trading(self):
        self.check_market_open()
        print(f'Start trading.. live={self.live}')
        account = self.trading_client.get_account()
        self.last_equity = float(account.last_equity)
        self.start_equity = float(account.equity)

        for symbol in self.stocks:
            self.positions[symbol] = Position()
            position = self.positions[symbol]
            try:
                acct_position = self.trading_client.get_open_position(symbol)
                #if position exists on start
                position.entry_price = float(acct_position.avg_entry_price)
                position.last_price = position.entry_price
                position.qty_available = int(acct_position.qty)
                position.qty = position.qty_available
                print(f'Existing position: {symbol} {position.qty} {position.last_price}')
            except Exception as e:
                position.entry_price = 0
                position.qty_available = 0
                print('Exception s_t:', e)

        async def handle_quotes(data):
            now = datetime.now()
            if self.last_order_time is not None and now - self.last_order_time < timedelta(seconds=3):
                #print(now, 'Cool off. skipping')
                return
            
            bid_price, ask_price = float(data.bid_price), float(data.ask_price)
            if bid_price == 0 or ask_price == 0:
                return

            self.now = now.time().strftime('%H:%M:%S')
            self.process_trade(data.symbol, bid_price, ask_price)

        async def handle_trade_updates(data):
            if data.event == 'fill' or data.event == 'partial_fill':
                symbol, side, price = data.order.symbol, data.order.side, data.order.filled_avg_price
                account = self.trading_client.get_account()
                current_equity = float(account.equity)
                #self.positions[symbol] = float(data.position_qty)
                position = self.positions[symbol]
                try:
                    acct_position = self.trading_client.get_open_position(symbol)
                    position.entry_price = float(acct_position.avg_entry_price)
                    position.qty_available = int(acct_position.qty)
                    position.qty = position.qty_available if position.qty_available != 0 else initial_qty
                except Exception as e:
                    position.entry_price = 0
                    position.qty_available = 0
                    position.qty = initial_qty
                    position.last_price = 0
                    print('Exception htu: ', symbol, data.event, e)
                
                print(f'{self.now} {side} {symbol} {round(float(price),2)} / {round(position.entry_price, 2)} qty: {data.qty} / {position.qty_available}  PnL: ${round(current_equity - self.start_equity, 2)} / ${round(current_equity - self.last_equity, 2)} {"partial" if data.event == "partial_fill" else ""}')

        async def handle_bars(trade): #TBD
            print('handle_trades', trade.price)

        async def handle_news(news): #TBD
            print('handle_trades', news)
        
        async def handle_crypto(crypto): #TBD
            print('handle_crypto', crypto)

        self.ws.subscribe_quotes(handle_quotes, *self.stocks)
        self.ts.subscribe_trade_updates(handle_trade_updates)
        t1 = threading.Thread(target = self.ts.run, daemon=True)
        t2 = threading.Thread(target=self.ws.run, daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # print('ts run')
        # self.ts.run()
        # #self.ts._start_ws()
        # print('ws run')
        # self.ws.run()
        

if __name__ == '__main__':
    trader = My()
    trader.start_trading()