"""
Saves every closed trade to trades.json.
Survives bot restarts on Railway.
"""
import json
import os
import logging
from datetime import datetime

LOG_FILE = 'trades.json'
log = logging.getLogger(__name__)


def _load() -> dict:
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Could not read trade log: {e}")
    return {'trades': []}


def _save(data: dict) -> None:
    try:
        with open(LOG_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error(f"Could not save trade log: {e}")


def record(symbol: str, side: str, entry: float, exit_price: float,
           pnl: float, close_type: str) -> None:
    """Append a closed trade to the log."""
    data = _load()
    data['trades'].append({
        'symbol':     symbol,
        'side':       side,
        'entry':      round(entry, 4),
        'exit':       round(exit_price, 4),
        'pnl':        round(pnl, 4),
        'close_type': close_type,
        'time':       datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
    })
    _save(data)
    log.info(f"Trade logged: {symbol} {side} pnl={pnl:.2f}")


def get_stats(open_count: int = 0) -> dict:
    """Return aggregated stats for the /data command."""
    trades = _load()['trades']

    if not trades:
        return None

    pnls   = [t['pnl'] for t in trades]
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    best   = max(trades, key=lambda t: t['pnl'])
    worst  = min(trades, key=lambda t: t['pnl'])
    last   = trades[-1]

    return {
        'total':      len(trades),
        'wins':       len(wins),
        'losses':     len(losses),
        'total_pnl':  round(sum(pnls), 2),
        'best':       best,
        'worst':      worst,
        'last':       last,
        'open':       open_count,
    }
