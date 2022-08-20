from alpaca.trading.client  import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest
from alpaca.data.live import StockDataStream
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass
import constants
from datetime import datetime, tzinfo
import pandas as pd
import time
import asyncio
import backtrader as bt

key = constants.ALPACA_API_KEY4
secret = constants.ALPACA_SECRET_KEY4
symbols = ('TQQQ', 'SQQQ',)
trading_client = TradingClient(key, secret, paper = True)
#client = StockHistoricalDataClient(key, secret)
# data = client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols = symbols ))
# print(data)

#assets = trading_client.get_all_assets(filter= GetAssetsRequest(asset_class=AssetClass.CRYPTO))
#print(assets)

class SmaCross(bt.SignalStrategy):
  def __init__(self) -> None:
    sma1, sma2 = bt.ind.SMA(period=1), bt.ind.SMA(period=2)
    crossover = bt.ind.crossover(sma1, sma2)
    self.close = self.data.close
    

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

    # def get_account():
    #   x = trading_client.get_account()
    #   y = trading_client.get_clock().is_open
    #   z = trading_client.get_clock().timestamp.second
    #   min = datetime.now().time().minute
    #   if min != self.minute:
    #     self.count = 0
    #     self.minute = min
        
      
    #   print(f'calls: {datetime.now().time()} {self.count} {y} {z}')
    #   self.count += 3
    # self.minute = datetime.now().time().minute
    # while (True):
    #   get_account()

    async def quote_handler(data):
      
      self.output[data.symbol]['b'] = data.bid_price
      self.output[data.symbol]['a'] = data.ask_price
      print(f'{datetime.now().time()} {self.output}')
      
      #print(data.symbol, data.bid_price, data.ask_price)
        #print(f'{datetime.now().time()} quote {data.symbol} bid: {data.bid_price} ask: {data.ask_price}')
        #pass
      
    async def trade_handler(data):
      self.output[data.symbol]['t'] = data.price
      #print(f'{datetime.now().time()} {self.output}')

    async def bar_handler(data):
      print(data)
    
    ws = StockDataStream(key, secret)
    ws.subscribe_trades(trade_handler, *symbols)
    ws.subscribe_quotes(quote_handler, *symbols)
    # ws.subscribe_bars(bar_handler, *symbols)
    ws.run()

    # a = [38.05, 38, 37.95, 37.90]
    # b = [10, 10, 20, 40]

    # df = pd.DataFrame({'price':a, 'qty': b})
    # df['cost_basis'] = df['price'] * df['qty']
    # avg = df.sum(axis=0)
    # print(df)
    # print(avg['cost_basis']/avg['qty'])

    # clock = trading_client.get_clock()
    # next_open = clock.next_open
    # now = datetime.now(tz=next_open.tzinfo)
    # if not clock.is_open:
    #   secs = (next_open - now).total_seconds()
    #   print('sleeping until market open..')
    #   print(next_open, now, (next_open - now).total_seconds())
    #   time.sleep(secs)
      
    #  pass
    
    

if __name__ == '__main__':
  t = My()
  t.start()