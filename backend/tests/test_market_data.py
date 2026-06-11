import io
import json

from app.services import market_data


class CoinMetricsSettings:
    coinmetrics_api_base_url = "https://community-api.coinmetrics.io/v4"


class JsonResponse(io.BytesIO):
    def __init__(self, payload: dict) -> None:
        super().__init__(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_bitcoin_prices_parse_coin_metrics_response(monkeypatch):
    monkeypatch.setattr(market_data, "get_settings", lambda: CoinMetricsSettings())
    monkeypatch.setattr(
        market_data,
        "urlopen",
        lambda url, timeout: JsonResponse(
            {
                "data": [
                    {
                        "asset": "btc",
                        "time": "2011-01-01T00:00:00.000000000Z",
                        "PriceUSD": "0.3",
                    }
                ]
            }
        ),
    )

    frame = market_data.fetch_btc_prices()

    assert frame.iloc[0]["date"].isoformat() == "2011-01-01T00:00:00+00:00"
    assert frame.iloc[0]["value"] == 0.3


def test_bitcoin_prices_follow_coin_metrics_pagination(monkeypatch):
    monkeypatch.setattr(market_data, "get_settings", lambda: CoinMetricsSettings())
    responses = iter(
        [
            {
                "data": [{"time": "2011-01-01T00:00:00Z", "PriceUSD": "0.3"}],
                "next_page_token": "next-page",
            },
            {
                "data": [{"time": "2011-01-02T00:00:00Z", "PriceUSD": "0.31"}],
            },
        ]
    )
    requested_urls = []

    def fake_urlopen(url, timeout):
        requested_urls.append(url)
        return JsonResponse(next(responses))

    monkeypatch.setattr(market_data, "urlopen", fake_urlopen)

    frame = market_data.fetch_btc_prices()

    assert frame["value"].tolist() == [0.3, 0.31]
    assert "next_page_token=next-page" in requested_urls[1]
