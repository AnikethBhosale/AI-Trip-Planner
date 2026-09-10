from datetime import date
from pydantic import BaseModel, Field, model_validator


class TripRequest(BaseModel):
    departure_city: str
    destination_city: str
    departure_date: date
    return_date: date
    travelers: int = Field(ge=1, le=12)
    budget: int = Field(gt=0)
    currency: str
    travel_style: str
    accommodation_level: str
    interests: list[str] = Field(min_length=1)
    dietary_requirements: str
    pace: str
    extra_details: str = ""

    @model_validator(mode="after")
    def dates_are_valid(self):
        if self.return_date <= self.departure_date:
            raise ValueError("Return date must be after departure date.")
        return self

    def as_prompt(self) -> str:
        return self.model_dump_json(indent=2)
