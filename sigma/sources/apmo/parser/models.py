"""APMO data models."""

from enum import Enum

from pydantic import BaseModel, Field


class Award(str, Enum):
    GOLD = "Gold Medal"
    SILVER = "Silver Medal"
    BRONZE = "Bronze Medal"
    HONOURABLE_MENTION = "Honourable Mention"


class Contestant(BaseModel):
    country_name: str = Field(..., description="Full country name")
    country_code: str = Field(..., description="3-letter country code")
    given_name: str
    family_name: str
    problem_scores: list[int | None] = Field(
        ..., description="Scores for each problem (P1-P5, None if missing)"
    )
    total: int = Field(..., description="Total score")
    award: Award | None = None
    rank: int | None = None
    aliases: list[str] = Field(
        default_factory=list,
        description="Other names this person is known by (e.g. a romanized name)",
    )

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}"


class APMOScoreboard(BaseModel):
    year: int = Field(..., description="Competition year")
    contestants: list[Contestant]

    @property
    def num_problems(self) -> int:
        if self.contestants:
            return len(self.contestants[0].problem_scores)
        return 5  # APMO has 5 problems

    @property
    def countries(self) -> list[str]:
        return sorted(set(c.country_name for c in self.contestants))

    def get_by_award(self, award: Award) -> list[Contestant]:
        return [c for c in self.contestants if c.award == award]

    def get_by_country(self, country_code: str) -> list[Contestant]:
        return [c for c in self.contestants if c.country_code == country_code]
