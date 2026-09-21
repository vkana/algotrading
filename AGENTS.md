# Algorithmic Trading Project Guidelines

## Project Shape

- This is a collection of standalone Python trading strategies, not a packaged application.
- Existing strategy entry points include `blshlimit.py`, `blshlimit_new.py`, `roth_strat.py`, `avg_testaccount.py`, and `template.py`.
- `filo_strat.py` is currently empty and is a suitable place for a new strategy only after following the patterns below.
- Read [README.md](README.md) for the project overview and [example-scalping/README.md](example-scalping/README.md) for the older scalping architecture. Treat any README instruction to put keys directly in source as obsolete; use environment variables or a secret manager instead.

## Alpaca SDK And Streaming

- Use `alpaca-py` from `requirements.txt` for new code. The preferred clients are:
  - `TradingClient` for account, position, order, and clock operations.
  - `StockHistoricalDataClient` for synchronous historical/latest quote or trade requests.
  - `StockDataStream` or `CryptoDataStream` for market-data streams.
  - `TradingStream` for order and trade updates.
- Build API calls with the SDK request classes (`MarketOrderRequest`, `LimitOrderRequest`, `GetOrdersRequest`, and similar) and enum values such as `OrderSide`, `TimeInForce`, and `QueryOrderStatus`.
- Stream callbacks must be `async def` functions. Register subscriptions before calling `run()`.
- `run()` blocks. When a strategy owns multiple streams or must perform startup/shutdown work concurrently, follow `template.py` and `avg_testaccount.py` by running the streams and lifecycle tasks in a `ThreadPoolExecutor`.
- Keep callback state scoped to the strategy instance and keyed by symbol. On startup, hydrate positions and open orders from Alpaca so a restart can reconcile broker state before submitting new orders.
- Treat fill, partial-fill, cancellation, and rejection events as state transitions. Re-check broker state after fills before placing replacement or exit orders.
- Do not call blocking `time.sleep()` inside an async callback; use `await asyncio.sleep()` for callback delays. Stop streams explicitly during shutdown, then cancel or reconcile outstanding orders.
- Use `TradingClient(..., paper=True)` by default. Make live trading an explicit opt-in and keep the paper/live choice visible in logs.

## Legacy Streaming Examples

- `websockets/*.py` and `example-scalping/main.py` use the older `alpaca_trade_api.Stream` API. They document subscription, restart, and reconnect ideas, but do not copy that API into new strategies unless maintaining those files.
- Prefer the `alpaca.data.live` and `alpaca.trading.stream` interfaces shown in `template.py` and `avg_testaccount.py` for new work.

## Credentials And Safety

- Never add API keys, secrets, account passwords, or tokens to source, documentation, or logs. Load credentials from environment variables or a local secret manager.
- Existing `constants.py` files contain credentials that are still imported by runtime strategies; treat them as compromised, do not propagate them into new code, and rotate/revoke them before any further trading.
- Keep new strategies paper-only until their order lifecycle and shutdown behavior have been verified with mocked or paper-account calls.
- Validate symbol lists, quantities, prices, and live/paper configuration at the boundary. Log order IDs, symbols, sides, quantities, prices, and statuses without logging credentials.

## Running And Checking Changes

```text
pip install -r requirements.txt
python -m py_compile <strategy>.py
# Only run a strategy after forcing paper mode and confirming the selected account.
```

- `start.sh` launches `blshlimit.py` and `roth_strat.py` in the background, and the Roth entry point currently enables live mode. Agents must not execute `start.sh`; use an explicitly paper-only entry point after review instead. Use `stop.sh` only to stop processes recorded by the starter script.
- There is no established automated test suite. For strategy changes, at minimum run compilation and exercise order decisions with mocked clients. If an integration run is needed, use an explicitly paper-only configuration; never use live credentials for validation.
- Avoid running a strategy merely to validate imports if it will connect to a broker or submit orders; inspect or mock client construction first.

## Representative Files

- `template.py`: smallest modern `alpaca-py` example combining market-data and trade-update streams.
- `avg_testaccount.py`: modern quote and trade-update handlers with account/position reconciliation.
- `blshlimit.py`: fuller order lifecycle with typed requests, enums, market-clock handling, and shutdown behavior.
- `roth_strat.py`: class-based strategy with logging, paper/live selection, and trade-update reactions.