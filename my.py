import alpaca_trade_api as tradeapi
import constants
from alpaca_trade_api.stream import Stream
import logging

class My(object):
    def __init__(self):
        self.key_id = constants.ALPACA_API_KEY_LIVE
        self.secret_key = constants.ALPACA_SECRET_KEY_LIVE
        self.base_url = constants.base_url_live
        self.data_url = constants.data_url
        self.stocks = ('AMD')
        self.last_price = {}
        self.positions = {}
        self.target_price = 0.05
        self.qty = 100
        self.start_equity = 0
        self.last_equity = 0


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
        )
    
    
    
    def start_trading(self):
        # logging.basicConfig(filename='console2.log', level=logging.INFO)
        # logging.info('start trading')
        print(self.api.get_account().regt_buying_power)

        #self.conn.run()

        

if __name__ == '__main__':
    trader = My()
    trader.start_trading()