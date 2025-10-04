from sqlmodel import SQLModel, Session, create_engine, text

from util import read_parity_sheet, read_trade_sheet
from models.player import Player


if __name__ == "__main__":
    db_filename = "maul.db"
    engine = create_engine(f"sqlite:///{db_filename}")

    SQLModel.metadata.create_all(engine)

    df = read_parity_sheet()
    trade_counts, traded_last_time = read_trade_sheet()

    with Session(engine) as session:
        session.exec(text("DELETE FROM player;"))

        for row in df.itertuples():
            player = Player(name=row.name, salary=row.salary, team=row.team)

            if trade_count := trade_counts.get(player.name):
                player.trade_count = trade_count

            if player.name in traded_last_time:
                player.traded_last_time = True

            session.add(player)

        session.commit()
