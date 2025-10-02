from sqlmodel import SQLModel, Session, create_engine, text

from util import read_parity_sheet
from models.player import Player


if __name__ == "__main__":
    db_filename = "maul.db"
    engine = create_engine(f"sqlite:///{db_filename}")

    SQLModel.metadata.create_all(engine)

    df = read_parity_sheet()

    with Session(engine) as session:
        session.exec(text("DELETE FROM player;"))

        for row in df.itertuples():
            session.add(Player(name=row.name, salary=row.salary, team=row.team))

        session.commit()
