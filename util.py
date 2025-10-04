import gspread
from collections import Counter
import numpy as np
import pandas as pd


def read_parity_sheet() -> pd.DataFrame:
    client = gspread.service_account()
    sheet = client.open("2024 MAUL Parity League Master Sheet")

    df = pd.DataFrame(sheet.worksheet("Team Composition Copy").get("A2:H13"))

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
    df["salary"] = df["salary"].str.replace("$", "").str.replace(",", "").astype(float)

    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    return df


def read_trade_sheet() -> tuple[dict, set]:
    client = gspread.service_account()
    sheet = client.open("2024 MAUL Parity League Master Sheet")

    df_trades = pd.DataFrame(
        sheet.worksheet("Trade List").get("B3:G100"),
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
