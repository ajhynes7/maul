import gspread
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
