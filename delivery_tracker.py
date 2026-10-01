"""
Delivery percentage tracking for NSE stocks.
High delivery % signals real institutional buying interest,
as opposed to intraday speculation that washes out by close.
"""
import logging
import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def get_delivery_data(ticker: str) -> dict | None:
    """
    Fetch delivery % for a ticker.
    Tries jugaad-data first (which includes deliveryToTradedQuantity),
    then falls back to yfinance info fields.
    Returns dict with delivery_pct, delivery_qty, traded_qty or None.
    """
    # Attempt 1: jugaad-data (already returns this in tradeInfo)
    try:
        from jugaad_data.nse import NSELive
        n = NSELive()
        q = n.stock_quote(ticker)
        trade_info = q.get("tradeInfo", {})
        del_pct = trade_info.get("deliveryToTradedQuantity")
        del_qty = trade_info.get("deliveryquantity") or trade_info.get("deliveryQuantity")
        traded_qty = trade_info.get("totalTradedVolume") or trade_info.get("quantitytraded")

        if del_pct is not None:
            return {
                "delivery_pct": float(del_pct),
                "delivery_qty": int(del_qty) if del_qty else None,
                "traded_qty": int(traded_qty) if traded_qty else None,
                "source": "jugaad-data",
            }
    except Exception as e:
        logger.debug(f"jugaad-data delivery data failed for {ticker}: {e}")

    # Attempt 2: jugaad-data sec_info
    try:
        from jugaad_data.nse import NSELive
        n = NSELive()
        q = n.stock_quote(ticker)
        sec_info = q.get("secInfo", {})
        del_pct = sec_info.get("deliveryTotradedQuantity") or sec_info.get("deliveryToTradedQuantity")
        del_qty = sec_info.get("deliveryQuantity")

        if del_pct is not None:
            return {
                "delivery_pct": float(del_pct),
                "delivery_qty": int(del_qty) if del_qty else None,
                "traded_qty": None,
                "source": "jugaad-data-sec",
            }
    except Exception as e:
        logger.debug(f"jugaad-data secInfo delivery data failed for {ticker}: {e}")

    logger.info(f"Delivery data not available for {ticker}")
    return None


def format_delivery_data(data: dict | None) -> str:
    """Format delivery data for Telegram message."""
    if not data:
        return ""

    pct = data["delivery_pct"]
    # Classify
    if pct >= 70:
        tag = "🟢 STRONG (institutional buying likely)"
    elif pct >= 50:
        tag = "🟡 MODERATE"
    else:
        tag = "🔴 LOW (mostly speculative)"

    parts = [f"\n\n📦 <b>Delivery Data:</b>"]
    parts.append(f"Delivery %: {pct:.1f}% [{tag}]")
    if data.get("delivery_qty"):
        parts.append(f"Delivery Qty: {data['delivery_qty']:,}")
    if data.get("traded_qty"):
        parts.append(f"Total Traded: {data['traded_qty']:,}")

    return "\n".join(parts)
