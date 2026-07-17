from __future__ import annotations

from decimal import Decimal

from paperagent.pricing import ModelPrice, PriceTable


def test_price_table_returns_unknown_when_usage_or_model_is_unknown() -> None:
    table = PriceTable(version="test", models={})

    assert table.estimate(model="missing", input_tokens=1, output_tokens=1) is None
    assert table.estimate(model="missing", input_tokens=None, output_tokens=1) is None


def test_price_table_estimates_known_model() -> None:
    table = PriceTable(
        version="test",
        models={
            "model": ModelPrice(
                input_usd_per_million_tokens=Decimal("2"),
                output_usd_per_million_tokens=Decimal("6"),
            )
        },
    )

    assert table.estimate(model="model", input_tokens=1_000, output_tokens=500) == 0.005
