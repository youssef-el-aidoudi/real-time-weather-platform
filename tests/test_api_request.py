"""
Tests for scripts/api_request.py
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from api_request import fetch_data


class TestFetchData:
    def test_success_returns_json(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"current": {"temperature_2m": 22.5}}
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            result = fetch_data("https://api.open-meteo.com/test")

        assert result == {"current": {"temperature_2m": 22.5}}
        mock_resp.raise_for_status.assert_called_once()

    def test_raises_after_all_retries_exhausted(self):
        with patch(
            "requests.get",
            side_effect=requests.ConnectionError("Connection refused"),
        ):
            with pytest.raises(requests.ConnectionError):
                fetch_data("https://api.open-meteo.com/test", max_retries=2, backoff=0.01)

    def test_retries_on_transient_error_then_succeeds(self):
        mock_success = MagicMock()
        mock_success.json.return_value = {"ok": True}
        mock_success.raise_for_status = MagicMock()

        side_effects = [
            requests.ConnectionError("transient"),
            mock_success,
        ]
        with patch("requests.get", side_effect=side_effects):
            result = fetch_data("https://api.open-meteo.com/test", max_retries=3, backoff=0.01)

        assert result == {"ok": True}

    def test_http_error_raises(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(requests.HTTPError):
                fetch_data("https://api.open-meteo.com/test", max_retries=1, backoff=0.01)
