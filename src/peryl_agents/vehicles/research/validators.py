from typing import Annotated

from pydantic import BaseModel, HttpUrl, Field, ConfigDict, WithJsonSchema, model_validator


TIRE_CLASSES = {1: "touring_all_season",
                2: "performance_all_season",
                3: "all_weather",
                4: "summer",
                5: "performance_summer",
                6: "winter",
                7: "studded_winter",
                8: "all_terrain"}


class SourcedValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int = Field(gt=0, strict=True)
    # Validate URLs locally without emitting an unsupported URI schema format.
    source_url: Annotated[HttpUrl, WithJsonSchema({"type": "string"})]
    confidence: int = Field(ge=1, le=5, strict=True)

class VehicleSpecCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_id: int = Field(gt=0, strict=True)
    width_mm: SourcedValue | None
    length_mm: SourcedValue | None
    height_mm: SourcedValue | None
    curb_weight_kg: SourcedValue | None
    stock_tire_class: SourcedValue | None

    @model_validator(mode="after")
    def validate_stock_tire_class(self):
        if self.stock_tire_class is not None:
            if self.stock_tire_class.value not in TIRE_CLASSES:
                raise ValueError("stock_tire_class must use a known tire class ID")
        return self
