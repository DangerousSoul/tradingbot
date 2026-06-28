import logging
import time
from datetime import datetime, timezone

import ccxt
import pandas as pd

import notifications
from config import (    API_KEY, API_SECRET, PAIRS, TIMEFRAME, CANDLES_NEEDED,
    LEVERAGE, RISK_PER_TRADE, STOP_LOSS_PCT, TAKE_PROFIT_PCT,
    MAX_POSITIONS, DRY_RUN,
)
from strategy import get_signal

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log'),
    ],
)
log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

# Maps timeframe string to hours
TIMEFRAME_HOURS = {'1h': 1, '2h': 2, '4h': 4, '6h': 6, '8h': 8, '12h': 12, '1d': 24}

def seconds_to_next_candle() -> float:
    hours      = TIMEFRAME_HOURS.get(TIMEFRAME, 4)
    now        = datetime.now(timezone.utc)
    total_secs = now.hour * 3600 + now.minute * 60 + now.second
    period     = hours * 3600
    remaining  = period - (total_secs % period) + 15
    return max(remaining, 60)


def calc_quantity(balance: float, entry_price: float) -> float:
    risk_amount = balance * RISK_PER_TRADE
    return risk_amount / (entry_price * STOP_LOSS_PCT)


def calc_sl_tp(entry: float, side: str) -> tuple[float, float]:
    if side == 'long':
        return round(entry * (1 - STOP_LOSS_PCT), 4), round(entry * (1 + TAKE_PROFIT_PCT), 4)
    return round(entry * (1 + STOP_LOSS_PCT), 4), round(entry * (1 - TAKE_PROFIT_PCT), 4)


def calc_pnl(side: str, entry: float, exit_price: float, qty: float) -> float:
    if side == 'long':
        return (exit_price - entry) * qty
    return (entry - exit_price) * qty


def close_type_from_price(side: str, exit_price: float, sl: float, tp: float) -> str:
    """Guess whether SL or TP was hit based on exit price."""
    tolerance = 0.003  # 0.3%
    if side == 'long':
        if exit_price <= sl * (1 + tolerance):
            return 'SL'
        if exit_price >= tp * (1 - tolerance):
            return 'TP'
    else:
        if exit_price >= sl * (1 - tolerance):
            return 'SL'
        if exit_price <= tp * (1 + tolerance):
            return 'TP'
    return 'reversal'


# ── Bot ───────────────────────────────────────────────────────────────────────

class SwingBot:
    def __init__(self):
        self.exchange = ccxt.binanceusdm({
            'apiKey':         API_KEY,
            'secret':         API_SECRET,
            'options':        {'defaultType': 'future'},
            'enableRateLimit': True,
        })

        # Tracks positions we've opened: {symbol: {side, entry, qty, sl, tp, risk}}
        self.tracked: dict[str, dict] = {}

        if DRY_RUN:
            log.info("🧪 DRY RUN MODE — no real orders will be placed")

    # ── Exchange helpers ──────────────────────────────────────────────────────

    def _setup_pair(self, symbol: str) -> None:
        try:
            self.exchange.set_leverage(LEVERAGE, symbol)
            self.exchange.set_margin_mode('isolated', symbol)
        except Exception as e:
            log.warning(f"Leverage/margin setup for {symbol}: {e}")

    def _ohlcv(self, symbol: str) -> pd.DataFrame:
        rows = self.exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=CANDLES_NEEDED)
        df   = pd.DataFrame(rows, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        return df

    def _free_usdt(self) -> float:
        return float(self.exchange.fetch_balance()['USDT']['free'])

    def _open_position(self, symbol: str) -> dict | None:
        # In DRY_RUN, use our in-memory tracker instead of hitting the exchange
        if DRY_RUN:
            if symbol in self.tracked:
                info = self.tracked[symbol]
                return {'side': info['side'], 'contracts': info['qty']}
            return None
        try:
            for p in self.exchange.fetch_positions([symbol]):
                if p['contracts'] and abs(float(p['contracts'])) > 0:
                    return p
        except Exception as e:
            log.error(f"fetch_positions({symbol}): {e}")
        return None

    def _count_open_positions(self) -> int:
        return sum(1 for sym in PAIRS if self._open_position(sym) is not None)

    def _cancel_orders(self, symbol: str) -> None:
        try:
            self.exchange.cancel_all_orders(symbol)
        except Exception as e:
            log.warning(f"cancel_all_orders({symbol}): {e}")

    def _precision_qty(self, symbol: str, qty: float) -> float:
        market  = self.exchange.market(symbol)
        min_qty = market['limits']['amount']['min'] or 0
        qty     = max(qty, min_qty)
        return float(self.exchange.amount_to_precision(symbol, qty))

    # ── SL/TP hit detection ───────────────────────────────────────────────────

    def _get_last_exit_price(self, symbol: str) -> float | None:
        """Fetch the most recent trade fill price for a symbol."""
        try:
            trades = self.exchange.fetch_my_trades(symbol, limit=5)
            if trades:
                return float(trades[-1]['price'])
        except Exception as e:
            log.warning(f"Could not fetch trades for {symbol}: {e}")
        return None

    def _check_external_closes(self) -> None:
        """
        Called at the start of each cycle.

        DRY_RUN: checks if current price has crossed the simulated SL or TP.
        Live mode: checks if a position we opened is no longer on the exchange.
        """
        if DRY_RUN:
            for symbol, info in list(self.tracked.items()):
                try:
                    price = float(self.exchange.fetch_ticker(symbol)['last'])
                    side, sl, tp = info['side'], info['sl'], info['tp']
                    hit = None
                    if side == 'long':
                        if price <= sl:  hit = 'SL'
                        elif price >= tp: hit = 'TP'
                    else:
                        if price >= sl:  hit = 'SL'
                        elif price <= tp: hit = 'TP'

                    if hit:
                        exit_price = sl if hit == 'SL' else tp
                        pnl = calc_pnl(side, info['entry'], exit_price, info['qty'])
                        log.info(f"[DRY RUN] {symbol} {hit} hit @ {exit_price}")
                        notifications.trade_closed(symbol, side, info['entry'], exit_price, pnl, hit)
                        del self.tracked[symbol]
                except Exception as e:
                    log.warning(f"DRY RUN SL/TP check error for {symbol}: {e}")
            return

        # ── Live mode ─────────────────────────────────────────────────────────
        for symbol, info in list(self.tracked.items()):
            if self._open_position(symbol) is None:
                log.info(f"Position on {symbol} was closed externally (SL/TP hit)")
                exit_price = self._get_last_exit_price(symbol)
                if exit_price:
                    pnl   = calc_pnl(info['side'], info['entry'], exit_price, info['qty'])
                    ctype = close_type_from_price(info['side'], exit_price, info['sl'], info['tp'])
                    notifications.trade_closed(symbol, info['side'], info['entry'], exit_price, pnl, ctype)
                else:
                    notifications.notify(f"📊 {symbol} position closed (SL or TP hit — could not fetch exit price)")
                del self.tracked[symbol]

    # ── Order execution ───────────────────────────────────────────────────────

    def _enter(self, symbol: str, side: str, qty: float, sl: float, tp: float, balance: float) -> None:
        order_side = 'buy'  if side == 'long' else 'sell'
        exit_side  = 'sell' if side == 'long' else 'buy'
        risk       = round(balance * RISK_PER_TRADE, 2)

        log.info(f"{'📈' if side == 'long' else '📉'} {side.upper()} {symbol} qty={qty} SL={sl} TP={tp}")

        if DRY_RUN:
            log.info("   [DRY RUN] Order skipped.")
            # Still track it so we can simulate close notifications
            entry_price = float(self.exchange.fetch_ticker(symbol)['last'])
            self.tracked[symbol] = {'side': side, 'entry': entry_price, 'qty': qty, 'sl': sl, 'tp': tp, 'risk': risk}
            notifications.trade_opened(symbol, side, entry_price, sl, tp, qty, risk, LEVERAGE)
            return

        try:
            order       = self.exchange.create_order(symbol, 'market', order_side, qty)
            entry_price = float(order.get('average') or order.get('price') or sl / (1 - STOP_LOSS_PCT))

            self.exchange.create_order(symbol, 'STOP_MARKET', exit_side, qty, None,
                                       {'stopPrice': sl, 'reduceOnly': True})
            self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', exit_side, qty, None,
                                       {'stopPrice': tp, 'reduceOnly': True})

            # Track this position for P&L reporting
            self.tracked[symbol] = {
                'side':  side,
                'entry': entry_price,
                'qty':   qty,
                'sl':    sl,
                'tp':    tp,
                'risk':  risk,
            }

            notifications.trade_opened(symbol, side, entry_price, sl, tp, qty, risk, LEVERAGE)

        except Exception as e:
            log.error(f"Entry failed for {symbol}: {e}")
            notifications.notify(f"❌ Entry failed — {symbol}: {e}")

    def _close(self, symbol: str, position: dict) -> None:
        """Close a position manually (signal reversal) and report P&L."""
        side     = position['side']
        qty      = abs(float(position['contracts']))
        exit_dir = 'sell' if side == 'long' else 'buy'

        log.info(f"🔄 Closing {side} on {symbol}")

        if DRY_RUN:
            log.info("   [DRY RUN] Close skipped.")
            if symbol in self.tracked:
                # Simulate exit at current price
                ticker     = self.exchange.fetch_ticker(symbol)
                exit_price = float(ticker['last'])
                info       = self.tracked.pop(symbol)
                pnl        = calc_pnl(side, info['entry'], exit_price, qty)
                notifications.trade_closed(symbol, side, info['entry'], exit_price, pnl, 'reversal')
            return

        try:
            self._cancel_orders(symbol)
            self.exchange.create_order(symbol, 'market', exit_dir, qty, None, {'reduceOnly': True})

            # Get actual exit price from last trade
            exit_price = self._get_last_exit_price(symbol) or float(position.get('markPrice', 0))

            if symbol in self.tracked and exit_price:
                info = self.tracked.pop(symbol)
                pnl  = calc_pnl(side, info['entry'], exit_price, qty)
                notifications.trade_closed(symbol, side, info['entry'], exit_price, pnl, 'reversal')
            else:
                notifications.notify(f"🔄 {symbol} {side} position closed (reversal)")

        except Exception as e:
            log.error(f"Close failed for {symbol}: {e}")
            notifications.notify(f"❌ Close failed — {symbol}: {e}")

    # ── Per-pair logic ────────────────────────────────────────────────────────

    def _run_pair(self, symbol: str) -> None:
        log.info(f"── {symbol} ──")
        try:
            df     = self._ohlcv(symbol)
            signal = get_signal(df)
            pos    = self._open_position(symbol)

            if pos:
                pos_side = pos['side']
                if signal and signal != pos_side:
                    log.info(f"Signal reversed → closing {pos_side}")
                    self._close(symbol, pos)
                    pos = None
                else:
                    log.info(f"Holding {pos_side} — no reversal")
                    return

            if not signal:
                log.info("No signal.")
                return

            if self._count_open_positions() >= MAX_POSITIONS:
                log.info(f"Max {MAX_POSITIONS} positions open. Skipping.")
                return

            balance     = self._free_usdt()
            entry_price = float(df['close'].iloc[-2])
            qty         = self._precision_qty(symbol, calc_quantity(balance, entry_price))
            sl, tp      = calc_sl_tp(entry_price, signal)

            self._setup_pair(symbol)
            self._enter(symbol, signal, qty, sl, tp, balance)

        except Exception as e:
            log.error(f"Error on {symbol}: {e}")

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        import telegram_listener
        log.info("🤖 Swing Bot starting up…")
        self.exchange.load_markets()
        telegram_listener.start(self.tracked)

        while True:
            log.info("═══ Cycle start ═══")

            # Check if any of our tracked positions were closed by SL/TP
            self._check_external_closes()

            for symbol in PAIRS:
                self._run_pair(symbol)
                time.sleep(1)

            wait = seconds_to_next_candle()
            log.info(f"Sleeping {wait / 60:.1f} min until next {TIMEFRAME} candle…")
            time.sleep(wait)
