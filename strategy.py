import pandas as pd
from config import EMA_FAST, EMA_SLOW, RSI_PERIOD, RSI_LONG_MIN, RSI_SHORT_MAX


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss  = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))


def get_signal(df: pd.DataFrame) -> str | None:
    """
    Analyses the last two CLOSED 4H candles and returns:
      'long'  – EMA fast crossed above EMA slow AND RSI > 50
      'short' – EMA fast crossed below EMA slow AND RSI < 50
      None    – no actionable signal

    Index convention:
      df.iloc[-1]  = currently forming candle  (ignored)
      df.iloc[-2]  = last fully closed candle  (signal candle)
      df.iloc[-3]  = candle before that        (for crossover detection)
    """
    close    = df['close']
    fast     = ema(close, EMA_FAST)
    slow     = ema(close, EMA_SLOW)
    rsi_vals = rsi(close, RSI_PERIOD)

    prev_fast, prev_slow = fast.iloc[-3], slow.iloc[-3]
    curr_fast, curr_slow = fast.iloc[-2], slow.iloc[-2]
    curr_rsi             = rsi_vals.iloc[-2]

    bullish_cross = prev_fast <= prev_slow and curr_fast > curr_slow
    bearish_cross = prev_fast >= prev_slow and curr_fast < curr_slow

    if bullish_cross and curr_rsi > RSI_LONG_MIN:
        return 'long'
    if bearish_cross and curr_rsi < RSI_SHORT_MAX:
        return 'short'
    return None
