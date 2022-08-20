from typing import Dict
from alpaca.trading.client  import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest
from alpaca.data.live import StockDataStream, CryptoDataStream
from alpaca.trading.requests import GetAssetsRequest, MarketOrderRequest
from alpaca.trading.enums import TimeInForce
import datetime
import time
import constants
import asyncio

key = constants.ALPACA_API_KEY2
secret = constants.ALPACA_SECRET_KEY2
symbols = ('BTCUSD','ETHUSD', 'DOGEUSD')
trading_client = TradingClient(key, secret, paper = True)
client = StockHistoricalDataClient(key, secret)
#data = client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols = symbols ))
lot_amt = 1000
price_target = 0.005
#print(data)

#assets = trading_client.get_all_assets(filter= GetAssetsRequest(asset_class=AssetClass.CRYPTO))
#print(assets)

class Position(object):
  def __init__(self):
    self.last_price = 0
    self.qty = 0
    self.mult = 1
    self.pending_update = False
    self.dec = 0
  
  def __str__(self):
     return f'last_price={self.last_price} qty={self.qty} mult={self.mult} pending_update={self.pending_update} dec={self.dec}'

class My(object):
  def __init__(self):
    self.positions: Dict[str, Position] = {}
    pass

  def start(self):
    print('start')
    try:
      trading_client.close_all_positions(cancel_orders=True)
    except Exception as e:
      print('close positions exception:', e)
    
    async def quote_handler(data):
      symbol = data.symbol
      position = self.positions[symbol]

      try:
        #print(f'{datetime.datetime.now()}: quote  {data.symbol} bid: {data.bid_price} ask: {data.ask_price}')
        if not position.pending_update:
          #buy to open
          if (position.qty == 0 or data.ask_price < position.last_price * (1-price_target)):
            qty = round(position.mult*lot_amt/data.ask_price, position.dec)
            position.last_price = data.ask_price
            buy_order = trading_client.submit_order(MarketOrderRequest(symbol=symbol, side='buy', time_in_force=TimeInForce.DAY, qty= qty))
            position.mult +=1
            print(f'{symbol} {data.ask_price} {qty} BUY')

          position.pending_update = True
          #await asyncio.sleep(2)
          acct_position = trading_client.get_open_position(symbol)
          position.qty = float(acct_position.qty)
          position.avg_price = acct_position.avg_entry_price
          if (float(acct_position.qty) > 0 and float(acct_position.unrealized_intraday_plpc) > price_target):
            print(f'{symbol} closing position')
            sell_order = trading_client.close_position(symbol)
            #trading_client.submit_order(MarketOrderRequest(symbol=symbol, side='sell', time_in_force='day', qty= round(float(acct_position.qty),3)))
            print(f'{symbol} {data.ask_price} SELL')
            position.mult = 1
            #trading_client.close_position(symbol)
          
          position.pending_update = False

          #print(f'{symbol} pnl: {round(float(acct_position.unrealized_intraday_plpc),4)}% {symbol} {position}')
          
          
      except Exception as e:
        print(e)
    
    async def trade_handler(data):
      print(f'trade {data.symbol}  trade_price: {data.price}')
    
    async def bar_handler(data):
      print(datetime.datetime.now(), data)
      
    for symbol in symbols:
      self.positions[symbol] = Position()
      self.positions[symbol].dec = 0 if symbol=='DOGEUSD' else 3 if symbol=='ETHUSD' else 4 if symbol == 'BTCUSD' else 0
      # position = self.positions[symbol]
      # print(symbol, trading_client.get_asset(symbol))

    
    ws = CryptoDataStream(key, secret)
    print('here1')
    #ws.subscribe_trades(trade_handler, *symbols)
    ws.subscribe_quotes(quote_handler, *symbols)
    #ws.subscribe_bars(bar_handler, *symbols)
    print('here2')
    ws.run()

if __name__ == '__main__':
  t = My()
  t.start()