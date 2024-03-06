from alpaca.trading.client import TradingClient
from alpaca.data.live import StockDataStream
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import MarketOrderRequest, ClosePositionRequest, GetOrdersRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus
import constants
from datetime import datetime, timedelta 
import time
import concurrent.futures
from threading import Event


initial_qty = 10
target_price = 0.05
exp = [1<<exponent for exponent in range(20)]

class Position(object):
    def __init__(self):
        self.qty_available = 0
        self.entry_price = 0
        self.exit_qty = 0
        self.exit_price = 0
        self.entries=[]
        self.qty = initial_qty
        self.last_price = 0

class My(object):
    def __init__(self):
        self.stocks = ('TQQQ', 'SQQQ',)
        self.positions = {}
        self.start_equity = 0
        self.last_equity = 0
        self.now = ''
        self.last_order_time = None
        self.live = False
        
        if self.live:
            self.key_id = constants.ALPACA_API_KEY_LIVE
            self.secret_key = constants.ALPACA_SECRET_KEY_LIVE
        else:
            self.key_id = constants.ALPACA_API_KEY4
            self.secret_key = constants.ALPACA_SECRET_KEY4
        
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
            for e in exp:
                if position.qty/initial_qty > e:
                    diff += 0.01

        #print(f'diff={diff}')
        #print(f'{symbol} {ask_price} <= {last_price}-{target_price}-{diff} qty {position.qty} last_price {last_price}')
        if last_price == 0 or ask_price <= last_price - target_price - diff:
            
            #print(f'{symbol} buy condition {last_price} == 0 or  {ask_price}  < {last_price - target_price - diff}')
            if float(self.trading_client.get_account().regt_buying_power) < ask_price * position.qty:
                print(f'{self.now} {symbol} {ask_price} {position.entry_price} {position.qty} No buying power. Skipping..')
                #avoid get_account call repeatedly
                position.last_price = ask_price
                return
            
            try:
                position.last_price = ask_price
                self.last_order_time = datetime.now()
                self.trading_client.submit_order(order_data=MarketOrderRequest(
                    symbol=symbol, qty=position.qty, side=OrderSide.BUY, time_in_force=TimeInForce.DAY))
            except Exception as e:
                print(symbol, ask_price, position.entry_price, position.qty,  e)
                print('after exception -', symbol, position.last_price)
            return
        
        if position.exit_qty > 0 and bid_price >= position.exit_price:
            #print(f'{symbol} sell condition {position.qty_available} > 0 and  {bid_price} > {position.entry_price + target_price}')
            try:
                self.last_order_time = datetime.now()
                #self.trading_client.close_position(symbol, close_options=ClosePositionRequest(percentage=100)
                order = self.trading_client.submit_order(MarketOrderRequest(
                    symbol = symbol, side = 'sell', qty = position.exit_qty, time_in_force = 'day'))
                #reset
                position.last_price = bid_price
                #position.qty_available -= position.exit_qty # remaining qty. These 2 lines needed?
                #position.qty = max(position.qty_available, initial_qty) # for next buy, double the position
            except Exception as e:
                print(symbol, position.exit_qty, 'exit order error', e)

    def check_market_open(self):
        clock = self.trading_client.get_clock()
        
        if not clock.is_open:
            next_open = clock.next_open
            now = datetime.now(tz=next_open.tzinfo)
            secs = (next_open - now).total_seconds()
            print('Sleeping until market open..')
            time.sleep(secs+5)
    
    def check_market_close(self):
        clock = self.trading_client.get_clock()
        if clock.is_open:
            next_close = clock.next_close
            now = datetime.now(tz=next_close.tzinfo)
            #next_close = datetime.now(tz=now.tzinfo)+timedelta(seconds=75)
            secs = (next_close - now).total_seconds()
            print('waiting until market close time..')
            time.sleep(secs-30)
    
    def stop_trading(self):
        self.check_market_close()
        self.ts.stop()
        self.ws.stop()
        orders = self.trading_client.get_orders(GetOrdersRequest(symbols=self.stocks))
        print('Cancelling pending orders..')
        for order in orders:
            try:
                self.trading_client.cancel_order_by_id(order.id)
                print(f'cancel {symbol} {order.id}')
            except:
                pass
        print('submitting target orders for open positions')
        for symbol in self.stocks:
            try:
                position = self.positions[symbol]
                order = self.trading_client.submit_order(LimitOrderRequest(
                    symbol=symbol, qty=position.qty_available, side='sell',
                    limit_price = round(position.entry_price + target_price, 2), 
                    time_in_force='day', extended_hours=True))
                print(f'sell limit {symbol} {position.qty_available} {order.id}')
            except:
                pass

    def calc_exit(self, symbol):
        position = self.positions[symbol]
        if len(position.entries) > 0:
            cost_basis = sum([d['qty'] * d['price'] for d in position.entries[-2:]])
            exit_qty = sum([d['qty'] for d in position.entries[-2:]])
            exit_price = round(cost_basis / exit_qty + target_price, 2)
            position.exit_qty = exit_qty
            position.exit_price = exit_price
            position.entry_price = round(sum([d['qty'] * d['price'] for d in position.entries]) / sum([d['qty'] for d in position.entries]), 2)
        else:
            position.exit_qty = 0
            position.exit_price = 0
            position.entry_price = 0
            position.last_price = 0
            #self.positions[symbol] = position # need to reassign object back?
        
        print('after calc_exit* ', symbol, vars(self.positions[symbol]))

    def start_trading(self):
        print(f'Start trading.. live={self.live}')
        self.check_market_open()
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
                position.last_price = position.entry_price #TODO write to file and fetch next run for more accurate exits
                position.qty_available = int(acct_position.qty)
                position.qty = max(position.qty_available, initial_qty)
                position.entries.append({'qty':position.qty_available, 'price': position.entry_price})
                self.calc_exit(symbol)
                print(f'Existing position: {symbol} {position.qty} {position.last_price}')
            except Exception as e:
                print('Exception s_t:', e)

        async def handle_quotes(data):
            now = datetime.now()
            if self.last_order_time is not None and now - self.last_order_time < timedelta(seconds=1):
                return
            
            bid_price, ask_price = float(data.bid_price), float(data.ask_price)
            if bid_price == 0 or ask_price == 0:
                return

            self.now = now.time().strftime('%H:%M:%S')
            self.process_trade(data.symbol, bid_price, ask_price)

        async def handle_trade_updates(data):
            # if data.event in ['fill', 'partial_fill']:
            #     print(data.event, data)
            if data.event == 'fill':
                symbol, side, fill_price = data.order.symbol, data.order.side, round(float(data.order.filled_avg_price),2)
                account = self.trading_client.get_account()
                current_equity = float(account.equity)
                position = self.positions[symbol]
                position.qty_available = data.position_qty
                position.qty = max(position.qty_available, initial_qty)

                # try:
                #     acct_position = self.trading_client.get_open_position(symbol)
                #     position.entry_price = float(acct_position.avg_entry_price) #TODO calculate from entries
                # except Exception as e: #if no position
                #     pass

                if side == 'buy':
                    position.entries.append({'qty': float(data.order.qty), 'price': fill_price}) #data.order.filled_qty?
                elif side == 'sell':
                    try:
                        position.entries.pop()
                        position.entries.pop()
                    except Exception as e:
                        print('Less than 2 entries', e)
                
                self.calc_exit(symbol)
                #doublecheck data.qty in partial_fill
                print(f'{self.now} {side} {symbol} {fill_price} / {round(position.entry_price, 2)} ' \
                f'qty: {data.order.qty} / {position.qty_available}  PnL: ${round(current_equity - self.start_equity, 2)} / ' \
                    f'${round(current_equity - self.last_equity, 2)}')

        self.ws.subscribe_quotes(handle_quotes, *self.stocks)
        self.ts.subscribe_trade_updates(handle_trade_updates)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.submit(self.ts.run)
            executor.submit(self.ws.run)
            executor.submit(self.stop_trading)

if __name__ == '__main__':
    trader = My()
    trader.start_trading()