import gspread
from collections import Counter
import numpy as np
import pandas as pd


class SheetReader:
    def __init__(self):
        client = gspread.service_account()
        self.sheet = client.open("2025 MAUL Parity League Master Sheet")

    def read_player_worksheet(self) -> pd.DataFrame:
        df = pd.DataFrame(
            self.sheet.worksheet("Team Composition").get("A2:H13", maintain_size=True)
        )

        arr = df.values
        n_members = len(arr)

        df = pd.DataFrame(
            np.vstack(
                [
                    np.hstack([arr[:, 0:2], np.ones((n_members, 1)) * 1]),
                    np.hstack([arr[:, 2:4], np.ones((n_members, 1)) * 2]),
                    np.hstack([arr[:, 4:6], np.ones((n_members, 1)) * 3]),
                    np.hstack([arr[:, 6:8], np.ones((n_members, 1)) * 4]),
                ]
            ),
            columns=["name", "salary", "team"],
        )

        df["team"] = pd.to_numeric(df["team"]).astype(int)
        df["salary"] = (
            df["salary"].str.replace("$", "").str.replace(",", "").astype(float)
        )

        df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

        return df

    def read_trade_worksheet(self) -> tuple[dict, set]:
        try:
            df_trades = pd.DataFrame(
                self.sheet.worksheet("Trade List").get("B3:F100"),
                columns=["week", "team_1", "player_1", "team_2", "player_2"],
            )

            traded_player_names = []

            for row in df_trades.itertuples():
                if row.player_1:
                    traded_player_names.append(row.player_1)
                    traded_player_names.append(row.player_2)

            previously_traded = set()

            last_week = df_trades["week"].max()

            for row in df_trades[df_trades["week"] == last_week].itertuples():
                previously_traded.add(row.player_1)
                previously_traded.add(row.player_2)

            trade_counts = Counter(traded_player_names)

            return trade_counts, previously_traded

        except ValueError:
            return dict(), set()
