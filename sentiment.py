"""
Sentiment analysis module.
Uses Gemini AI when GEMINI_API_KEY is set, otherwise falls back to VADER.
"""
import os
import logging

logger = logging.getLogger(__name__)


def _analyze_with_gemini(headlines: list[str], ticker: str) -> list[dict]:
    """
    Use Gemini to analyze news headlines and return sentiment + reasoning.
    Returns list of dicts: [{"title": ..., "sentiment": ..., "reason": ...}]
    """
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)

    headlines_text = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines))
    prompt = f"""You are a stock market analyst. Analyze these news headlines for {ticker} (an Indian NSE stock).

For EACH headline, respond with exactly this format (one per line):
HEADLINE_NUMBER|SENTIMENT|ONE_LINE_REASON

Where SENTIMENT is exactly one of: BULLISH, BEARISH, NEUTRAL

Headlines:
{headlines_text}

Respond ONLY with the formatted lines, nothing else."""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = response.text.strip()
        results = []
        for i, line in enumerate(text.split("\n")):
            parts = line.strip().split("|", 2)
            if len(parts) == 3:
                sentiment = parts[1].strip().upper()
                reason = parts[2].strip()
                title = headlines[i] if i < len(headlines) else ""
                emoji = {"BULLISH": "🟢", "BEARISH": "🔴"}.get(sentiment, "⚪")
                results.append({
                    "title": title,
                    "sentiment": f"{emoji} {sentiment}",
                    "reason": reason,
                })
        return results
    except Exception as e:
        logger.warning(f"Gemini analysis failed: {e}")
        raise


def _analyze_with_vader(headlines: list[str]) -> list[dict]:
    """Fallback: use VADER for basic sentiment scoring."""
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    analyzer = SentimentIntensityAnalyzer()
    results = []
    for title in headlines:
        score = analyzer.polarity_scores(title)
        compound = score["compound"]
        if compound >= 0.05:
            sentiment = "🟢 POSITIVE"
        elif compound <= -0.05:
            sentiment = "🔴 NEGATIVE"
        else:
            sentiment = "⚪ NEUTRAL"
        results.append({
            "title": title,
            "sentiment": sentiment,
            "reason": None,
        })
    return results


def get_news_and_sentiment(ticker: str) -> str:
    """
    Fetch news for a ticker and analyze sentiment.
    Uses Gemini AI if available, falls back to VADER.
    Returns formatted string for Telegram.
    """
    try:
        import yfinance as yf
        news = yf.Ticker(f"{ticker}.NS").news
        if not news:
            return "\n\n📰 No recent news found."

        # Extract headlines and URLs
        headlines = []
        urls = []
        for item in news[:3]:  # Top 3 headlines
            content = item.get("content", {})
            if not content:
                continue
            title = content.get("title", "")
            url_data = content.get("clickThroughUrl", {})
            link = url_data.get("url", "") if url_data else ""
            if title:
                headlines.append(title)
                urls.append(link)

        if not headlines:
            return "\n\n📰 No recent news found."

        # Try Gemini first, fall back to VADER
        use_gemini = bool(os.environ.get("GEMINI_API_KEY"))
        engine_name = ""
        try:
            if use_gemini:
                results = _analyze_with_gemini(headlines, ticker)
                engine_name = " (Gemini AI)"
            else:
                results = _analyze_with_vader(headlines)
                engine_name = " (VADER)"
        except Exception:
            results = _analyze_with_vader(headlines)
            engine_name = " (VADER fallback)"

        text = f"\n\n📰 <b>News & Sentiment{engine_name}:</b>\n"
        for i, r in enumerate(results):
            text += f"• {r['title']} [{r['sentiment']}]\n"
            if r.get("reason"):
                text += f"  💡 {r['reason']}\n"
            if i < len(urls) and urls[i]:
                text += f"  <a href='{urls[i]}'>Read article</a>\n"
        return text

    except Exception as e:
        logger.warning(f"Failed to fetch news for {ticker}: {e}")
        return ""
