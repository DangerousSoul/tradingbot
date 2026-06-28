"""
Runs in a background thread and listens for Telegram commands.
Supported commands:
  /status  — is the bot alive + open positions + next candle time
  /data    — trade stats and total P&L
  /help    — list of commands
"""
import threading
import logging
import time
from datetime import datetime, timezone

import requests

import trade_log
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger(__name__)


# ── Send ──────────────────────────────────────────────────────────────────────

def _send(chat_id: str, text: str) -> None:
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            'chat_id':    chat_id,
            'text':       text,
            'parse_mode': 'HTML',
        }, timeout=10)
    except Exception as e:
        log.warning(f"Telegram send error: {e}")


# ── Command handlers ──────────────────────────────────────────────────────────

def _cmd_status(chat_id: str, get_positions_fn) -> None:
    """Reply instantly confirming bot is alive, with live position value and P&L."""
    from config import TIMEFRAME
    TIMEFRAME_HOURS = {'1h': 1, '2h': 2, '4h': 4, '6h': 6, '8h': 8, '12h': 12, '1d': 24}
    now        = datetime.now(timezone.utc)
    total_secs = now.hour * 3600 + now.minute * 60 + now.second
    hours      = TIMEFRAME_HOURS.get(TIMEFRAME, 4)
    period     = hours * 3600
    remaining  = period - (total_secs % period)
    hrs        = remaining // 3600
    mins       = (remaining % 3600) // 60

    positions = get_positions_fn()

    if positions:
        lines = []
        for pos in positions:
            pair    = pos['symbol'].replace(':USDT', '')
            side    = pos['side'].upper()
            entry   = pos['entry']
            mark    = pos['mark_price']
            value   = pos['notional']
            pnl     = pos['unrealized_pnl']
            pct     = pos['percentage']
            emoji   = "📈" if pos['side'] == 'long' else "📉"
            pnl_str = f"+${pnl:.2f} (+{pct:.2f}%) 🟢" if pnl >= 0 else f"-${abs(pnl):.2f} ({pct:.2f}%) 🔴"
            lines.append(
                f"{emoji} <b>{side} {pair}</b>\n"
                f"   Entry:  ${entry:,.4f}\n"
                f"   Price:  ${mark:,.4f}\n"
                f"   Value:  ${value:,.2f}\n"
                f"   P&L:    {pnl_str}"
            )
        pos_text = f"<b>Open Positions ({len(positions)}):</b>\n\n" + "\n\n".join(lines)
    else:
        pos_text = "Open Positions: <b>none</b>"

    _send(chat_id, (
        f"✅ <b>Bot is running</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 Next {TIMEFRAME} candle: {hrs}h {mins}m\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{pos_text}\n"
    ))


def _cmd_data(chat_id: str, tracked: dict) -> None:
    from config import STARTING_BALANCE
    stats = trade_log.get_stats(open_count=len(tracked))

    if not stats:
        _send(chat_id, "📊 No closed trades yet. The bot is still running its first signals.")
        return

    total    = stats['total']
    wins     = stats['wins']
    losses   = stats['losses']
    pnl      = stats['total_pnl']
    roi      = round(pnl / STARTING_BALANCE * 100, 2)
    win_rate = round(wins / total * 100, 1) if total else 0

    pnl_str = f"<b>+${pnl:.2f} 🟢</b>"  if pnl >= 0 else f"<b>-${abs(pnl):.2f} 🔴</b>"
    roi_str = f"<b>+{roi}% 🟢</b>"       if roi >= 0 else f"<b>{roi}% 🔴</b>"

    best       = stats['best']
    worst      = stats['worst']
    last       = stats['last']
    best_pair  = best['symbol'].replace(':USDT', '')
    worst_pair = worst['symbol'].replace(':USDT', '')
    last_pair  = last['symbol'].replace(':USDT', '')
    last_pnl   = f"+${last['pnl']:.2f} 🟢" if last['pnl'] >= 0 else f"-${abs(last['pnl']):.2f} 🔴"

    _send(chat_id, (
        f"📊 <b>BOT STATISTICS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Total Trades:  <b>{total}</b>\n"
        f"Wins:          {wins}  ({win_rate}%)\n"
        f"Losses:        {losses}\n"
        f"Open Now:      {stats['open']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Total P&L:     {pnl_str}\n"
        f"Total ROI:     {roi_str}\n"
        f"Start Balance: ${STARTING_BALANCE:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Best Trade:    +${best['pnl']:.2f}  ({best_pair} {best['side'].upper()})\n"
        f"Worst Trade:   -${abs(worst['pnl']):.2f}  ({worst_pair} {worst['side'].upper()})\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Last Trade:    {last_pair} {last['side'].upper()}  {last_pnl}\n"
        f"               {last['time']}\n"
    ))


def _cmd_help(chat_id: str) -> None:
    _send(chat_id, (
        "🤖 <b>Available Commands</b>\n"
        "/status  — is bot running &amp; open positions\n"
        "/data    — trade stats &amp; total P&amp;L\n"
        "/help    — show this message"
    ))


# ── Polling loop ──────────────────────────────────────────────────────────────

def _poll(tracked: dict, get_positions_fn) -> None:
    offset = None
    log.info("Telegram command listener running…")

    while True:
        try:
            url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            resp = requests.get(url, params={'timeout': 30, 'offset': offset}, timeout=35)
            updates = resp.json().get('result', [])

            for update in updates:
                offset  = update['update_id'] + 1
                msg     = update.get('message', {})
                chat_id = str(msg.get('chat', {}).get('id', ''))
                text    = msg.get('text', '').strip().lower()

                # Security: only respond to your own chat
                if chat_id != str(TELEGRAM_CHAT_ID):
                    log.warning(f"Ignored message from unknown chat_id {chat_id}")
                    continue

                if text == '/status':
                    _cmd_status(chat_id, get_positions_fn)
                elif text == '/data':
                    _cmd_data(chat_id, tracked)
                elif text == '/help':
                    _cmd_help(chat_id)

        except Exception as e:
            log.warning(f"Telegram poll error: {e}")
            time.sleep(5)


# ── Public API ────────────────────────────────────────────────────────────────

def start(tracked: dict, get_positions_fn) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.info("Telegram not configured — command listener disabled")
        return
    t = threading.Thread(target=_poll, args=(tracked, get_positions_fn), daemon=True)
    t.start()
    log.info("Telegram listener started  (/status  /data  /help)")
