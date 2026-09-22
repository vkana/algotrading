import asyncio
import logging
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo
import constants

from alpaca.common.exceptions import APIError
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetCalendarRequest, GetOrdersRequest, LimitOrderRequest, MarketOrderRequest
from alpaca.trading.stream import TradingStream


LOGGER = logging.getLogger("filo_strategy")
TAKE_PROFIT = 0.10
ENTRY_STEP = 0.05
DEFAULT_SYMBOLS = ("TQQQ", "SQQQ")
POLL_SECONDS = 15
EXTENDED_HOURS_BEFORE_OPEN = timedelta(hours=5, minutes=30)
EXTENDED_HOURS_AFTER_CLOSE = timedelta(hours=4)
EASTERN = ZoneInfo("America/New_York")


def _utc_now() -> str:
	return datetime.now(timezone.utc).isoformat()


def _enum_value(value: Any) -> str:
	return str(getattr(value, "value", value)).lower()


class FiloState:
	"""SQLite state for independent entries and their take-profit orders."""

	def __init__(self, path: str) -> None:
		self._connection = sqlite3.connect(path, check_same_thread=False)
		self._connection.row_factory = sqlite3.Row
		self._lock = threading.RLock()
		self._connection.execute("PRAGMA journal_mode=WAL")
		self._connection.executescript(
			"""
			CREATE TABLE IF NOT EXISTS entries (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				symbol TEXT NOT NULL,
				buy_order_id TEXT,
				quantity INTEGER NOT NULL,
				remaining_quantity INTEGER NOT NULL,
				filled_sell_quantity INTEGER NOT NULL DEFAULT 0,
				entry_price REAL NOT NULL,
				target_order_id TEXT,
				target_price REAL NOT NULL,
				realized_profit REAL NOT NULL DEFAULT 0,
				status TEXT NOT NULL DEFAULT 'open',
				created_at TEXT NOT NULL,
				closed_at TEXT
			);
			CREATE INDEX IF NOT EXISTS entries_symbol_status
				ON entries(symbol, status);
			CREATE TABLE IF NOT EXISTS pending_buys (
				order_id TEXT PRIMARY KEY,
				symbol TEXT NOT NULL,
				quantity INTEGER NOT NULL,
				filled_quantity INTEGER NOT NULL DEFAULT 0,
				limit_price REAL,
				status TEXT NOT NULL DEFAULT 'open',
				created_at TEXT NOT NULL
			);
			"""
		)
		columns = {row["name"] for row in self._connection.execute("PRAGMA table_info(pending_buys)")}
		if "filled_quantity" not in columns:
			self._connection.execute(
				"ALTER TABLE pending_buys ADD COLUMN filled_quantity INTEGER NOT NULL DEFAULT 0"
			)
		entry_columns = {row["name"] for row in self._connection.execute("PRAGMA table_info(entries)")}
		if "filled_sell_quantity" not in entry_columns:
			self._connection.execute(
				"ALTER TABLE entries ADD COLUMN filled_sell_quantity INTEGER NOT NULL DEFAULT 0"
			)
		self._connection.commit()

	def close(self) -> None:
		with self._lock:
			self._connection.close()

	def add_pending_buy(self, order_id: str, symbol: str, quantity: int, limit_price: float | None) -> None:
		with self._lock, self._connection:
			self._connection.execute(
				"INSERT OR REPLACE INTO pending_buys "
				"(order_id, symbol, quantity, filled_quantity, limit_price, created_at) VALUES (?, ?, ?, 0, ?, ?)",
				(order_id, symbol, quantity, limit_price, _utc_now()),
			)

	def pending_buy(self, symbol: str) -> sqlite3.Row | None:
		with self._lock:
			return self._connection.execute(
				"SELECT * FROM pending_buys WHERE symbol = ? AND status = 'open' "
				"ORDER BY created_at DESC LIMIT 1",
				(symbol,),
			).fetchone()

	def pending_buys(self, symbol: str) -> list[sqlite3.Row]:
		with self._lock:
			return list(
				self._connection.execute(
					"SELECT * FROM pending_buys WHERE symbol = ? AND status = 'open' ORDER BY created_at",
					(symbol,),
				)
			)

	def has_pending_buy_order(self, order_id: str) -> bool:
		with self._lock:
			return self._connection.execute(
				"SELECT 1 FROM pending_buys WHERE order_id = ?", (order_id,)
			).fetchone() is not None

	def tracked_order_ids(self) -> set[str]:
		with self._lock:
			rows = self._connection.execute(
				"SELECT buy_order_id AS order_id FROM entries "
				"UNION SELECT target_order_id FROM entries WHERE target_order_id IS NOT NULL "
				"UNION SELECT order_id FROM pending_buys"
			).fetchall()
			return {str(row["order_id"]) for row in rows if row["order_id"]}

	def update_pending_buy(self, order_id: str, status: str) -> None:
		with self._lock, self._connection:
			self._connection.execute(
				"UPDATE pending_buys SET status = ? WHERE order_id = ?",
				(status, order_id),
			)

	def record_pending_fill(self, order_id: str, cumulative_quantity: int) -> int:
		with self._lock, self._connection:
			row = self._connection.execute(
				"SELECT filled_quantity FROM pending_buys WHERE order_id = ?", (order_id,)
			).fetchone()
			previous_quantity = int(row["filled_quantity"]) if row else 0
			delta = max(0, cumulative_quantity - previous_quantity)
			self._connection.execute(
				"UPDATE pending_buys SET filled_quantity = ? WHERE order_id = ?",
				(max(previous_quantity, cumulative_quantity), order_id),
			)
			return delta

	def open_entries(self, symbol: str | None = None) -> list[sqlite3.Row]:
		with self._lock:
			if symbol is None:
				return list(self._connection.execute("SELECT * FROM entries WHERE status = 'open'"))
			return list(
				self._connection.execute(
					"SELECT * FROM entries WHERE symbol = ? AND status = 'open' ORDER BY id",
					(symbol,),
				)
			)

	def add_entry(
		self,
		symbol: str,
		buy_order_id: str,
		quantity: int,
		entry_price: float,
		target_order_id: str | None = None,
	) -> int:
		target_price = round(entry_price + TAKE_PROFIT, 2)
		with self._lock, self._connection:
			cursor = self._connection.execute(
				"INSERT INTO entries "
				"(symbol, buy_order_id, quantity, remaining_quantity, entry_price, "
				"target_order_id, target_price, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
				(symbol, buy_order_id, quantity, quantity, entry_price, target_order_id, target_price, _utc_now()),
			)
			return int(cursor.lastrowid)

	def entries_for_buy(self, buy_order_id: str) -> list[sqlite3.Row]:
		with self._lock:
			return list(
				self._connection.execute(
					"SELECT * FROM entries WHERE buy_order_id = ? ORDER BY id",
					(buy_order_id,),
				)
			)

	def attach_target_order(self, entry_id: int, order_id: str) -> None:
		with self._lock, self._connection:
			self._connection.execute(
				"UPDATE entries SET target_order_id = ? WHERE id = ?",
				(order_id, entry_id),
			)

	def record_sell_fill(self, entry_id: int, quantity: int, exit_price: float) -> sqlite3.Row | None:
		with self._lock, self._connection:
			entry = self._connection.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
			if entry is None or entry["status"] != "open":
				return entry

			previous_filled = int(entry["filled_sell_quantity"])
			cumulative_quantity = min(quantity, int(entry["quantity"]))
			filled_quantity = max(0, cumulative_quantity - previous_filled)
			profit = filled_quantity * (exit_price - float(entry["entry_price"]))
			remaining = int(entry["quantity"]) - cumulative_quantity
			status = "closed" if remaining == 0 else "open"
			self._connection.execute(
				"UPDATE entries SET remaining_quantity = ?, filled_sell_quantity = ?, realized_profit = realized_profit + ?, "
				"status = ?, closed_at = CASE WHEN ? = 'closed' THEN ? ELSE closed_at END WHERE id = ?",
				(remaining, cumulative_quantity, profit, status, status, _utc_now(), entry_id),
			)
			return entry

	def find_entry_by_target(self, order_id: str) -> sqlite3.Row | None:
		with self._lock:
			return self._connection.execute(
				"SELECT * FROM entries WHERE target_order_id = ? LIMIT 1",
				(order_id,),
			).fetchone()


class FiloStrategy:
	def __init__(
		self,
		symbols: Iterable[str] = DEFAULT_SYMBOLS,
		num_of_shares: int = 10,
		max_position: int = 300,
		state_path: str = "filo_state.sqlite3",
		live: bool = False,
		trading_client: TradingClient | None = None,
		trading_stream: TradingStream | None = None,
	) -> None:
		if num_of_shares <= 0 or max_position <= 0:
			raise ValueError("num_of_shares and max_position must be positive")
		if num_of_shares > max_position:
			raise ValueError("num_of_shares cannot exceed max_position")

		normalized_symbols = tuple(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
		if not normalized_symbols:
			raise ValueError("at least one symbol is required")

		self.symbols = normalized_symbols
		self.num_of_shares = num_of_shares
		self.max_position = max_position
		self.live = live
		self.state = FiloState(state_path)
		self.trading_client = trading_client
		self.trading_stream = trading_stream
		self.market_data_client: StockHistoricalDataClient | None = None
		self._executor: ThreadPoolExecutor | None = None

	@classmethod
	def from_environment(cls) -> "FiloStrategy":
		symbols = tuple(os.getenv("FILO_SYMBOLS", ",".join(DEFAULT_SYMBOLS)).split(","))
		return cls(
			symbols=symbols,
			num_of_shares=int(os.getenv("FILO_NUM_OF_SHARES", "10")),
			max_position=int(os.getenv("FILO_MAX_POSITION", "300")),
			state_path=os.getenv("FILO_STATE_DB", "filo_state.sqlite3"),
			live=os.getenv("ALPACA_LIVE", "false").lower() == "true",
		)

	def _ensure_clients(self) -> None:
		if self.trading_client is not None and self.trading_stream is not None:
			return
		#use key and secret from constants.py

		key = constants.ALPACA_API_KEY3
		secret = constants.ALPACA_SECRET_KEY3
		self.trading_client = TradingClient(key, secret, paper=not self.live)
		self.trading_stream = TradingStream(key, secret, paper=not self.live)
		self.market_data_client = StockHistoricalDataClient(key, secret)

	def _open_orders(self) -> list[Any]:
		assert self.trading_client is not None
		return list(
			self.trading_client.get_orders(
				GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=list(self.symbols))
			)
		)

	def _position_quantity(self, symbol: str) -> int:
		assert self.trading_client is not None
		try:
			return int(float(self.trading_client.get_open_position(symbol).qty))
		except APIError as exc:
			if getattr(exc, "status_code", None) == 404:
				return 0
			LOGGER.error("position lookup failed symbol=%s error_type=%s", symbol, type(exc).__name__)
			return -1
		except Exception as exc:
			LOGGER.error("position lookup failed symbol=%s error_type=%s", symbol, type(exc).__name__)
			return -1

	def _submit_target(self, symbol: str, quantity: int, entry_price: float) -> Any:
		assert self.trading_client is not None
		return self.trading_client.submit_order(
			LimitOrderRequest(
				symbol=symbol,
				qty=quantity,
				side=OrderSide.SELL,
				limit_price=round(entry_price + TAKE_PROFIT, 2),
				# Alpaca requires DAY for extended-hours eligible orders.
				time_in_force=TimeInForce.DAY,
				extended_hours=True,
			)
		)

	def _submit_market_entry(self, symbol: str, quantity: int) -> Any:
		assert self.trading_client is not None
		if self.trading_client.get_clock().is_open:
			order = self.trading_client.submit_order(
				MarketOrderRequest(
					symbol=symbol,
					qty=quantity,
					side=OrderSide.BUY,
					time_in_force=TimeInForce.DAY,
				)
			)
		else:
			if self.market_data_client is None:
				raise RuntimeError("market data client is required for extended-hours entries")
			quote = self.market_data_client.get_stock_latest_quote(
				request_params=StockLatestQuoteRequest(symbol_or_symbols=symbol)
			)[symbol]
			limit_price = quote.ask_price or quote.bid_price
			if not limit_price:
				raise RuntimeError(f"no usable quote for extended-hours entry: {symbol}")
			order = self.trading_client.submit_order(
				LimitOrderRequest(
					symbol=symbol,
					qty=quantity,
					side=OrderSide.BUY,
					limit_price=round(float(limit_price), 2),
					# Alpaca requires DAY for extended-hours eligible orders.
					time_in_force=TimeInForce.DAY,
					extended_hours=True,
				)
			)
		self.state.add_pending_buy(
			str(order.id),
			symbol,
			quantity,
			float(order.limit_price) if getattr(order, "limit_price", None) is not None else None,
		)
		LOGGER.info("submitted market entry symbol=%s qty=%s order_id=%s", symbol, quantity, order.id)
		return order

	def _submit_ladder_entry(self, symbol: str, quantity: int, entry_price: float) -> Any:
		assert self.trading_client is not None
		limit_price = round(entry_price - ENTRY_STEP, 2)
		order = self.trading_client.submit_order(
			LimitOrderRequest(
				symbol=symbol,
				qty=quantity,
				side=OrderSide.BUY,
				limit_price=limit_price,
				# Alpaca requires DAY for extended-hours eligible orders.
				time_in_force=TimeInForce.DAY,
				extended_hours=True,
			)
		)
		self.state.add_pending_buy(str(order.id), symbol, quantity, limit_price)
		LOGGER.info(
			"submitted ladder entry symbol=%s qty=%s limit_price=%s order_id=%s",
			symbol,
			quantity,
			limit_price,
			order.id,
		)
		return order

	def _ensure_target_orders(self, open_orders: list[Any]) -> None:
		open_order_ids = {str(order.id) for order in open_orders}
		reserved_sell_quantity = {
			symbol: sum(
				int(float(order.qty))
				for order in open_orders
				if order.symbol == symbol and _enum_value(order.side) == "sell"
			)
			for symbol in self.symbols
		}
		for entry in self.state.open_entries():
			if entry["target_order_id"] and str(entry["target_order_id"]) in open_order_ids:
				continue
			position_quantity = self._position_quantity(entry["symbol"])
			if position_quantity < 0:
				continue
			quantity = min(
				int(entry["remaining_quantity"]),
				max(0, position_quantity - reserved_sell_quantity[entry["symbol"]]),
			)
			if quantity <= 0:
				continue
			order = self._submit_target(entry["symbol"], quantity, float(entry["entry_price"]))
			self.state.attach_target_order(int(entry["id"]), str(order.id))
			reserved_sell_quantity[entry["symbol"]] += quantity
			LOGGER.info("restored target symbol=%s entry_id=%s order_id=%s", entry["symbol"], entry["id"], order.id)

	def reconcile(self) -> None:
		"""Restore missing targets and seed each symbol's next entry order."""
		open_orders = self._open_orders()
		for order in open_orders:
			if _enum_value(order.side) != "buy" or self.state.has_pending_buy_order(str(order.id)):
				continue
			filled_quantity = int(float(getattr(order, "filled_qty", 0) or 0))
			self.state.add_pending_buy(
				str(order.id),
				order.symbol,
				int(float(order.qty)),
				float(order.limit_price) if order.limit_price is not None else None,
			)
			if filled_quantity > 0 and not self.state.entries_for_buy(str(order.id)):
				entry_price = float(getattr(order, "filled_avg_price", 0) or 0)
				if entry_price > 0:
					entry_id = self.state.add_entry(str(order.symbol), str(order.id), filled_quantity, entry_price)
					try:
						target = self._submit_target(str(order.symbol), filled_quantity, entry_price)
						self.state.attach_target_order(entry_id, str(target.id))
					except Exception:
						LOGGER.exception("failed to restore target for partially filled order_id=%s", order.id)
		self._ensure_target_orders(open_orders)
		for symbol in self.symbols:
			position_quantity = self._position_quantity(symbol)
			if position_quantity < 0:
				continue
			pending_buys = self.state.pending_buys(symbol)
			open_entries = self.state.open_entries(symbol)
			if position_quantity == 0 and not pending_buys:
				self._submit_market_entry(symbol, min(self.num_of_shares, self.max_position))
				continue

			pending_quantity = sum(
				int(row["quantity"]) - int(row["filled_quantity"]) for row in pending_buys
			)
			committed_quantity = position_quantity + pending_quantity
			if committed_quantity >= self.max_position or pending_buys:
				continue

			reference_price = float(open_entries[-1]["entry_price"]) if open_entries else 0.0
			if reference_price <= 0:
				continue
			quantity = min(self.num_of_shares, self.max_position - committed_quantity)
			self._submit_ladder_entry(symbol, quantity, reference_price)

	async def handle_trade_update(self, data: Any) -> None:
		try:
			order = getattr(data, "order", None)
			symbol = getattr(order, "symbol", None)
			if symbol not in self.symbols or order is None:
				return

			event = _enum_value(getattr(data, "event", ""))
			order_id = str(getattr(order, "id", ""))
			side = _enum_value(getattr(order, "side", ""))
			if side == "buy":
				if not self.state.has_pending_buy_order(order_id):
					return
				await self._handle_buy_update(data, event, symbol, order_id)
			elif side == "sell":
				await self._handle_sell_update(data, event, symbol, order_id)
		except Exception:
			LOGGER.exception("trade update processing failed")

	async def _handle_buy_update(self, data: Any, event: str, symbol: str, order_id: str) -> None:
		if event not in {"partial_fill", "fill"}:
			if event in {"canceled", "rejected", "expired"}:
				self.state.update_pending_buy(order_id, event)
			return

		order = data.order
		entry_price = float(getattr(data, "price", 0) or getattr(order, "filled_avg_price", 0) or 0)
		if entry_price <= 0:
			LOGGER.warning("buy update has no usable fill price order_id=%s", order_id)
			return
		cumulative_quantity = int(float(getattr(order, "filled_qty", 0) or 0))
		filled_quantity = self.state.record_pending_fill(order_id, cumulative_quantity)
		if filled_quantity <= 0:
			return
		entry_id = self.state.add_entry(symbol, order_id, filled_quantity, entry_price)
		try:
			target = self._submit_target(symbol, filled_quantity, entry_price)
		except Exception:
			LOGGER.exception("take-profit submission failed symbol=%s entry_id=%s", symbol, entry_id)
			self.reconcile()
			return
		self.state.attach_target_order(entry_id, str(target.id))
		if event == "fill":
			self.state.update_pending_buy(order_id, "filled")
		LOGGER.info(
			"buy fill symbol=%s qty=%s entry_price=%s target_order_id=%s",
			symbol,
			filled_quantity,
			entry_price,
			target.id,
		)
		if event == "fill":
			self.reconcile()

	async def _handle_sell_update(self, data: Any, event: str, symbol: str, order_id: str) -> None:
		if event not in {"partial_fill", "fill"}:
			return
		entry = self.state.find_entry_by_target(order_id)
		if entry is None:
			LOGGER.warning("sell update has no tracked entry symbol=%s order_id=%s", symbol, order_id)
			return
		quantity = int(float(getattr(data.order, "filled_qty", 0) or getattr(data, "qty", 0)))
		exit_price = float(getattr(data.order, "filled_avg_price", 0) or getattr(data, "price", 0) or 0)
		if quantity <= 0 or exit_price <= 0:
			return
		tracked_entry = self.state.record_sell_fill(int(entry["id"]), quantity, exit_price)
		if tracked_entry is not None:
			profit = quantity * (exit_price - float(tracked_entry["entry_price"]))
			LOGGER.info(
				"take profit symbol=%s qty=%s entry_price=%s exit_price=%s realized_profit=%.2f",
				symbol,
				quantity,
				tracked_entry["entry_price"],
				exit_price,
				profit,
			)
		if event == "fill":
			self.reconcile()

	def _session_window(self) -> tuple[datetime, datetime]:
		assert self.trading_client is not None
		now = datetime.now(EASTERN)
		calendar = self.trading_client.get_calendar(
			GetCalendarRequest(start=now.date(), end=now.date() + timedelta(days=3))
		)
		for session in calendar:
			regular_open = session.open
			regular_close = session.close
			if regular_open.tzinfo is None:
				regular_open = regular_open.replace(tzinfo=EASTERN)
			else:
				regular_open = regular_open.astimezone(EASTERN)
			if regular_close.tzinfo is None:
				regular_close = regular_close.replace(tzinfo=EASTERN)
			else:
				regular_close = regular_close.astimezone(EASTERN)
			window_start = regular_open - EXTENDED_HOURS_BEFORE_OPEN
			window_end = regular_close + EXTENDED_HOURS_AFTER_CLOSE
			if now <= window_end:
				return window_start, window_end
		raise RuntimeError("Alpaca returned no upcoming trading session")

	def _wait_for_session_start(self, session_start: datetime) -> None:
		now = datetime.now(EASTERN)
		seconds = max(0, (session_start - now).total_seconds())
		if seconds > 0:
			LOGGER.info("waiting %.0f seconds for extended-hours session start", seconds)
			time.sleep(seconds)

	def _run_until_session_end(self, stream_future: Any, session_end: datetime) -> None:
		while True:
			if stream_future.done():
				stream_future.result()
				return
			seconds = (session_end - datetime.now(EASTERN)).total_seconds()
			if seconds <= 0:
				return
			time.sleep(min(POLL_SECONDS, seconds))

	def _cancel_open_orders(self) -> None:
		if self.trading_client is None:
			return
		tracked_order_ids = self.state.tracked_order_ids()
		for order in self._open_orders():
			if str(order.id) not in tracked_order_ids:
				continue
			try:
				self.trading_client.cancel_order_by_id(order.id)
			except Exception:
				LOGGER.exception("order cancellation failed order_id=%s", order.id)

	def run(self) -> None:
		try:
			self._ensure_clients()
			assert self.trading_stream is not None
			LOGGER.info("starting Filo strategy symbols=%s live=%s", self.symbols, self.live)
			session_start, session_end = self._session_window()
			self._wait_for_session_start(session_start)
			self.trading_stream.subscribe_trade_updates(self.handle_trade_update)
			self._executor = ThreadPoolExecutor(max_workers=2)
			stream_future = self._executor.submit(self.trading_stream.run)
			self.reconcile()
			self._run_until_session_end(stream_future, session_end)
		finally:
			if self.trading_stream is not None:
				self.trading_stream.stop()
			if self._executor is not None:
				self._executor.shutdown(wait=True)
				self._executor = None
			if self.trading_client is not None:
				self._cancel_open_orders()
			self.state.close()
			LOGGER.info("Filo strategy stopped at market close")


def main() -> None:
	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
	FiloStrategy.from_environment().run()


if __name__ == "__main__":
	main()
