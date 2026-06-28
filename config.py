import os
from dotenv import load_dotenv

load_dotenv()

# ── Binance API ───────────────────────────────────────────────────────────────
API_KEY    = os.getenv('BINANCE_API_KEY', '')
API_SECRET = os.getenv('BINANCE_API_SECRET', '')

# ── Safety: set DRY_RUN=false in Railway env vars when ready to go live ───────
DRY_RUN = os.getenv('DRY_RUN', 'true').lower() == 'true'

# ── Trading Pairs (USDT-M Futures) ────────────────────────────────────────────
PAIRS = [
    'BTC/USDT:USDT',
'ETH/USDT:USDT',
'SOL/USDT:USDT',
'BNB/USDT:USDT',
'XRP/USDT:USDT',
'DOGE/USDT:USDT',
'ADA/USDT:USDT',
'AVAX/USDT:USDT',
'LINK/USDT:USDT',
'TRX/USDT:USDT',
'SUI/USDT:USDT',
'LTC/USDT:USDT',
'BCH/USDT:USDT',
'DOT/USDT:USDT',
'APT/USDT:USDT',
'ARB/USDT:USDT',
'OP/USDT:USDT',
'ATOM/USDT:USDT',
'NEAR/USDT:USDT',
'FIL/USDT:USDT',
'ETC/USDT:USDT',
'UNI/USDT:USDT',
'AAVE/USDT:USDT',
'INJ/USDT:USDT',
'SEI/USDT:USDT',
'WIF/USDT:USDT',
'PEPE/USDT:USDT',
'FET/USDT:USDT',
'RENDER/USDT:USDT',
'TAO/USDT:USDT',
'ONDO/USDT:USDT',
'JUP/USDT:USDT',
'ENA/USDT:USDT',
'TON/USDT:USDT',
'HBAR/USDT:USDT',
'SHIB/USDT:USDT',
'CRV/USDT:USDT',
'SNX/USDT:USDT',
'MKR/USDT:USDT',
'ICP/USDT:USDT',
'RUNE/USDT:USDT',
'GRT/USDT:USDT',
'ALGO/USDT:USDT',
'FLOW/USDT:USDT',
'EGLD/USDT:USDT',
'VET/USDT:USDT',
'THETA/USDT:USDT',
'SAND/USDT:USDT',
'MANA/USDT:USDT',
'AXS/USDT:USDT',
'KAS/USDT:USDT',
'STX/USDT:USDT',
'IMX/USDT:USDT',
'TIA/USDT:USDT',
'PYTH/USDT:USDT',
'NOT/USDT:USDT',
'WLD/USDT:USDT',
'ZRO/USDT:USDT',
'PENDLE/USDT:USDT',
'1000PEPE/USDT:USDT'
]

# ── Timeframe & Candle Lookback ───────────────────────────────────────────────
TIMEFRAME      = '1h'
CANDLES_NEEDED = 100

# ── Leverage ──────────────────────────────────────────────────────────────────
# ⚠️  Start low (3–5x). High leverage = fast liquidation.
LEVERAGE = int(os.getenv('LEVERAGE', '5'))

# ── EMA Crossover + RSI Parameters ───────────────────────────────────────────
EMA_FAST       = 9
EMA_SLOW       = 21
RSI_PERIOD     = 14
RSI_LONG_MIN   = 50   # RSI must be above this to enter long
RSI_SHORT_MAX  = 50   # RSI must be below this to enter short

# ── Risk Management ───────────────────────────────────────────────────────────
RISK_PER_TRADE   = 0.01   # 1% of account balance risked per trade
STOP_LOSS_PCT    = 0.02   # 2% stop loss from entry
TAKE_PROFIT_PCT  = 0.04   # 4% take profit → 2:1 reward/risk
MAX_POSITIONS    = 4      # Max simultaneous open positions

# ── Optional: Telegram alerts to your iPhone ─────────────────────────────────
TELEGRAM_TOKEN   = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
