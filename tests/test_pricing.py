from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from paperagent.pricing import ModelPrice, PriceTable, load_price_table


def test_price_table_returns_unknown_when_usage_or_model_is_unknown() -> None:
    table = PriceTable(
        version="test",
        models={
            "known": ModelPrice(
                input_usd_per_million_tokens=Decimal("1"),
                output_usd_per_million_tokens=Decimal("1"),
            )
        },
    )

    assert table.estimate(model="missing", input_tokens=1, output_tokens=1) is None
    assert table.estimate(model="known", input_tokens=None, output_tokens=1) is None


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


def test_example_price_table_is_loadable() -> None:
    table = load_price_table(Path("evals/v0_6/price_table.example.json"))

    assert table.version == "operator-example-2026-07"
    assert "replace-with-configured-model" in table.models
