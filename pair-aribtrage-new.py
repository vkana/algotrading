from turtle import pos
from alpaca.trading.client  import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest
from alpaca.trading.requests import MarketOrderRequest
from alpaca.data.live import StockDataStream
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass, TimeInForce
import time

key = "PKB97SPJRL9JL90D7ZQR"
secret = "YvmDUETetE3xSH2DojMlFpEbHYzepWVThWfe5oFz"
symbols = ('TQQQ','SQQQ',)
trading_client = TradingClient(key, secret, paper = True)
client = StockHistoricalDataClient(key, secret)
data = client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols = symbols ))
print(data)

#assets = trading_client.get_all_assets(filter= GetAssetsRequest(asset_class=AssetClass.CRYPTO))
#print(assets)

class My(object):
  def __init__(self):
    pass

  def process_trade(self, symbol, bid_price, ask_price):
      current_pl = 0
      positions = trading_client.get_all_positions()
      if len(positions) == 0:
        print('Entering..')
        trading_client.submit_order(MarketOrderRequest(symbol = 'TQQQ', side='buy', notional=30000, time_in_force='day'))
        trading_client.submit_order(MarketOrderRequest(symbol = 'SQQQ', side='buy', notional=30000, time_in_force='day'))
        time.sleep(2)
        return
      

      for p in positions:
        current_pl += float(p.unrealized_pl)
      
      print(f'current_pl {current_pl}')
      if current_pl > 10:
        print('Exiting..')
        trading_client.close_all_positions(cancel_orders=True)
      
  def start(self):
    print('start')
    
    async def quote_handler(data):
      #filter bad quotes
      if (data.bid_price == 0 or data.ask_price == 0 or data.ask_price - data.bid_price > 0.01):
        return
      
      self.process_trade(data.symbol, data.bid_price, data.ask_price)
      
    async def trade_handler(data):
        print(f'trade {data.symbol}  trade_price: {data.price}')
    
    ws = StockDataStream(key, secret)
    #ws.subscribe_trades(trade_handler, *symbols)
    ws.subscribe_quotes(quote_handler, *symbols)
    ws.run()

if __name__ == '__main__':
  t = My()
  t.start()