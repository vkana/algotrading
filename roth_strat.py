import asyncio
from dataclasses import dataclass

import constants
from alpaca.trading.client import TradingClient
from alpaca.trading.stream import TradingStream
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest, MarketOrderRequest
import time
import concurrent.futures
from datetime import datetime, timedelta

MAX_POSITION = 100
INITIAL_POSITION = 20
ADD_POSITION = 5
TARGET_MULTIPLIER = 1.005
NEXT_ENTRY_MULTIPLIER = 0.998

@dataclass
class Position:
    symbol: str
    qty: int
    side: str


def float2 (input, decimals=2):
    return round(float(input), decimals)

class RothStrategy:
    def __init__(self, live: bool = False):
        self.live = live
        self.symbols = ("TQQQ", "XLE", "XLF", "XLU", "FXI","SCHD", "SCHB", "SCHF")
        self.key = None
        self.secret = None
        self.tc = None
        self.ts = None

    def execute(self):
        if self.live:
            self.key = constants.ALPACA_API_KEY_ROTH
            self.secret = constants.ALPACA_SECRET_KEY_ROTH
        else:
            self.key = constants.ALPACA_API_KEY2
            self.secret = constants.ALPACA_SECRET_KEY2

        self.tc = TradingClient(self.key, self.secret, paper=not self.live)
        self.ts = TradingStream(self.key, self.secret, paper=not self.live)
        
        print(f"Executing {'live' if self.live else 'paper'} strategy...")
        # subscribe async handler
        self.ts.subscribe_trade_updates(self.handle_trade_updates)

        self.cancel_orders(self.symbols)

        for symbol in self.symbols:
            #if symbol is in positions above, print symbol, qty, side, avg_entry_price
            try:
                position = self.tc.get_open_position(symbol)
            except Exception as e:
                position = None

            if position:
                avg_price = float(position.avg_entry_price)

                print(f"symbol: {symbol}, qty: {position.qty}, side: {position.side}, avg_entry_price: {float2(avg_price)}")
                self.submit_limit_order(symbol, float2(position.qty), "sell",  float2(avg_price * TARGET_MULTIPLIER) )
                
                if float(position.qty) < MAX_POSITION:
                    self.submit_limit_order(symbol, ADD_POSITION, "buy",  float2(avg_price * NEXT_ENTRY_MULTIPLIER) )
            
            else:
                self.submit_market_order(symbol, INITIAL_POSITION, "buy")

        # Run the stream only during market hours; this will block until the
        # stream is stopped at the next market close.
        self.run_stream_during_market()

    #write unimplemented functions
    #use LimitOrderRequest

    def submit_limit_order(self, symbol, qty, side, limit_price):
        try:
            self.tc.submit_order(LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                type="limit",
                time_in_force="gtc",
                limit_price=limit_price
            ))
        except Exception as e:
            print(f"Error submitting limit order for {symbol}: {e}")

    def submit_market_order(self, symbol, qty, side):
        try:
            self.tc.submit_order(MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                type="market",
                time_in_force="gtc"
            ))
        except Exception as e:
            print(f"Error submitting market order for {symbol}: {e}")

    
    def cancel_orders(self, symbols):
        if isinstance(symbols, str):
            symbols = [symbols]

        orders = self.tc.get_orders(GetOrdersRequest(status="open"))
        for order in orders:
            if order.symbol in symbols:
                try:
                    self.tc.cancel_order_by_id(order.id)
                except Exception as e:
                    print(f"Error cancelling order {order.symbol} {order.side} {order.qty}: {e}")

    async def handle_trade_updates(self, data):
        if data.event in ("fill", "partial_fill") and data.order.symbol in self.symbols:
            if data.event == "partial_fill":
                await asyncio.sleep(5)
            
            # string data.order.side
            print(data.event, data.order.symbol, str(data.order.side), data.order.qty, data.order.filled_avg_price)

            # If an order was filled, submit a new limit order to add to the position.
            symbol = data.order.symbol
            side = data.order.side
            price = float(data.order.filled_avg_price) 
            
            await asyncio.sleep(5)
            self.cancel_orders(symbol)

            if side == "buy":
                position = self.tc.get_open_position(symbol)
                qty = float(position.qty)
                avg_price = float(position.avg_entry_price)
                self.submit_limit_order(symbol, qty, "sell", float2(avg_price * TARGET_MULTIPLIER))
                self.submit_limit_order(symbol, ADD_POSITION, "buy", float2(price * NEXT_ENTRY_MULTIPLIER))
                
            else:
                self.submit_market_order(symbol, INITIAL_POSITION, "buy")
        elif data.event in ("canceled", "new"):
            try:
                print(data.event, data.order.symbol, str(data.order.side), data.order.qty, (data.order.limit_price if data.order.limit_price else "market"))
            except Exception as e:
                print(data.event, e)

    def run_stream_during_market(self):
        """Start `self.ts.run()` when the market is open and stop it at next_close.

        This method:
        - Waits until `next_open` if market is closed.
        - Starts `self.ts.run()` in a background thread.
        - Sleeps until a few seconds before `next_close`, then stops the stream.
        """
        if self.tc is None or self.ts is None:
            raise RuntimeError("Trading client and stream must be initialized before running stream")

        # Check clock and wait until open if necessary
        clock = self.tc.get_clock()
        if not clock.is_open:
            next_open = clock.next_open
            now = datetime.now(tz=next_open.tzinfo)
            secs = (next_open - now).total_seconds()
            if secs > 0:
                print(f"Market closed — waiting {int(secs)}s until open at {next_open}")
                time.sleep(secs + 1)

        # Re-evaluate clock; if still closed, don't start
        clock = self.tc.get_clock()
        if not clock.is_open:
            print("Market still closed after waiting — aborting stream start")
            return

        next_close = clock.next_close
        now = datetime.now(tz=next_close.tzinfo)
        secs_until_close = (next_close - now).total_seconds()
        print(f"Market open — starting stream. Will stop in {int(secs_until_close)}s at {next_close}.")

        # Run the stream in a worker thread and stop it shortly before close.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            fut = executor.submit(self.ts.run)

            # Sleep until a few seconds before close, then stop the stream.
            wait_secs = max(secs_until_close - 5, 0)
            try:
                time.sleep(wait_secs)
            except KeyboardInterrupt:
                print("Interrupted — stopping stream")

            print("Stopping stream for market close...")
            try:
                self.ts.stop()
            except Exception as e:
                print("Error stopping stream:", e)

            # Give the run() thread time to exit cleanly.
            try:
                fut.result(timeout=30)
            except Exception:
                pass



# Example usage
if __name__ == "__main__":
    strat = RothStrategy(live=True)
    strat.execute()
    
