from sqlmodel import Session, SQLModel, create_engine, text

from models.player import Player
from util import SheetReader

if __name__ == "__main__":
    db_filename = "maul.db"
    engine = create_engine(f"sqlite:///{db_filename}")

    SQLModel.metadata.create_all(engine)

    reader = SheetReader()
    df_salaries = reader.read_team_composition_worksheet()
    trade_counts, traded_last_time = reader.read_trades_worksheet()

    df_stats = reader.read_player_database_worksheet()

    df = df_salaries.join(df_stats)

    with Session(engine) as session:
        session.exec(text("DELETE FROM player;"))

        for _, row in df.iterrows():
            player = Player(
                name=row.name,
                salary=row["salary"],
                team=row["team"],
                games_attended=row["Games Attended"],
                goals=row["Goals"],
                assists=row["Assists"],
                second_assists=row["2nd Assists"],
                completed_passes=row["Completed Passes"],
                d_blocks=row["D-Blocks"],
            )

            if trade_count := trade_counts.get(player.name):
                player.trade_count = trade_count

            if player.name in traded_last_time:
                player.traded_last_time = True

            session.add(player)

        session.commit()
