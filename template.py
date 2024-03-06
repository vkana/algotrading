from alpaca.trading.client  import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest
from alpaca.data.live import StockDataStream, CryptoDataStream
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass
import constants
from datetime import datetime, tzinfo
import pandas as pd
import time
import asyncio
import concurrent.futures


key = constants.ALPACA_API_KEY4
secret = constants.ALPACA_SECRET_KEY4
symbols = ('ETHUSD','BTCUSD', 'DOGEUSD')
trading_client = TradingClient(key, secret, paper = True)
ws = CryptoDataStream(key, secret)
ts = TradingStream(key, secret, paper = True)

class My(object):
  def __init__(self):
    self.count = 0
    self.minute = 0
    self.output = {}
    pass

  def start(self):
    print('start')
    for symbol in symbols:
      self.output[symbol] = {'b':0, 'a': 0, 't': 0}

    async def quote_handler(data):
      print('quote_handler......')
      self.output[data.symbol]['b'] = data.bid_price
      self.output[data.symbol]['a'] = data.ask_price
      print(f'{datetime.now().time()} {self.output}')
      
    async def trade_handler(data):
      self.output[data.symbol]['t'] = data.price

    async def trade_update_handler(data):
      print(data)

    async def bar_handler(data):
      print(data)
    
    
    ws.subscribe_quotes(quote_handler, *symbols)
    ts.subscribe_trade_updates(trade_update_handler)
    ws.subscribe_trades(trade_handler, *symbols)
    #ws.subscribe_bars(bar_handler, *symbols)
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.submit(ts.run)
            executor.submit(ws.run)
    
    

if __name__ == '__main__':
  t = My()
  t.start()