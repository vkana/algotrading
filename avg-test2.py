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
from pprint import pprint



exp = [1<<exponent for exponent in range(20)]

class Position(object):
    def __init__(self):
        self.next_qty = initial_qty
        self.entry_price = 0
        self.qty_available = 0
        self.last_price = 0
        self.entries = []
        self.next_order_id = ''
        self.exit_order_id = ''
    
    def __str__(self) -> str:
        return vars(self)


def initialize():
    account_positions = trading_client.get_all_positions()
    open_orders = trading_client.get_orders(GetOrdersRequest(symbols=symbols))    
    print('open orders', open_orders)
    for symbol in symbols:
        positions[symbol] = Position()
        position = positions[symbol]
        for pos in account_positions:
            if pos.symbol == symbol:
                position.entry_price = float(pos.avg_entry_price)
                position.qty_available = float(pos.qty)
                position.next_qty =  position.qty_available
                position.last_price = position.entry_price
                position.entries = [{'qty': position.qty_available, 'price': position.entry_price}]
                #cancel existing orders
                for o in open_orders:
                    if o.symbol == symbol:
                        print('cancel open order for open position')
                        try:
                            trading_client.cancel_order_by_id(o.id)
                        except Exception as e:
                            print('cancel order error', e)
                #target order for open positions:
                print('closing order for fresh entry order')
                try:
                    order = trading_client.submit_order(LimitOrderRequest(
                        symbol = symbol, side = 'sell', qty = position.qty_available, limit_price = round(position.entry_price + target_price, 2), 
                        type = 'limit', time_in_force = 'day', extended_hours = True))
                    position.exit_order_id = order.id
                except Exception as e:
                    print(symbol, 'new exit order error', e)

                break
        else:
            position.entry_price = 0
            position.qty_available = 0
            position.next_qty =  initial_qty
            position.last_price = 0
            #no position. buy now
            print(symbol, 'no position. fresh entry order')
            try:
                trading_client.submit_order(LimitOrderRequest(
                symbol = symbol, side = 'buy', qty = position.next_qty, limit_price = 99, #like market order 
                type = 'limit', time_in_force = 'day', extended_hours = True))
            except Exception as e:
                print(symbol, 'fresh entry order error', e)
    
    print('end initialize')
    for k, v in positions.items():
        print(k, vars(v))

async def handle_trade_updates(data):
    print('trade update data', data.order.symbol, data.event)
    symbol = data.order.symbol
    position = positions[symbol]

    if data.event == 'fill':
        position.next_qty = data.position_qty if data.position_qty > 0 else initial_qty
        position.qty_available = data.position_qty

        if data.order.side == 'buy':
            print(symbol, 'new buy filled.')
            position.last_price = float(data.order.filled_avg_price)
            position.entries.append({'qty':data.qty, 'price':float(data.order.filled_avg_price)})

            print(symbol, 'positions after new entry', position.entries)
            #next_buy order
            print(symbol, 'submitting next buy order')
            try:
                order = trading_client.submit_order(LimitOrderRequest(
                    symbol = symbol, side = 'buy', qty = position.next_qty, limit_price = round(position.last_price - target_price), 
                type = 'limit', time_in_force = 'day', extended_hours = True))
                position.next_order_id = order.id
            except Exception as e:
                print(symbol, 'next buy order error', e)
            
            #cancel previous exit order
            print(symbol, 'cancelling exit order')
            try:
                trading_client.cancel_order_by_id(position.exit_order_id)
            except Exception as e:
                print(symbol, 'cancel previous exit order error', e)
            
            #calculate average price, qty of last 2 entries
            cost_basis = 0
            exit_qty = 0
            avg_price = 0
            for p in position.entries[:2]:
                cost_basis += p['qty'] * p['price']
                exit_qty += p['qty']
            
            if exit_qty > 0:
                avg_price = round(cost_basis / exit_qty, 2)
                print(f'exit_qty {exit_qty} target_price {target_price}')

            print(symbol, 'submitting new exit order')
            #new exit order
            try:
                order = trading_client.submit_order(LimitOrderRequest(
                    symbol = symbol, side = 'sell', qty = exit_qty, limit_price = round(avg_price + target_price,2), 
                    type = 'limit', time_in_force = 'day', extended_hours = True))
                position.exit_order_id = order.id
            except Exception as e:
                print(symbol, 'new exit order error', e)
            
            print(symbol, 'submitting next entry order')
            #next entry order
            try:
                order = trading_client.submit_order(LimitOrderRequest(
                    symbol = symbol, side = 'buy', qty = position.next_qty, limit_price = round(position.last_price - target_price,2), 
                    type = 'limit', time_in_force = 'day', extended_hours = True))
                position.next_order_id = order.id
            except Exception as e:
                print(symbol, 'next buy order error', e)

        elif data.order.side == 'sell':
            print(symbol, 'sell filled')
            position.last_price = float(data.order.filled_avg_price)
            #remove last 2 entries from array
            try:
                position.entries.pop()
                position.entries.pop()
            except:
                print('less than 2 entries')
            
            print(symbol, 'positions after pop', position.entries)

            
            if position.qty_available == 0:
                print(symbol, 'no position. submitting fresh entry order (market)')
                try:
                    trading_client.submit_order(LimitOrderRequest(
                    symbol = symbol, side = 'buy', qty = position.next_qty, limit_price = 99, #like market order 
                    type = 'limit', time_in_force = 'day', extended_hours = True))
                except Exception as e:
                    print(symbol, 'fresh entry order error', e)
            else: 
                # next sell order
                #calculate average price, qty of last 2 entries
                cost_basis = 0
                exit_qty = 0
                avg_price = 0
                for p in position.entries[:2]:
                    cost_basis += p['qty'] * p['price']
                    exit_qty += p['qty']
                
                if exit_qty > 0:
                    avg_price = round(cost_basis / exit_qty, 2)
                    print(f'exit_qty {exit_qty} target_price {target_price}')
                #new exit order
                print(symbol, 'submitting new exit order')
                try:
                    order = trading_client.submit_order(LimitOrderRequest(
                        symbol = symbol, side = 'sell', qty = exit_qty, limit_price = round(avg_price + target_price,2), 
                        type = 'limit', time_in_force = 'day', extended_hours = True))
                    position.exit_order_id = order.id
                except Exception as e:
                    print(symbol, 'new exit order error', e)
    
    print('end of trade update')
    for k, v in positions.items():
        print(k, vars(v))


if __name__ == '__main__':
    is_live = False
    symbols = ('TQQQ', 'SQQQ',)
    positions = {}
    initial_qty = 10
    target_price = 0.05
    start_equity = 0
    last_equity = 0
    last_order_time = None

    if is_live:
        key_id = constants.ALPACA_API_KEY_LIVE
        secret_key = constants.ALPACA_SECRET_KEY_LIVE
    else:
        key_id = constants.ALPACA_API_KEY4
        secret_key = constants.ALPACA_SECRET_KEY4

    trading_client = TradingClient(key_id, secret_key, paper = not is_live)
    
    initialize()

    
    #ws = StockDataStream(key_id, secret_key)
    ts = TradingStream(key_id, secret_key, paper = not is_live)
    ts.subscribe_trade_updates(handle_trade_updates)
    ts.run()





