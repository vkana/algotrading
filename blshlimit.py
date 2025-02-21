import logging
import time
import math
import pytz
import concurrent.futures
from datetime import datetime, timedelta, time as dt_time
from alpaca.data import StockHistoricalDataClient, StockLatestTradeRequest, StockLatestQuoteRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import (MarketOrderRequest, ReplaceOrderRequest,
    GetOrdersRequest, LimitOrderRequest, GetCalendarRequest)
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
import constants

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-5s %(funcName)-20s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler("trades_blshlimit.log"),logging.StreamHandler()])
logger = logging.getLogger(__name__)

QTY = 5
TARGET = 0.02

def ceil2 (number):
    return math.ceil(float(number) * 100) / 100

def floor2 (number):
    return math.floor(float(number) * 100) / 100

class Position:
    def __init__(self):
        self.buy_order_id = ''
        self.sell_order_id = ''

class Trader:
    def __init__(self):
        self.symbols = ('F', 'SOFI', 'CLSK', 'PBR', 'LUNR', 'NU', 'RIOT', 'SNAP', 'RIVN', 'WBD', 'AMD',)
        self.symbols_exit = ('AMD',)
        self.live = False
        self.start_equity = 0
        self.positions = {}

        if self.live:
            self.key_id = constants.ALPACA_API_KEY_LIVE
            self.secret_key = constants.ALPACA_SECRET_KEY_LIVE
        else:
            self.key_id = constants.ALPACA_API_KEY2
            self.secret_key = constants.ALPACA_SECRET_KEY2
        
        self.quote_client = StockHistoricalDataClient(self.key_id, self.secret_key)
        self.trading_client = TradingClient(self.key_id, self.secret_key, paper = not self.live)
        self.ts = TradingStream(self.key_id, self.secret_key, paper = not self.live)

    def last_entry_price(self, symbol):
        request_params = GetOrdersRequest(
            status=QueryOrderStatus.CLOSED,
            limit=1,
            symbols=(symbol,),
            side= OrderSide.BUY
        )
        orders = self.trading_client.get_orders(request_params)

        if orders:
            latest_trade = orders[0]
            return(latest_trade.limit_price or latest_trade.filled_avg_price)
        else:
            return 0
    
    def get_current_price(self, symbol):
        quote = self.quote_client.get_stock_latest_quote(request_params= StockLatestQuoteRequest(symbol_or_symbols= symbol))
        current_price = quote[symbol].ask_price
        if current_price == 0:
            current_price = quote[symbol].bid_price + 1
        
        if current_price == 0:
            latest_trade = self.quote_client.get_stock_latest_trade(request_params=StockLatestTradeRequest(symbol_or_symbols= symbol))
            current_price = latest_trade[symbol].price + 1
            print(latest_trade)
        return ceil2(current_price)

    def cancel_open_orders(self, symbols):
        if (isinstance(symbols, str)):
            symbols_to_cancel = (symbols,)
        
        open_orders = self.trading_client.get_orders(GetOrdersRequest(symbols=symbols_to_cancel, status=QueryOrderStatus.OPEN))
        for order in open_orders:
            logger.debug('cancelling %s %s %s %s', len(open_orders), order.symbol, order.status.name, order.side.name)
            try:
                self.trading_client.cancel_order_by_id(order.id)
            except Exception as e:
                logger.error('Unable to cancel open order %s %s %s %s', order.symbol, order.id, order.type, order.side, e, e.__traceback__.tb_lineno)
                logger.error('%s %s', order.symbol, e, e.__traceback__.tb_lineno)

    def next_entry(self, symbol, qty, price):
        try :
            order = self.trading_client.submit_order(LimitOrderRequest(symbol = symbol, qty = qty, limit_price = price, side = OrderSide.BUY, extended_hours = True, time_in_force = TimeInForce.DAY ))
            self.positions[symbol].buy_order_id = order.id
            logger.debug('%s %s %s %s %s %s', order.symbol, order.side.name, order.limit_price or "", order.qty, order.order_type.name, order.status.name)
        except Exception as e:
            logger.error('%s %s %s', symbol, e, e.__traceback__.tb_lineno)

    def fresh_entry(self, symbol, qty = QTY):
        order_request = None
        try:
            if self.trading_client.get_clock().is_open:
                order_request = MarketOrderRequest(symbol = symbol, qty = qty, side = OrderSide.BUY, time_in_force = TimeInForce.DAY)
                order = self.trading_client.submit_order(order_request)
                self.positions[symbol].buy_order_id = order.id
                
            else:
                price = self.get_current_price(symbol)
                order_request = LimitOrderRequest(symbol = symbol, qty = qty, limit_price = price, side = OrderSide.BUY, extended_hours = True, time_in_force = TimeInForce.DAY )
                order = self.trading_client.submit_order(order_request)
            
            logger.debug('%s %s %s %s %s %s', order.symbol, order.side.name, order.limit_price or "", order.qty, order.order_type.name, order.status.name)
        except Exception as e:
            logger.error('%s %s %s %s', symbol, e, e.__traceback__.tb_lineno, order_request, e.__traceback__.tb_lineno)

    def target_order(self, symbol, qty, price):
        try :
            order = self.trading_client.submit_order(LimitOrderRequest(symbol = symbol, qty = qty, limit_price = price, side = OrderSide.SELL, extended_hours = True, time_in_force = TimeInForce.DAY))
            self.positions[symbol].sell_order_id = order.id
            logger.debug('%s %s %s %s %s %s', order.symbol, order.side.name, order.limit_price or "", order.qty, order.order_type.name, order.status.name)
        except Exception as e:
            logger.error('%s %s', symbol, e, e.__traceback__.tb_lineno)

    
    def replace_order(self, symbol, order_id, qty, price):
        try :
            logger.debug('replacing order %s', symbol)
            order = self.trading_client.replace_order_by_id(order_id, ReplaceOrderRequest(qty = qty, limit_price = price ))
            self.positions[symbol].sell_order_id = order.id
            logger.debug('%s %s %s %s %s %s', order.symbol, order.side.name, order.limit_price or "", order.qty, order.order_type.name, order.status.name)
        except Exception as e:
            logger.error('%s %s', symbol, e, e.__traceback__.tb_lineno)
    

    def check_market_open(self):
        tz = pytz.timezone('US/Eastern')
        now = datetime.now(tz = tz)
        next_open = None
        next_close = None
        
        calendar = self.trading_client.get_calendar(GetCalendarRequest(start=now.date(), end=now.date() + timedelta(days=7)))
        
        if calendar[0].date == now.date():
            if now.time() < dt_time(4,0): #trading day before open, today
                next_open = calendar[0].open
            elif now.time() > dt_time(20,0): #trading day after close, next trading day
                next_open = calendar[1].open
            else:
                next_close = calendar[0].close
        else:
            #0 is next trading day
            next_open = calendar[0].open

        if next_open is not None:
            next_open = tz.localize(next_open) - timedelta(minutes=330)
            secs = (next_open - now).total_seconds()
            logger.info(f'Waiting {secs} seconds until market open..')
            time.sleep(secs)
    
    def check_market_close(self):
        tz = pytz.timezone('US/Eastern')
        now = datetime.now(tz = tz)
        
        calendar = self.trading_client.get_calendar(GetCalendarRequest(start=now.date(), end=now.date() + timedelta(days=7)))
        
        if calendar[0].date == now.date() and dt_time(4,0) <= now.time() < dt_time(20,0):
            next_close = tz.localize(calendar[0].close) + timedelta(minutes=240)
            secs = (next_close - now).total_seconds() - 30
            logger.info(f'Waiting {secs} seconds until market close..')
            time.sleep(secs)

    def stop_trading(self):
        self.check_market_close()
        logger.info('Stop trading..')
        self.ts.stop()
        orders = self.trading_client.get_orders(GetOrdersRequest(symbols=self.symbols))
        logger.info('Cancelling pending orders..')
        self.cancel_open_orders(self.symbols)
        logger.info('Submitting target orders for open positions')
    
        for symbol in self.symbols:
            try:
                position = self.positions[symbol]
                self.target_order(symbol=symbol, qty=position.qty_available, price = round(position.entry_price + TARGET,2))
            except:
                pass
    
    def trade(self):
        logger.info('Trade start')
        for symbol in self.symbols:
            self.positions[symbol] = Position()
            try:
                self.cancel_open_orders(symbol)
                acct_position = self.trading_client.get_open_position(symbol)
                acct = self.trading_client.get_account()
                self.start_equity = float(acct.equity)
                todays_pl = ceil2(float(acct.equity) - float(acct.last_equity))
                current_pl = ceil2(float(acct.equity) - float(self.start_equity))
                
                logger.info('* %-4s %s %s PL %s/%s', symbol, acct_position.qty_available, ceil2(acct_position.avg_entry_price), current_pl, todays_pl)
                entry_price = float(acct_position.avg_entry_price)
                qty_available = acct_position.qty_available
                self.target_order(symbol, qty_available, ceil2(entry_price + TARGET))
                last_entry = self.last_entry_price(symbol) or acct_position.current_price
                self.next_entry(symbol, QTY, floor2(float(last_entry) - TARGET))
                
            except Exception as e:
                logger.error('%s %s %s',symbol, e, e.__traceback__.tb_lineno)
                self.cancel_open_orders(symbol)
                #print('processing 3', symbol)
                if (symbol not in self.symbols_exit):
                    self.fresh_entry(symbol)

    def start_trading(self):
        self.check_market_open()

        async def handle_trade_updates(data):
            #print(data)
            logger.debug('Received event: %s %s %s %s %s %s filled %s',data.event, data.order.symbol, data.order.side.name, data.order.qty, data.price, data.position_qty, data.order.filled_qty)
            if data.event == 'fill' and data.order.symbol in self.symbols:
                symbol = data.order.symbol
                logger.debug('*FILL* %s %s %s %s %s %s', symbol, data.order.side.name, data.order.filled_avg_price, data.order.order_type.name, int(data.qty), int(data.position_qty))
                time.sleep(1)
                try:
                    #self.cancel_open_orders(symbol)
                    acct = self.trading_client.get_account()
                    equity = float(acct.equity)
                    todays_pl = ceil2(equity - float(acct.last_equity))
                    current_pl = ceil2(equity - float(self.start_equity))

                    if data.order.side == OrderSide.BUY:
                        acct_position = self.trading_client.get_open_position(symbol)
                        entry_price = float(data.order.filled_avg_price)
                        qty_available = data.position_qty
                        pos_avg_price = float(acct_position.avg_entry_price)
                        
                        if self.positions[symbol].sell_order_id:
                            self.replace_order(symbol, self.positions[symbol].sell_order_id, qty_available, ceil2(pos_avg_price + TARGET))
                        else:
                            self.target_order(symbol, qty_available, ceil2(pos_avg_price + TARGET))
                        
                        self.next_entry(symbol, QTY, floor2(entry_price - TARGET))
                        
                        logger.info('+ %-4s %s %s/%s PL %s/%s', symbol, acct_position.qty, ceil2(entry_price), ceil2(acct_position.avg_entry_price), current_pl, todays_pl)
                        
                    elif data.order.side == OrderSide.SELL:
                        self.positions[symbol].sell_order_id = ''
                        try:
                            logger.debug('%s cancelling buy order', symbol)
                            self.trading_client.cancel_order_by_id(self.positions[symbol].buy_order_id)
                        except Exception as e:
                            logger.error('%s %s %s', symbol, e, e.__traceback__.tb_lineno)
                        if (symbol not in self.symbols_exit):
                            self.fresh_entry(symbol)
                        logger.info('- %-4s %s %s PL %s/%s', symbol, int(data.qty), data.price, current_pl, todays_pl)
                except Exception as e:
                    logger.error('%s %s %s', symbol, e, e.__traceback__.tb_lineno)

        logger.info('subscribing to trade updates websocket')
        self.ts.subscribe_trade_updates(handle_trade_updates)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.submit(self.ts.run)
            executor.submit(self.trade)
            executor.submit(self.stop_trading)



if __name__ == '__main__':
    trader = Trader()
    trader.start_trading()
