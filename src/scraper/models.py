"""Data models for Lotto Max draws."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class LottoMaxDraw(BaseModel):
    """Model representing a single Lotto Max draw."""

    draw_date: datetime = Field(..., description="Date of the draw")
    draw_number: int = Field(..., description="Unique draw number")
    winning_numbers: List[int] = Field(
        ...,
        description="Seven main winning numbers",
        min_length=7,
        max_length=7
    )
    bonus_number: int = Field(..., description="Bonus number")
    jackpot_amount: Optional[Decimal] = Field(
        None,
        description="Jackpot amount in CAD"
    )
    winners: Optional[int] = Field(
        None,
        description="Number of jackpot winners"
    )
    maxmillions: Optional[List[List[int]]] = Field(
        None,
        description="MaxMillions winning numbers (multiple draws possible)"
    )

    @field_validator('winning_numbers')
    @classmethod
    def validate_winning_numbers(cls, v: List[int]) -> List[int]:
        """Validate that winning numbers are between 1 and 50."""
        for num in v:
            if not 1 <= num <= 50:
                raise ValueError(f"Winning number {num} must be between 1 and 50")
        if len(set(v)) != len(v):
            raise ValueError("Winning numbers must be unique")
        return sorted(v)

    @field_validator('bonus_number')
    @classmethod
    def validate_bonus_number(cls, v: int) -> int:
        """Validate that bonus number is between 1 and 50."""
        if not 1 <= v <= 50:
            raise ValueError(f"Bonus number {v} must be between 1 and 50")
        return v

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v)
        }


class ScraperMetadata(BaseModel):
    """Metadata about the scraping session."""

    scrape_date: datetime = Field(
        default_factory=datetime.now,
        description="When the scrape was performed"
    )
    total_draws: int = Field(..., description="Total number of draws collected")
    date_range_start: datetime = Field(..., description="Start date of range")
    date_range_end: datetime = Field(..., description="End date of range")
    errors: List[str] = Field(
        default_factory=list,
        description="List of errors encountered"
    )

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ScraperResult(BaseModel):
    """Complete result of a scraping session."""

    metadata: ScraperMetadata
    draws: List[LottoMaxDraw]

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v)
        }
