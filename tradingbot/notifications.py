import requests
import logging
import trade_log
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger(__name__)


def _send(text: str) -> None:
    """Send a raw message to Telegram. No-op if token not set."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            'chat_id':    TELEGRAM_CHAT_ID,
            'text':       text,
            'parse_mode': 'HTML',
        }, timeout=10)
    except Exception as e:
        log.warning(f"Telegram error: {e}")


def notify(text: str) -> None:
    """Generic notification."""
    log.info(f"[TG] {text}")
    _send(text)


def trade_opened(
    symbol: str,
    side: str,
    entry: float,
    sl: float,
    tp: float,
    qty: float,
    risk: float,
    leverage: int,
) -> None:
    """Rich entry notification."""
    direction = "LONG  📈" if side == 'long' else "SHORT 📉"
    notional  = round(qty * entry, 2)
    sl_pct    = abs(round((sl - entry) / entry * 100, 1))
    tp_pct    = abs(round((tp - entry) / entry * 100, 1))
    pair      = symbol.replace(':USDT', '')

    msg = (
        f"🚀 <b>NEW TRADE OPENED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>{pair}</b>  —  {direction}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Entry:      <b>${entry:,.4f}</b>\n"
        f"Stop Loss:  ${sl:,.4f}  (-{sl_pct}%)\n"
        f"Take Prof:  ${tp:,.4f}  (+{tp_pct}%)\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Size:       {qty} units\n"
        f"Notional:   ${notional:,.2f}\n"
        f"Leverage:   {leverage}x\n"
        f"Risk:       ${risk:.2f}\n"
    )
    log.info(f"[TG] Trade opened: {pair} {side} @ {entry}")
    _send(msg)


def trade_closed(
    symbol: str,
    side: str,
    entry: float,
    exit_price: float,
    pnl: float,
    close_type: str,   # 'SL' | 'TP' | 'reversal'
) -> None:
    """Rich close notification with P&L."""
    pair      = symbol.replace(':USDT', '')
    direction = "LONG" if side == 'long' else "SHORT"
    pnl_pct   = round((exit_price - entry) / entry * 100 * (1 if side == 'long' else -1), 2)
    profit    = pnl >= 0

    if close_type == 'TP':
        header = "✅ <b>TAKE PROFIT HIT</b>"
    elif close_type == 'SL':
        header = "🛑 <b>STOP LOSS HIT</b>"
    else:
        header = "🔄 <b>POSITION CLOSED (signal reversal)</b>"

    pnl_line = (
        f"PnL:  <b>+${pnl:.2f}  (+{pnl_pct}%) 🟢</b>"
        if profit else
        f"PnL:  <b>-${abs(pnl):.2f}  ({pnl_pct}%) 🔴</b>"
    )

    msg = (
        f"{header}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>{pair}</b>  —  {direction}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Entry:  ${entry:,.4f}\n"
        f"Exit:   ${exit_price:,.4f}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{pnl_line}\n"
    )
    log.info(f"[TG] Trade closed: {pair} {side} pnl={pnl:.2f}")
    trade_log.record(symbol, side, entry, exit_price, pnl, close_type)
    _send(msg)
