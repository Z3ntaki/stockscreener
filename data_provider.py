import abc
import datetime
from zoneinfo import ZoneInfo
import logging
import time

logger = logging.getLogger(__name__)

class DataProvider(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @abc.abstractmethod
    def get_quote(self, ticker: str) -> dict | None:
        """Returns dict with keys: ticker, price, prev_close, source, timestamp_ist"""
        pass

class JugaadDataProvider(DataProvider):
    @property
    def name(self) -> str:
        return "jugaad-data"

    def get_quote(self, ticker: str) -> dict | None:
        try:
            from jugaad_data.nse import NSELive
            n = NSELive()
            q = n.stock_quote(ticker)
            
            # Extract price safely
            trade_info = q.get('tradeInfo', {})
            meta_data = q.get('metaData', {})
            
            price = trade_info.get('lastPrice') or meta_data.get('lastPrice') or meta_data.get('closePrice')
            prev_close = meta_data.get('previousClose')
            
            if price is None or prev_close is None:
                raise ValueError("Missing price or prev_close in response")
                
            return {
                "ticker": ticker,
                "price": float(price),
                "prev_close": float(prev_close),
                "source": self.name,
                "timestamp_ist": datetime.datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
            }
        except Exception as e:
            logger.warning(f"{self.name} failed for {ticker}: {e}")
            return None

class NsePythonDataProvider(DataProvider):
    @property
    def name(self) -> str:
        return "nsepython"

    def get_quote(self, ticker: str) -> dict | None:
        try:
            from nsepython import nse_quote
            q = nse_quote(ticker)
            
            price = q.get('priceInfo', {}).get('lastPrice')
            prev_close = q.get('priceInfo', {}).get('previousClose')
            
            if price is None or prev_close is None:
                # nsepython might structure it differently or be blocked
                price = q.get('lastPrice')
                prev_close = q.get('previousClose')
                
            if price is None or prev_close is None:
                raise ValueError("Missing price or prev_close in response")
                
            return {
                "ticker": ticker,
                "price": float(price),
                "prev_close": float(prev_close),
                "source": self.name,
                "timestamp_ist": datetime.datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
            }
        except Exception as e:
            logger.warning(f"{self.name} failed for {ticker}: {e}")
            return None

class YFinanceDataProvider(DataProvider):
    @property
    def name(self) -> str:
        return "yfinance"

    def get_quote(self, ticker: str) -> dict | None:
        try:
            import yfinance as yf
            yf_ticker = f"{ticker}.NS"
            t = yf.Ticker(yf_ticker)
            info = t.info
            
            # Fields vary slightly based on market state
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            prev_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
            
            if current_price is None or prev_close is None:
                raise ValueError("Missing price or prev_close in response")
                
            return {
                "ticker": ticker,
                "price": float(current_price),
                "prev_close": float(prev_close),
                "source": self.name,
                "timestamp_ist": datetime.datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
            }
        except Exception as e:
            logger.warning(f"{self.name} failed for {ticker}: {e}")
            return None

def get_quote_with_fallback(ticker: str, provider_names: list[str], retries: int = 3, backoff: float = 2.0) -> dict | None:
    available_providers = {
        "jugaad-data": JugaadDataProvider(),
        "nsepython": NsePythonDataProvider(),
        "yfinance": YFinanceDataProvider()
    }
    
    providers = []
    for p_name in provider_names:
        if p_name in available_providers:
            providers.append(available_providers[p_name])
            
    if not providers:
        # Fallback to all if config is empty or invalid
        providers = list(available_providers.values())
        
    for p in providers:
        for attempt in range(retries):
            data = p.get_quote(ticker)
            if data:
                return data
            # If failed, apply backoff and retry
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
        # Proceed to next provider after all retries fail
    
    logger.error(f"All providers failed to fetch quote for {ticker}")
    return None
