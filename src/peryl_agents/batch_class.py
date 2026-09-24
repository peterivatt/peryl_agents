from typing import Generic, TypeVar

from pydantic import BaseModel, Field, ConfigDict


T = TypeVar("T", bound=BaseModel)


class DataBatch(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    data: list[T] = Field(max_length=25)
