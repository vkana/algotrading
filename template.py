from alpaca.trading.client  import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest
from alpaca.data.live import StockDataStream
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass

key = "PKB97SPJRL9JL90D7ZQR"
secret = "YvmDUETetE3xSH2DojMlFpEbHYzepWVThWfe5oFz"
symbols = ('F', 'SPY', 'TQQQ','SQQQ',)
trading_client = TradingClient(key, secret, paper = True)
client = StockHistoricalDataClient(key, secret)
data = client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols = symbols ))
print(data)

#assets = trading_client.get_all_assets(filter= GetAssetsRequest(asset_class=AssetClass.CRYPTO))
#print(assets)

class My(object):
  def __init__(self):
    pass

  def start(self):
    print('start')
    
    async def quote_handler(data):
        print(f'quote {data.symbol} bid: {data.bid_price} ask: {data.ask_price}')
      
    async def trade_handler(data):
        print(f'trade {data.symbol}  trade_price: {data.price}')
    
    ws = StockDataStream(key, secret)
    print('here1')
    ws.subscribe_trades(trade_handler, *symbols)
    ws.subscribe_quotes(quote_handler, *symbols)
    print('here2')
    ws.run()

if __name__ == '__main__':
  t = My()
  t.start()