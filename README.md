# 📈 Binance Futures Swing Bot

EMA(9/21) crossover + RSI(14) filter on 4H candles.  
Trades BTC, ETH, SOL, BNB USDT-M Futures with isolated margin.

---

## Strategy

| Condition | Action |
|-----------|--------|
| EMA9 crosses above EMA21 **and** RSI > 50 | Long |
| EMA9 crosses below EMA21 **and** RSI < 50 | Short |
| Signal reverses while in a position | Close & flip |

**Risk per trade:** 1% of account balance  
**Stop loss:** 2% from entry  
**Take profit:** 4% from entry (2:1 R/R)

---

## Setup (one-time)

### 1. Binance API Keys
1. Log into Binance → Account → API Management
2. Create a new key → enable **Futures trading** (⚠️ do NOT enable withdrawals)
3. Whitelist your Railway IP once deployed (or leave open for now)

### 2. Put code on GitHub
```bash
git init
git add .
git commit -m "Initial bot"
# Create a repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/swing-bot.git
git push -u origin main
```
> ⚠️ Make sure `.env` is in `.gitignore` — never push real API keys

### 3. Deploy to Railway
1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
2. Select your repo
3. Go to **Variables** tab and add:
   - `BINANCE_API_KEY`
   - `BINANCE_API_SECRET`
   - `DRY_RUN=true` (change to `false` when ready)
   - `LEVERAGE=5`
4. Railway will auto-deploy. Check **Logs** tab to confirm it's running.

### 4. Optional: Telegram alerts on iPhone
1. Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot`
2. Copy the token → add `TELEGRAM_TOKEN` in Railway Variables
3. Message your new bot once, then open:  
   `https://api.telegram.org/bot<TOKEN>/getUpdates`  
   Copy the `"id"` value → add as `TELEGRAM_CHAT_ID`

---

## Going Live

1. Run in `DRY_RUN=true` for at least **one full week** and verify logs
2. Check signals match what you'd expect on TradingView (same EMA/RSI settings)
3. Change `DRY_RUN=false` in Railway Variables → redeploy
4. Start with a **small account** (e.g. $200 USDT) to validate live execution

---

## Tuning

All settings are in `config.py`:

| Setting | Default | Notes |
|---------|---------|-------|
| `LEVERAGE` | 5 | Lower = safer. Never go above 10x for swing trading |
| `RISK_PER_TRADE` | 1% | Max % of balance lost per trade if SL hits |
| `STOP_LOSS_PCT` | 2% | Stop distance from entry |
| `TAKE_PROFIT_PCT` | 4% | Target distance from entry |
| `PAIRS` | 4 pairs | Add/remove as desired |
| `EMA_FAST / EMA_SLOW` | 9 / 21 | Classic crossover combo |

---

## ⚠️ Risk Warning

Crypto futures trading involves significant risk of loss, especially with leverage.
This bot is provided for educational purposes. Always:
- Use money you can afford to lose
- Test in dry-run mode first
- Monitor the bot regularly
- Never disable stop-losses
