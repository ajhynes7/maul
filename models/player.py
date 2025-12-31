from pydantic import computed_field
import numpy as np
from sqlmodel import Field, SQLModel


class Player(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    name: str = Field(unique=True, nullable=False)

    salary: float = Field(default=0)
    team: int = Field(nullable=False)

    trade_count: int = Field(default=0)
    traded_last_time: bool = Field(default=False)

    games_attended: int = Field(default=0)
    goals: int = Field(default=0)
    assists: int = Field(default=0)
    second_assists: int = Field(default=0)
    completed_passes: int = Field(default=0)
    d_blocks: int = Field(default=0)

    @computed_field
    def goals_per_game(self) -> float:
        return self.goals / self.games_attended if self.games_attended else np.nan

    @computed_field
    def assists_per_game(self) -> float:
        return self.assists / self.games_attended if self.games_attended else np.nan

    @computed_field
    def second_assists_per_game(self) -> float:
        return (
            self.second_assists / self.games_attended if self.games_attended else np.nan
        )

    @computed_field
    def completed_passes_per_game(self) -> float:
        return (
            self.completed_passes / self.games_attended
            if self.games_attended
            else np.nan
        )

    @computed_field
    def d_blocks_per_game(self) -> float:
        return self.d_blocks / self.games_attended if self.games_attended else np.nan
