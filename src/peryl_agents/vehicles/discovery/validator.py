from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field, ConfigDict, model_validator


class VehicleDiscovery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    make: str = Field(max_length=128)
    model: str = Field(max_length=128)
    trim: str= Field(max_length=128)
    model_year_start: int= Field(ge=1960, le=2030)
    model_year_end: int= Field(ge=1960, le=2030)

    @model_validator(mode="after")
    def validate_model_year_range(self):
        if self.model_year_end < self.model_year_start:
            raise ValueError("model_year_end must be greater than or equal to model_year_start")
        return self

class VehicleDiscoveryBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicles: list[VehicleDiscovery] = Field(max_length=25)

class SourcedValue(BaseModel):
    value: int | float | str
    source_url: HttpUrl
    date_set: datetime
    confidence: int = Field(ge=1, le=5)


class VehicleSpecCandidate(BaseModel):
    width_mm: SourcedValue | None = None
    length_mm: SourcedValue | None = None
    height_mm: SourcedValue | None = None
    curb_weight_kg: SourcedValue | None = None
