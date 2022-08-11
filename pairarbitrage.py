import alpaca_trade_api as tradeapi
import constants
from alpaca_trade_api.stream import Stream
import time



initial_qty = 5

class Position(object):
    def __init__(self):
        self.qty = initial_qty
        self.entry_price = 0
        self.qty_available = 0
        self.last_price = 0


class My(object):
    def __init__(self):
        self.key_id = constants.ALPACA_API_KEY2
        self.secret_key = constants.ALPACA_SECRET_KEY2
        self.base_url = constants.base_url
        self.stocks = ('TQQQ', 'SQQQ')
        self.positions = {}
        self.target_price = 0.05
        self.start_equity = 0
        self.last_equity = 0
        self.live = False

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
    
    def process_trade(self, symbol, price):
        try:
            qty = float(self.api.get_position(symbol).qty)
        except:
            qty = 0

        try:
            if qty == 0:
                print('opening..')
                self.api.submit_order('TQQQ', side='buy',  notional=30000)
                self.api.submit_order('SQQQ', side='buy', notional=30000)
                self.api.submit_order('SQQQ', qty=10, side='buy', trail_price=0.03 )
                time.sleep(1)

            else:
                unrealized_pl = 0
                positions = self.api.list_positions()
                for position in positions:
                    unrealized_pl += float(position.unrealized_pl)
                print(f'unrealized_pl={unrealized_pl}')
                if unrealized_pl > 10:
                    self.api.close_all_positions()
                    print('closing..', float(self.api.get_account().equity) - self.start_equity)


        except Exception as e:
            print(f'order issue: ', e) 

    def start_trading(self):
        print(f'Start trading.. live={self.live}')
        self.start_equity = float(self.api.get_account().equity)
        

        async def handle_trades(trade):
            print('trade')
            self.process_trade(trade.symbol, trade.price)
        
        async def handle_trade_updates(data):
            print('trade_update')
            pass
            # if data.event == 'fill' or data.event == 'partial_fill':
            #     print(f'fill')

        self.conn.subscribe_trades(handle_trades, *self.stocks)
        self.conn.subscribe_trade_updates(handle_trade_updates)
        #self.conn.subscribe_news(handle_news, *self.stocks)
        #self.conn.subscribe_crypto_trades(handle_crypto, 'BTCUSD')
        self.conn.run()

        

if __name__ == '__main__':
    trader = My()
    trader.start_trading()