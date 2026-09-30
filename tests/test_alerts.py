import pytest
import os
import json
from alert_rules import AlertEngine
from unittest.mock import patch, mock_open

@pytest.fixture
def temp_state_file(tmpdir):
    state_file = tmpdir.join("state.json")
    return str(state_file)

@pytest.fixture
def mock_config(tmpdir):
    config_file = tmpdir.join("config.yaml")
    config_file.write("limits:\n  daily_alert_cap: 2\n")
    return str(config_file)

def test_alert_threshold(temp_state_file, mock_config):
    engine = AlertEngine(mock_config, temp_state_file)
    quote = {
        "ticker": "TEST",
        "price": 105.0,
        "prev_close": 100.0,
        "source": "mock",
        "timestamp_ist": "2023-01-01T12:00:00"
    }
    watch_config = {
        "ticker": "TEST",
        "threshold_pct": 3.0
    }
    
    alerts = engine.check_alerts(quote, watch_config)
    assert len(alerts) == 1
    assert "moved 5.00%" in alerts[0]

def test_anti_spam(temp_state_file, mock_config):
    engine = AlertEngine(mock_config, temp_state_file)
    quote = {
        "ticker": "TEST",
        "price": 105.0,
        "prev_close": 100.0,
        "source": "mock",
        "timestamp_ist": "2023-01-01T12:00:00"
    }
    watch_config = {
        "ticker": "TEST",
        "threshold_pct": 3.0
    }
    
    # First time triggers alert
    alerts = engine.check_alerts(quote, watch_config)
    assert len(alerts) == 1
    
    # Second time should NOT trigger alert
    alerts2 = engine.check_alerts(quote, watch_config)
    assert len(alerts2) == 0

def test_support_resistance(temp_state_file, mock_config):
    engine = AlertEngine(mock_config, temp_state_file)
    quote_res = {
        "ticker": "TEST",
        "price": 150.0,
        "prev_close": 140.0,
        "source": "mock",
        "timestamp_ist": "2023-01-01T12:00:00"
    }
    watch_config = {
        "ticker": "TEST",
        "support": 100,
        "resistance": 145,
        "threshold_pct": 10.0
    }
    
    alerts = engine.check_alerts(quote_res, watch_config)
    assert len(alerts) == 1
    assert "crossed resistance!" in alerts[0]
    
    quote_sup = {
        "ticker": "TEST2",
        "price": 90.0,
        "prev_close": 95.0,
        "source": "mock",
        "timestamp_ist": "2023-01-01T12:00:00"
    }
    watch_config_sup = {
        "ticker": "TEST2",
        "support": 92,
        "threshold_pct": 10.0
    }
    alerts2 = engine.check_alerts(quote_sup, watch_config_sup)
    assert len(alerts2) == 1
    assert "crossed support!" in alerts2[0]

def test_daily_cap(temp_state_file, mock_config):
    engine = AlertEngine(mock_config, temp_state_file)
    
    # Set limit to 2 in mock_config
    watch_config = {"threshold_pct": 1.0}
    
    # Alert 1
    quote1 = {"ticker": "T1", "price": 105.0, "prev_close": 100.0, "source": "mock", "timestamp_ist": "x"}
    alerts = engine.check_alerts(quote1, watch_config)
    assert len(alerts) == 1
    
    # Alert 2
    quote2 = {"ticker": "T2", "price": 105.0, "prev_close": 100.0, "source": "mock", "timestamp_ist": "x"}
    alerts = engine.check_alerts(quote2, watch_config)
    assert len(alerts) == 1
    
    # Alert 3 - should be skipped due to cap
    quote3 = {"ticker": "T3", "price": 105.0, "prev_close": 100.0, "source": "mock", "timestamp_ist": "x"}
    alerts = engine.check_alerts(quote3, watch_config)
    assert len(alerts) == 0

@patch('data_provider.YFinanceDataProvider.get_quote')
@patch('data_provider.NsePythonDataProvider.get_quote')
@patch('data_provider.JugaadDataProvider.get_quote')
def test_provider_fallback(jugaad_mock, nse_mock, yf_mock):
    from data_provider import get_quote_with_fallback
    
    jugaad_mock.return_value = None # Fails
    nse_mock.return_value = None # Fails
    yf_mock.return_value = {"ticker": "TEST", "price": 100, "prev_close": 90, "source": "yfinance"} # Succeeds
    
    result = get_quote_with_fallback("TEST", ["jugaad-data", "nsepython", "yfinance"], retries=1)
    
    assert result is not None
    assert result["source"] == "yfinance"
    assert jugaad_mock.called
    assert nse_mock.called
    assert yf_mock.called
