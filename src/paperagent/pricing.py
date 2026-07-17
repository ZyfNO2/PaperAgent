from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ModelPrice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_usd_per_million_tokens: Decimal = Field(ge=0)
    output_usd_per_million_tokens: Decimal = Field(ge=0)


class PriceTable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(min_length=1)
    models: dict[str, ModelPrice]

    def estimate(
        self,
        *,
        model: str,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> float | None:
        if input_tokens is None or output_tokens is None:
            return None
        price = self.models.get(model)
        if price is None:
            return None
        million = Decimal(1_000_000)
        total = (
            Decimal(input_tokens) * price.input_usd_per_million_tokens
            + Decimal(output_tokens) * price.output_usd_per_million_tokens
        ) / million
        return float(total)
