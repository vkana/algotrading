import alpaca_trade_api as tradeapi
import constants
from alpaca_trade_api.stream import Stream
from datetime import datetime 
import time



initial_qty = 10
exp = [1<<exponent for exponent in range(10)]

class Position(object):
    def __init__(self):
        self.qty = initial_qty
        self.entry_price = 0
        self.qty_available = 0
        self.last_price = 0


class My(object):
    def __init__(self):
        self.key_id = constants.ALPACA_API_KEY
        self.secret_key = constants.ALPACA_SECRET_KEY
        self.base_url = constants.base_url
        self.stocks = ('TQQQ', 'SQQQ',)
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
            base_url = self.base_url
            #,websocket_params =  {'ping_interval': 1}
        )
    
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
        
        if last_price == 0 or ask_price <= last_price - self.target_price - diff:
            #print(f'{symbol} buy condition {last_price} == 0 or  {ask_price}  < {last_price - self.target_price - diff}')
            if float(self.api.get_account().regt_buying_power) < ask_price * position.qty:
                print(f'{self.now} {symbol} {ask_price} {position.entry_price} {position.qty} No buying power. Skipping..')
                #avoid get_account call repeatedly
                position.last_price = ask_price
                return
            
            try:
                position.last_price = ask_price
                order = self.api.submit_order(symbol, position.qty, 'buy', 'market', 'day')
                #print(order.id)
                #position.qty *= 2
            except Exception as e:
                print(symbol, ask_price, position.entry_price, position.qty,  e)
                print('after exception -', symbol, position.last_price)
            return
        
        if position.qty_available > 0 and bid_price >= position.entry_price + self.target_price:
            try:
                self.api.close_position(symbol)
                #reset
                position.last_price = 0
                position.qty_available = 0
                position.qty = initial_qty
            except Exception as e:
                print(symbol, e)

    def check_market_open(self):
        clock = self.api.get_clock()
        
        if self.live and not clock.is_open:
            next_open = clock.next_open
            now = datetime.now(tz=next_open.tzinfo)
            secs = (next_open - now).total_seconds()
            print('sleeping until market open..')
            time.sleep(secs)

    def start_trading(self):
        #self.check_market_open()
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
                position.entry_price = float(acct_position.avg_entry_price)
                position.last_price = position.entry_price
                position.qty_available = int(acct_position.qty_available)
                position.qty = position.qty_available
                print(f'Existing position: {symbol} {position.qty} {position.last_price}')
            except:
                position.entry_price = 0
                position.qty_available = 0

        async def handle_trades(trade):
            self.now = datetime.now().time().strftime('%H:%M:%S')
            self.process_trade(trade.symbol, float(trade.bid_price), float(trade.ask_price))

        async def handle_trade_updates(data):
            if data.event == 'fill' or data.event == 'partial_fill':
                symbol, side, price = data.order['symbol'], data.order['side'], data.order['filled_avg_price']
                account = self.api.get_account()
                current_equity = float(account.equity)
                #self.positions[symbol] = float(data.position_qty)
                position = self.positions[symbol]
                try:
                    acct_position = self.api.get_position(symbol)
                    position.entry_price = float(acct_position.avg_entry_price)
                    position.qty_available = int(acct_position.qty_available)
                    position.qty = position.qty_available if position.qty_available != 0 else initial_qty
                except:
                    position.entry_price = 0
                    position.qty_available = 0
                    position.qty = initial_qty
                    position.last_price = 0
                
                print(f'{self.now} {side} {symbol} {round(float(price),2)} / {round(position.entry_price, 2)} qty: {data.qty} / {position.qty_available}  PnL: ${round(current_equity - self.start_equity, 2)} / ${round(current_equity - self.last_equity, 2)}')

        async def handle_bars(trade): #TBD
            print('handle_trades', trade.price)
            print(self.conn)

        async def handle_news(news): #TBD
            print('handle_trades', news)
        
        async def handle_crypto(crypto): #TBD
            print('handle_crypto', crypto)

        self.conn.subscribe_quotes(handle_trades, *self.stocks)
        self.conn.subscribe_trade_updates(handle_trade_updates)
        #self.conn.subscribe_news(handle_news, *self.stocks)
        #self.conn.subscribe_crypto_trades(handle_trades, *self.stocks)

        self.conn.run()
        

if __name__ == '__main__':
    trader = My()
    trader.start_trading()