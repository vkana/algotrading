from alpaca.trading.client import TradingClient
from alpaca.data.live import StockDataStream
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import MarketOrderRequest, ClosePositionRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, PositionSide
import constants
from datetime import datetime, timedelta 
import time
import concurrent.futures


initial_qty = 10
exp = [1<<exponent for exponent in range(20)]

class Position(object):
    def __init__(self):
        self.qty = initial_qty
        self.entry_price = 0
        self.qty_available = 0
        self.side = ''
        self.last_price = 0


class My(object):
    def __init__(self):
        self.live = False
        self.key_id = constants.ALPACA_API_KEY4
        self.secret_key = constants.ALPACA_SECRET_KEY4
        self.base_url = constants.base_url
        self.stocks = ('OXY','INTC', 'TQQQ')
        self.positions = {}
        self.target_price = 0.05
        self.start_equity = 0
        self.last_equity = 0
        self.now = ''
        self.last_order_time = None

        if self.live:
            self.base_url = constants.base_url_live
            self.key_id = constants.ALPACA_API_KEY_LIVE
            self.secret_key = constants.ALPACA_SECRET_KEY_LIVE

        
        self.trading_client = TradingClient(self.key_id, self.secret_key, paper = not self.live)
        self.sds = StockDataStream(self.key_id, self.secret_key)
        self.ts = TradingStream(self.key_id, self.secret_key, paper = not self.live)

    def check_bp_and_order(self, symbol, price, qty, side):
        if float(self.trading_client.get_account().daytrading_buying_power) < price * qty:
            print(f'{self.now} {symbol} {price} {qty} No buying power. Skipping..')
            return
        
        try:
            self.last_order_time = datetime.now()
            self.trading_client.submit_order(order_data=MarketOrderRequest(symbol=symbol, qty=qty, side=side, time_in_force=TimeInForce.GTC))
        except Exception as e:
            print(symbol, price, qty,  e)
            print('after order exception - ', symbol)
    
    def process_trade(self, symbol, bid_price, ask_price):
        position = self.positions[symbol]
        last_price = position.last_price
        diff = 0
        try:
            diff = exp.index(position.qty/initial_qty) / 100
        except:
            for e in exp:
                if position.qty/initial_qty > e:
                    diff += 1
            pass

        #print(f'qty={position.qty} init={initial_qty} side={position.side}')

        if position.qty_available == 0: #first trade
            
            position.last_price = ask_price
            order_side = OrderSide.SELL if position.side == PositionSide.SHORT else OrderSide.BUY
            print(f'{symbol} first entry {order_side}')
            self.check_bp_and_order(symbol, ask_price, position.qty, order_side)

        elif position.side == PositionSide.LONG:
            if ask_price < last_price - self.target_price - diff: #long next entry
                print(f'{symbol} long next entry {ask_price} < {last_price} - {self.target_price} - {diff}')
                position.last_price = ask_price
                self.check_bp_and_order(symbol, ask_price, position.qty, OrderSide.BUY)
            elif position.qty_available > 0 and  bid_price > position.entry_price + self.target_price: #long target exit
                print(f'{symbol} {position.qty_available} long target exit')
                self.last_order_time = datetime.now()
                try:
                    self.trading_client.close_position(symbol, close_options=ClosePositionRequest(percentage=100))
                    print('long exit no exception')
                    position.last_price = 0
                    position.qty_available = 0
                    position.qty = initial_qty
                except Exception as e:
                    print('long exit', symbol, e)
        elif position.side == PositionSide.SHORT:
            if bid_price > last_price + self.target_price + diff: #short next entry
                print(f'{symbol} short next entry {bid_price} > {last_price} + {self.target_price} + {diff}')
                position.last_price = bid_price
                self.check_bp_and_order(symbol, bid_price, position.qty, OrderSide.SELL)
            elif position.qty_available < 0 and ask_price < position.entry_price - self.target_price: #short target exit
                print(f'{symbol} short target exit')
                try:
                    self.last_order_time = datetime.now()
                    self.trading_client.close_position(symbol, close_options=ClosePositionRequest(percentage=100))
                    position.last_price = 0
                    position.qty_available = 0
                    position.qty = initial_qty
                except Exception as e:
                    print('short exit', symbol, e)

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
                position.qty_available = round(float(acct_position.qty),2)
                position.side = acct_position.side
                position.qty = initial_qty if position.qty_available < initial_qty else position.qty_available
                print(f'Existing position: {symbol} {position.qty_available} {position.side} {position.last_price}')
            except Exception as e:
                position.entry_price = 0
                position.qty_available = 0
                position.qty = initial_qty
                position.side = PositionSide.LONG
                print(symbol, e)

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
                symbol, side, price = data.order.symbol.replace('/',''), data.order.side, data.order.filled_avg_price
                account = self.trading_client.get_account()
                current_equity = float(account.equity)
                #self.positions[symbol] = float(data.position_qty)
                position = self.positions[symbol]
                try:
                    acct_position = self.trading_client.get_open_position(symbol)
                    position.entry_price = float(acct_position.avg_entry_price)
                    position.qty_available = round(float(acct_position.qty),2)
                    position.side = acct_position.side
                    position.qty = initial_qty if position.qty_available < initial_qty else position.qty_available
                except Exception as e:
                    position.entry_price = 0
                    position.qty_available = 0
                    position.qty = initial_qty
                    position.side = PositionSide.SHORT if side == OrderSide.SELL else PositionSide.LONG
                    position.last_price = 0
                    print('Exception htu: ', symbol, data.event, e)
                
                print(f'{self.now} {side} {symbol} {round(float(price),2)} / {round(position.entry_price, 2)} {position.side} qty: {data.qty} / {position.qty_available}  PnL: ${round(current_equity - self.start_equity, 2)} / ${round(current_equity - self.last_equity, 2)} {"partial" if data.event == "partial_fill" else ""}')

        async def handle_bars(trade): #TBD
            print('handle_trades', trade.price)

        async def handle_news(news): #TBD
            print('handle_trades', news)
        
        async def handle_crypto(crypto): #TBD
            print('handle_crypto', crypto)

        self.sds.subscribe_quotes(handle_quotes, *self.stocks)
        self.ts.subscribe_trade_updates(handle_trade_updates)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            f1 = executor.submit(self.ts.run)
            f2 = executor.submit(self.sds.run)

if __name__ == '__main__':
    trader = My()
    trader.start_trading()