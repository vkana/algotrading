import alpaca_trade_api as tradeapi
import constants
from alpaca_trade_api.stream import Stream
from datetime import datetime 
import time



initial_qty = 5
now = ''

class Position(object):
    def __init__(self):
        self.qty = initial_qty
        self.entry_price = 0
        self.qty_available = 0
        self.last_price = 0
        self.buy_order_id = '' #track open order
        self.sell_order_id = ''

class My(object):
    def __init__(self):
        self.key_id = constants.ALPACA_API_KEY
        self.secret_key = constants.ALPACA_SECRET_KEY
        self.base_url = constants.base_url
        self.stocks = ('TQQQ', 'SQQQ')
        self.positions = {}
        self.target_price = 0.05
        self.start_equity = 0
        self.last_equity = 0
        self.live = False
        self.now = ''

        if self.live:
            self.base_url = constants.base_url_live
            self.key_id = constants.ALPACA_API_KEY_LIVE
            self.secret_key = constants.ALPACA_SECRET_KEY_LIVE

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
            #,websocket_params =  {'ping_interval': 1}
        )
    
    def process_trade(self, symbol, bid_price, ask_price):
        
        position = self.positions[symbol]
        last_price = position.last_price
        
        if position.buy_order_id == '' and (last_price == 0 or ask_price <= last_price - self.target_price) :
            #print(f'Buy condition: {symbol} {position.qty} {ask_price} <= {position.last_price - self.target_price}')
            if float(self.api.get_account().regt_buying_power) < ask_price * position.qty:
                print(f'{self.now} {symbol} {ask_price} {position.entry_price} {position.qty} No buying power. Skipping..')
                #avoid get_account call repeatedly
                position.last_price = ask_price
                return
            
            try:
                position.last_price = ask_price
                buyorder = self.api.submit_order(symbol, position.qty, 'buy', type='limit', time_in_force='ioc', limit_price=ask_price, extended_hours=True)
                position.buy_order_id = buyorder.id
                #position.qty *= 2 #move it to trade_updates
            except Exception as e:
                print(symbol, ask_price, position.entry_price, position.qty,  e)
                print('after exception -', symbol, position.last_price)
            return
        
        # if position.qty_available > 0 and bid_price >= position.entry_price + self.target_price:
        #     try:
        #         #self.api.submit_order(symbol, position.qty_available, 'sell', 'market', 'da
        #         sellorder = self.api.submit_order(symbol, position.qty, 'sell', type='limit', time_in_force='day', limit_price=bid_price, extended_hours=True)
        #         #self.api.close_position(symbol)
        #         #reset
        #         position.last_price = 0
        #         position.qty_available = 0
        #         position.qty = initial_qty
        #     except Exception as e:
        #         print(symbol, e)
    
    def start_trading(self):
        print(f'Start trading.. live={self.live}')
        account = self.api.get_account()
        self.last_equity = float(account.last_equity)
        self.start_equity = float(account.equity)
        #print([s.symbol for s in [asset for asset in self.api.list_assets(status="active") if asset.tradable]])
        for symbol in self.stocks:
            self.positions[symbol] = Position()
            position = self.positions[symbol]
            try:
                acct_position = self.api.get_position(symbol)
                #if position exists on start
                position.entry_price = round(float(acct_position.avg_entry_price), 2)
                position.last_price = position.entry_price
                position.qty_available = int(acct_position.qty_available)
                position.qty = position.qty_available
                print(f'Existing position: {symbol} {position.qty} {position.last_price}')
            except:
                position.entry_price = 0
                position.qty_available = 0

        async def handle_quotes(quote):
            self.now = datetime.now().time().strftime('%H:%M:%S')
            #print(self.now, quote.timestamp.strftime('%H:%M:%S'))
            if (float(quote.ask_price) == 0 or float(quote.bid_price) == 0):
                return
            #print(f'{datetime.datetime.now()} {quote.symbol} {quote.bid_price} {quote.ask_price}')
            self.process_trade(quote.symbol, float(quote.bid_price), float(quote.ask_price))

        async def handle_trade_updates(data):
            if data.event == 'fill' or data.event == 'partial_fill':
                symbol = data.order['symbol']
                price = data.order['filled_avg_price']
                side = data.order['side']
                account = self.api.get_account()
                current_equity = float(account.equity)
                #self.positions[symbol] = float(data.position_qty)
                position = self.positions[symbol]

                if side == 'sell':
                    print('sell order complete')
                    position.sell_order_id = ''
                
                try:
                    acct_position = self.api.get_position(symbol)
                    position.entry_price = round(float(acct_position.avg_entry_price), 2)
                    position.qty_available = int(acct_position.qty_available)

                    if data.id == position.buy_order_id: #open position means it's a buy order
                        print('buy order complete.')
                        position.buy_order_id = ''

                    if position.sell_order_id != '': #open sell order exists, update exit price and qty
                        print('replacing sell order.. ')
                        self.api.replace_order(position.sell_order_id, position.qty_available, position.entry_price + self.target_price)
                    else:
                        print('creating sell order')
                        sell_order = self.api.submit_order(symbol, position.qty_available, 'sell', 'limit', 'day', position.entry_price + self.target_price, extended_hours=True)
                        position.sell_order_id = sell_order.id
                except Exception as e:
                    print(symbol, position.last_price, position.entry_price, position.qty_available,  e)
                    position.entry_price = 0
                    position.qty_available = 0
                    position.qty = initial_qty
                    position.last_price = 0
                
                print(f'{self.now} {side} {symbol} {price} / {position.entry_price} qty: {data.qty} / {position.qty_available} eq: {current_equity} PnL: ${round(current_equity - self.start_equity, 2)} / ${round(current_equity - self.last_equity, 2)}')

        async def handle_bars(trade): #TBD
            print('handle_trades', trade.price)
            print(self.conn)

        async def handle_news(news): #TBD
            print('handle_trades', news)
        
        async def handle_crypto(crypto): #TBD
            print('handle_crypto', crypto)

        self.conn.subscribe_quotes(handle_quotes, *self.stocks)
        self.conn.subscribe_trade_updates(handle_trade_updates)
        #self.conn.subscribe_news(handle_news, *self.stocks)
        #self.conn.subscribe_crypto_trades(handle_crypto, 'BTCUSD')

        self.conn.run()
        

if __name__ == '__main__':
    trader = My()
    trader.start_trading()