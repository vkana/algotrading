import logging
import concurrent.futures
from datetime import datetime, timedelta
import time
import platform
from alpaca.trading.client import TradingClient
from alpaca.data.live import StockDataStream
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import (MarketOrderRequest, ClosePositionRequest,
    GetOrdersRequest, LimitOrderRequest)
from alpaca.trading.enums import OrderSide, TimeInForce
import constants

try:
    import winsound
except ImportError:
    pass

#from threading import Event

#%(funcName)s 
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(funcName)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler("trades.log"), logging.StreamHandler()])
logger = logging.getLogger(__name__)


INITIAL_QTY = 10
exp = [1<<exponent for exponent in range(20)]


class Position:
    def __init__(self):
        self.qty = INITIAL_QTY
        self.entry_price = 0
        self.qty_available = 0
        self.last_price = 0


class My:
    def __init__(self):
        self.stocks = ('TQQQ','SQQQ')
        self.positions = {}
        self.target_price = 0.05
        self.start_equity = 0
        self.last_equity = 0
        self.now = ''
        self.last_order_time = None
        self.live = True

        if self.live:
            self.key_id = constants.ALPACA_API_KEY_LIVE
            self.secret_key = constants.ALPACA_SECRET_KEY_LIVE
        else:
            self.key_id = constants.ALPACA_API_KEY2
            self.secret_key = constants.ALPACA_SECRET_KEY2

        self.trading_client = TradingClient(self.key_id, self.secret_key, paper = not self.live)
        self.ws = StockDataStream(self.key_id, self.secret_key)
        self.ts = TradingStream(self.key_id, self.secret_key, paper = not self.live)

    def process_trade(self, symbol, bid_price, ask_price):
        position = self.positions[symbol]
        last_price = position.last_price
        diff = 0
        try:
            diff = exp.index(position.qty/10) / 50
        except:
            for e in exp:
                if position.qty/INITIAL_QTY > e:
                    diff += 0.02

        if last_price == 0 or ask_price <= last_price - self.target_price - diff:

            buying_power = float(self.trading_client.get_account().regt_buying_power)
            buying_power = min(buying_power, 30000)

            if buying_power < ask_price * position.qty:
                logger.info(f'{symbol} {ask_price} {position.entry_price} {position.qty} No buying power. Skipping..')
                #avoid get_account call repeatedly
                position.last_price = ask_price
                return

            try:
                position.last_price = ask_price
                self.last_order_time = datetime.now()
                self.trading_client.submit_order(order_data=MarketOrderRequest(symbol=symbol, qty=position.qty, side=OrderSide.BUY, time_in_force=TimeInForce.DAY))
                if platform.system() == 'Windows':
                    winsound.Beep(2500,10)
            except Exception as e:
                logger.error(f'{symbol} {ask_price} {position.entry_price} {position.qty} {e} {e.__traceback__.tb_lineno}') 
                logger.error(f'After exception - {symbol} {position.last_price} {e.__traceback__.tb_lineno}')
            return
        
        if position.qty_available > 0 and bid_price >= position.entry_price + self.target_price:
            #print(f'{symbol} sell condition {position.qty_available} > 0 and  {bid_price} > {position.entry_price + self.target_price}')
            try:
                #self.trading_client.submit_order(symbol, position.qty_available, 'sell', 'market', 'day')
                self.last_order_time = datetime.now()
                self.trading_client.close_position(symbol, close_options=ClosePositionRequest(percentage='100'))
                if platform.system() == 'Windows':
                    winsound.Beep(1000,10)
                #reset
                position.last_price = 0
                position.qty_available = 0
                position.qty = INITIAL_QTY
            except Exception as e:
                logger.error(f'{symbol} {e} {e.__traceback__.tb_lineno}')
    
    def get_positions(self):
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
                logger.info(f'Existing position: {symbol} {position.qty} {position.last_price}')
            except Exception as e:
                position.entry_price = 0
                position.qty_available = 0
                logger.error(f'Exception : {symbol} {e} {e.__traceback__.tb_lineno}')

    def check_market_open(self):
        clock = self.trading_client.get_clock()

        if not clock.is_open:
            next_open = clock.next_open
            now = datetime.now(tz=next_open.tzinfo)
            secs = (next_open - now).total_seconds()
            logger.info('Waiting until market open..')
            time.sleep(secs + 5)

    def check_market_close(self):
        clock = self.trading_client.get_clock()
        if clock.is_open:
            next_close = clock.next_close
            now = datetime.now(tz=next_close.tzinfo)
            #next_close = datetime.now(tz=now.tzinfo)+timedelta(seconds=75)
            secs = (next_close - now).total_seconds()
            logger.info('Waiting until market close time..')
            time.sleep(secs-30)

    def cancel_pending_orders(self, symbols):
        orders = self.trading_client.get_orders(GetOrdersRequest(symbols=symbols))
        logger.info('Cancelling pending orders..')
        for order in orders:
            try:
                self.trading_client.cancel_order_by_id(order.id)
                logger.info(f'Cancel {order.symbol} {order.id}')
            except:
                pass
    
    def submit_target_orders(self, symbols):
        logger.info('Submitting target orders for open positions')
        for symbol in symbols:
            try:
                position = self.positions[symbol]
                if position and position.qty_available > 0:
                    orders = self.trading_client.get_orders(GetOrdersRequest(symbols = [symbol], side = OrderSide.SELL, status= 'open'))
                    if not orders:
                        limit_price = round(position.entry_price + self.target_price,2)

                        self.trading_client.submit_order(LimitOrderRequest(symbol=symbol, qty=position.qty_available, side=OrderSide.SELL,limit_price = limit_price, time_in_force=TimeInForce.DAY, extended_hours=True))
                        logger.info(f'Sell limit {symbol} {position.qty_available} {limit_price}')
            except Exception as e:
                logger.error(f'{symbol} {e} {e.__traceback__.tb_lineno}')
    
    def stop_trading(self):
        self.check_market_close()
        self.ts.stop()
        self.ws.stop()
        self.submit_target_orders(self.stocks)

    def start_trading(self):
        logger.info(f'Start trading.. live={self.live}')
        self.get_positions()
        
        if not self.trading_client.get_clock().is_open:
            self.submit_target_orders(self.stocks)
        
        self.check_market_open()
        self.cancel_pending_orders(self.stocks)
        self.get_positions()    #to get latest positions start of day
        account = self.trading_client.get_account()
        self.last_equity = float(account.last_equity)
        self.start_equity = float(account.equity)

        async def handle_quotes(data):
            now = datetime.now()
            if self.last_order_time is not None and now - self.last_order_time < timedelta(seconds=3):
                return

            bid_price, ask_price = float(data.bid_price), float(data.ask_price)
            if bid_price == 0 or ask_price == 0:
                return

            self.now = now.time().strftime('%H:%M:%S')
            self.process_trade(data.symbol, bid_price, ask_price)

        async def handle_trade_updates(data):
            if data.event in ('fill', 'partial_fill'):
                symbol, side, price = data.order.symbol, data.order.side, data.order.filled_avg_price
                account = self.trading_client.get_account()
                current_equity = float(account.equity)
                position = self.positions[symbol]
                try:
                    acct_position = self.trading_client.get_open_position(symbol)
                    position.entry_price = float(acct_position.avg_entry_price)
                    position.qty_available = int(acct_position.qty)
                    position.qty = position.qty_available if position.qty_available != 0 else INITIAL_QTY
                except:
                    position.entry_price = 0
                    position.qty_available = 0
                    position.qty = INITIAL_QTY
                    position.last_price = 0

                logger.info(f'{side.name} {symbol} {round(float(price),2)} / {round(position.entry_price, 2)} qty: {data.qty} / {position.qty_available}  PnL: ${round(current_equity - self.start_equity, 2)} / ${round(current_equity - self.last_equity, 2)} {"partial" if data.event == "partial_fill" else ""}')
                # logger.info('%s %s %.2f / %.2f qty: %d / %d PnL: %.2f / %.2f %s', side, symbol, round(float(price),2),
                #     round(position.entry_price, 2), data.qty, position.qty_available, round(current_equity - self.start_equity, 2), 
                #     round(current_equity - self.last_equity, 2), "partial" if data.event == "partial_fill" else "")
        # async def handle_bars(trade): #TBD
        #     print('handle_bars', trade.price)

        # async def handle_news(news): #TBD
        #     print('handle_news', news)

        # async def handle_crypto(crypto): #TBD
        #     print('handle_crypto', crypto)

        self.ws.subscribe_quotes(handle_quotes, *self.stocks)
        self.ts.subscribe_trade_updates(handle_trade_updates)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.submit(self.ts.run)
            executor.submit(self.ws.run)
            executor.submit(self.stop_trading)


if __name__ == '__main__':
    trader = My()
    trader.start_trading()
