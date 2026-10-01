"""
Technical indicators module: RSI, MACD, and Moving Average crossovers.
Uses the bulk 10-day DataFrame from yfinance when available,
otherwise fetches history for a single ticker.
"""
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def compute_rsi(closes: pd.Series, period: int = 14) -> float | None:
    """Compute the Relative Strength Index for the latest bar."""
    if len(closes) < period + 1:
        return None
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    latest = rsi.dropna()
    return round(float(latest.iloc[-1]), 2) if len(latest) > 0 else None


def compute_macd(closes: pd.Series,
                 fast: int = 12, slow: int = 26, signal: int = 9) -> dict | None:
    """Return MACD line, signal line and histogram for the latest bar."""
    if len(closes) < slow + signal:
        return None
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {
        "macd": round(float(macd_line.iloc[-1]), 2),
        "signal": round(float(signal_line.iloc[-1]), 2),
        "histogram": round(float(histogram.iloc[-1]), 2),
    }


def compute_ma_crossover(closes: pd.Series,
                         short_window: int = 50,
                         long_window: int = 200) -> dict | None:
    """Detect golden cross / death cross between two moving averages."""
    if len(closes) < long_window + 1:
        return None
    sma_short = closes.rolling(window=short_window).mean()
    sma_long = closes.rolling(window=long_window).mean()

    current_short = sma_short.iloc[-1]
    current_long = sma_long.iloc[-1]
    prev_short = sma_short.iloc[-2]
    prev_long = sma_long.iloc[-2]

    cross = None
    if prev_short <= prev_long and current_short > current_long:
        cross = "golden_cross"
    elif prev_short >= prev_long and current_short < current_long:
        cross = "death_cross"

    return {
        "sma_short": round(float(current_short), 2),
        "sma_long": round(float(current_long), 2),
        "cross": cross,
    }


def get_technicals_for_ticker(ticker: str) -> dict:
    """
    Fetch ~1 year of daily history from yfinance and compute all indicators.
    Returns a dict with keys: rsi, macd, ma_cross, each may be None on failure.
    """
    result = {"rsi": None, "macd": None, "ma_cross": None}
    try:
        import yfinance as yf
        df = yf.download(f"{ticker}.NS", period="1y", progress=False)
        if df is None or df.empty:
            return result
        closes = df["Close"].squeeze()
        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]
        result["rsi"] = compute_rsi(closes)
        result["macd"] = compute_macd(closes)
        result["ma_cross"] = compute_ma_crossover(closes)
    except Exception as e:
        logger.warning(f"Failed to compute technicals for {ticker}: {e}")
    return result


def format_technicals(technicals: dict) -> str:
    """Format the technicals dict into a human-readable string for Telegram."""
    parts = []

    rsi = technicals.get("rsi")
    if rsi is not None:
        if rsi >= 70:
            rsi_tag = "⚠️ OVERBOUGHT"
        elif rsi <= 30:
            rsi_tag = "🔥 OVERSOLD"
        else:
            rsi_tag = "✅ Normal"
        parts.append(f"RSI(14): {rsi} [{rsi_tag}]")

    macd = technicals.get("macd")
    if macd:
        direction = "📈 Bullish" if macd["histogram"] > 0 else "📉 Bearish"
        parts.append(f"MACD: {macd['macd']} | Signal: {macd['signal']} [{direction}]")

    ma = technicals.get("ma_cross")
    if ma:
        if ma["cross"] == "golden_cross":
            parts.append(f"⭐ GOLDEN CROSS! SMA50={ma['sma_short']} > SMA200={ma['sma_long']}")
        elif ma["cross"] == "death_cross":
            parts.append(f"💀 DEATH CROSS! SMA50={ma['sma_short']} < SMA200={ma['sma_long']}")
        else:
            parts.append(f"SMA50: {ma['sma_short']} | SMA200: {ma['sma_long']}")

    if not parts:
        return ""
    return "\n\n📊 <b>Technical Indicators:</b>\n" + "\n".join(parts)
