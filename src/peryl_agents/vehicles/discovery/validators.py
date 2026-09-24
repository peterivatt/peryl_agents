
from pydantic import BaseModel, Field, ConfigDict, model_validator

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