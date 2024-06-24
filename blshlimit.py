import logging
import time
import math
import concurrent.futures
from alpaca.data import StockHistoricalDataClient, StockLatestTradeRequest, StockLatestQuoteRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import (MarketOrderRequest, ReplaceOrderRequest,
    GetOrdersRequest, LimitOrderRequest)
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
import constants

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-5s %(funcName)-20s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler("trades_blshlimit.log"),logging.StreamHandler()])
logger = logging.getLogger(__name__)

QTY = 1
TARGET = 0.10

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
        self.symbols = ('TSLA','TQQQ', 'INTC', 'SPY', 'AMD')
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

    def get_current_price(self, symbol):
        quote = self.quote_client.get_stock_latest_quote(request_params= StockLatestQuoteRequest(symbol_or_symbols= symbol))
        return ceil2(quote[symbol].ask_price)

    def cancel_open_orders(self, symbol):
        open_orders = self.trading_client.get_orders(GetOrdersRequest(symbols=[symbol], status=QueryOrderStatus.OPEN))
        for order in open_orders:
            logger.debug('cancelling %s %s %s %s', len(open_orders), order.symbol, order.status.name, order.side.name)
            try:
                self.trading_client.cancel_order_by_id(order.id)
            except Exception as e:
                logger.error('Unable to cancel open order %s %s %s %s', symbol, order.id, order.type, order.side, e)
                logger.error('%s %s', symbol, e)

    def next_entry(self, symbol, qty, price):
        try :
            order = self.trading_client.submit_order(LimitOrderRequest(symbol = symbol, qty = qty, limit_price = price, side = OrderSide.BUY, extended_hours = True, time_in_force = TimeInForce.DAY ))
            self.positions[symbol].buy_order_id = order.id
            logger.debug('%s %s %s %s %s %s', order.symbol, order.side.name, order.limit_price or "", order.qty, order.order_type.name, order.status.name)
        except Exception as e:
            logger.error('%s %s', symbol, e)

    def fresh_entry(self, symbol, qty = QTY):
        try:
            if self.trading_client.get_clock().is_open:
                order = self.trading_client.submit_order(MarketOrderRequest(symbol = symbol, qty = qty, side = OrderSide.BUY, time_in_force = TimeInForce.DAY))
                self.positions[symbol].buy_order_id = order.id
                
            else:
                price = self.get_current_price(symbol)
                order = self.trading_client.submit_order(LimitOrderRequest(symbol = symbol, qty = qty, limit_price = price, side = OrderSide.BUY, extended_hours = True, time_in_force = TimeInForce.DAY ))
            
            logger.debug('%s %s %s %s %s %s', order.symbol, order.side.name, order.limit_price or "", order.qty, order.order_type.name, order.status.name)
        except Exception as e:
            logger.error('%s %s', symbol, e)

    def target_order(self, symbol, qty, price):
        try :
            order = self.trading_client.submit_order(LimitOrderRequest(symbol = symbol, qty = qty, limit_price = price, side = OrderSide.SELL, extended_hours = True, time_in_force = TimeInForce.DAY ))
            self.positions[symbol].sell_order_id = order.id
            logger.debug('%s %s %s %s %s %s', order.symbol, order.side.name, order.limit_price or "", order.qty, order.order_type.name, order.status.name)
        except Exception as e:
            logger.error('%s %s', symbol, e)

    
    def replace_order(self, symbol, order_id, qty, price):
        try :
            logger.debug('replacing order %s', symbol)
            order = self.trading_client.replace_order_by_id(order_id, ReplaceOrderRequest(qty = qty, limit_price = price ))
            self.positions[symbol].sell_order_id = order.id
            logger.debug('%s %s %s %s %s %s', order.symbol, order.side.name, order.limit_price or "", order.qty, order.order_type.name, order.status.name)
        except Exception as e:
            logger.error('%s %s', symbol, e)
    
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
                self.next_entry(symbol, QTY, floor2(float(acct_position.current_price) - TARGET))
                
            except Exception as e:
                logger.error('%s %s',symbol, e)
                self.cancel_open_orders(symbol)
                #print('processing 3', symbol)
                self.fresh_entry(symbol)

    def start_trading(self):
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
                        
                        logger.info('+ %-4s %s %s PL %s/%s', symbol, acct_position.qty, ceil2(acct_position.avg_entry_price), current_pl, todays_pl)
                        
                    elif data.order.side == OrderSide.SELL:
                        self.positions[symbol].sell_order_id = ''
                        try:
                            logger.debug('%s cancelling buy order', symbol)
                            self.trading_client.cancel_order_by_id(self.positions[symbol].buy_order_id)
                        except Exception as e:
                            logger.error('%s %s', symbol, e)
                        self.fresh_entry(symbol)
                        logger.info('- %-4s %s %s PL %s/%s', symbol, int(data.position_qty), data.price, current_pl, todays_pl)
                except Exception as e:
                    logger.error('%s %s', symbol, e)

        logger.info('subscribing to trade updates websocket')
        self.ts.subscribe_trade_updates(handle_trade_updates)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.submit(self.ts.run)
            executor.submit(self.trade)



if __name__ == '__main__':
    trader = Trader()
    trader.start_trading()
