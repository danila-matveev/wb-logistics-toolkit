# tests/shared/wb_api/test_client.py
import pytest
import httpx
from unittest.mock import patch, MagicMock

from shared.wb_api.client import WBClient


def test_client_sets_authorization_header():
    client = WBClient(token="test_token_abc")
    assert client._headers["Authorization"] == "test_token_abc"


def test_client_get_calls_correct_url():
    client = WBClient(token="tok")
    mock_response = {"data": [{"id": 1}]}

    with patch("httpx.Client") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.return_value.__enter__.return_value.get.return_value = mock_resp

        result = client.get(
            base="https://statistics-api.wildberries.ru",
            path="/api/v1/supplier/orders",
            params={"dateFrom": "2026-01-01"},
        )

    assert result == mock_response
    call_args = mock_httpx.return_value.__enter__.return_value.get.call_args
    assert call_args[0][0] == "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
    assert call_args[1]["params"]["dateFrom"] == "2026-01-01"


def test_client_raises_on_http_error():
    client = WBClient(token="tok")

    with patch("httpx.Client") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=MagicMock()
        )
        mock_httpx.return_value.__enter__.return_value.get.return_value = mock_resp

        with pytest.raises(httpx.HTTPStatusError):
            client.get(
                base="https://statistics-api.wildberries.ru",
                path="/api/v1/supplier/orders",
            )


def test_client_default_timeout_is_30():
    client = WBClient(token="tok")
    assert client.timeout == 30.0


def test_client_custom_timeout():
    client = WBClient(token="tok", timeout=60.0)
    assert client.timeout == 60.0


def test_client_post_calls_correct_url():
    client = WBClient(token="tok")
    mock_response = {"result": "ok"}

    with patch("httpx.Client") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.return_value.__enter__.return_value.post.return_value = mock_resp

        result = client.post(
            base="https://content-api.wildberries.ru",
            path="/content/v2/get/cards/list",
            json={"settings": {"cursor": {"nmIDs": [123], "limit": 100}}},
        )

    assert result == mock_response
    call_args = mock_httpx.return_value.__enter__.return_value.post.call_args
    assert call_args[0][0] == "https://content-api.wildberries.ru/content/v2/get/cards/list"
    assert call_args[1]["json"]["settings"]["cursor"]["nmIDs"] == [123]
