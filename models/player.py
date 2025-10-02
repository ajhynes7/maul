from sqlmodel import SQLModel, Field


class Player(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    name: str = Field(unique=True, nullable=False)

    salary: float = Field(default=0)
    team: int = Field(nullable=False)

    trade_count: int = Field(default=0)
    traded_last_time: bool = Field(default=False)
