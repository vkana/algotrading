from alpaca.trading.client import TradingClient
from alpaca.data.live import StockDataStream
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import MarketOrderRequest, ClosePositionRequest, LimitOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, PositionSide
import constants
from datetime import datetime, timedelta 
import time
import pprint
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
        self.last_qty = 0
        self.next_entry_order = ''
        self.exit_order=''


class My(object):
    def __init__(self):
        self.live = False
        self.key_id = constants.ALPACA_API_KEY4
        self.secret_key = constants.ALPACA_SECRET_KEY4
        self.base_url = constants.base_url
        self.stocks = ('TQQQ', 'SQQQ',)
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
    
    def process_trade(self, symbol, bid_price, ask_price):
        pass

    def check_market_open(self):
        clock = self.trading_client.get_clock()
        
        if not self.live and not clock.is_open:
            next_open = clock.next_open - timedelta(hours=5.5)
            now = datetime.now(tz=next_open.tzinfo)
            secs = (next_open - now).total_seconds()
            print('sleeping until market open..')
            time.sleep(secs)

    def submit_order(self,symbol, qty, side, price):
        order = self.trading_client.submit_order(LimitOrderRequest(symbol=symbol, qty=qty, side=side, time_in_force='day', extended_hours=True, limit_price=price))
        return order

    def get_next_delta(self, current_qty):
        diff = 0
        try:
            diff = exp.index(current_qty/initial_qty) / 100
        except:
            for e in exp:
                if current_qty/initial_qty > e:
                    diff += 1
        return diff

    def start_trading(self):
        #self.check_market_open()
        print(f'Start trading.. live={self.live}')
        for symbol in self.stocks:
            self.positions[symbol] = Position()

        #for every 15 sec
        while False:
            print(f'running..')
            account_positions = self.trading_client.get_all_positions()
            open_orders = self.trading_client.get_orders(GetOrdersRequest(symbols=self.stocks))
            print('open orders: ', open_orders)

            for symbol in self.stocks:
                self.trading_client.cancel_orders()
                try:
                    self.trading_client.close_position(symbol)
                except:
                    pass
                position = self.positions[symbol]
                for ap in account_positions:
                    if ap.symbol == symbol:
                        print(f'found {symbol} {ap.qty} {ap.avg_entry_price} {ap.current_price}')
                        position.qty_available = int(ap.qty)
                        position.entry_price = float(ap.avg_entry_price)
                        if position.last_qty == position.qty_available:
                            #qty didn't change
                            pass
                        else:
                            #cancel orders and re submit
                            try:
                                print('cancel next order')
                                self.trading_client.cancel_order_by_id(position.next_entry_order)
                            except Exception as e:
                                print (e)
                            try:
                                print('exit order')
                                self.trading_client.cancel_order_by_id(position.exit_order)
                            except Exception as e:
                                print (e)
                                pass

                            try:    
                                #next entry order. last_fill_price?? - tgt - diff
                                order = self.submit_order(symbol, position.qty, 'buy', round(float(ap.current_price) - self.target_price - self.get_next_delta(position.qty), 2))
                                print('order 1', order.id, order.filled_avg_price, order.limit_price)
                                position.next_entry_order = order.id
                                order = self.submit_order(symbol, position.qty_available, 'sell', round(position.entry_price + self.target_price, 2))
                                print('order 2 ', order.id, order.filled_avg_price, order.limit_price)
                                position.exit_order = order.id
                            except Exception as e:
                                print (e)

                            position.last_qty = position.qty_available #update last_qty
                            

                        if position.qty_available < initial_qty:
                            position.qty = round(initial_qty - position.qty_available)
                            self.submit_order(symbol, position.qty, 'buy', 39)

                        break
                else:
                    print(f'didnt find position {symbol}')
                    #entry order
                    order = self.submit_order(symbol, initial_qty, 'buy', 39)
                    print(order)
                    #next entry order
                    
                    #exit order

                    pass

            time.sleep(10)

        

        

        async def handle_quotes(data):
            pass

        async def handle_trade_updates(data):
            print(f'trade_update')
            if data.event == 'fill' or data.event == 'partial_fill':
                print(f'{data.event} {data.order.symbol} {data.order.qty} {data.order.side}')
                pass
                

        async def handle_bars(trade): #TBD
            print('handle_trades', trade.price)

        async def handle_news(news): #TBD
            print('handle_trades', news)
        
        async def handle_crypto(crypto): #TBD
            print('handle_crypto', crypto)

        # #self.sds.subscribe_quotes(handle_quotes, *self.stocks)
        # self.ts.subscribe_trade_updates(handle_trade_updates)
        # self.ts.run()
        # # with concurrent.futures.ThreadPoolExecutor() as executor:
        # #     f1 = executor.submit(self.ts.run)
        # #     f2 = executor.submit(self.sds.run)

if __name__ == '__main__':
    trader = My()
    trader.start_trading()