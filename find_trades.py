import os
import argparse

import gspread
import numpy as np
import pandas as pd
import yagmail
from dataclasses import dataclass


@dataclass
class Player:
    name: str
    team: int


def main(floor_coeff: float, cap_coeff: float) -> None:
    df = read_parity_sheet()

    df["Player"] = df["Player"].str.strip()
    df["Salary"] = df["Salary"].str.replace("$", "").str.replace(",", "").astype(float)

    salary_map = {player: salary for player, salary in zip(df["Player"], df["Salary"])}

    email_contents = ["Found trades:\n"]

    while True:
        team_salaries = df.groupby("Team").sum()["Salary"]
        mean_team_salary = team_salaries.mean()

        salary_floor = mean_team_salary * floor_coeff
        salary_cap = mean_team_salary * cap_coeff

        team_numbers = team_salaries.index
        teams_under_floor = team_numbers[team_salaries < salary_floor]
        teams_over_cap = team_numbers[team_salaries > salary_cap]

        if not teams_under_floor.any() and not teams_over_cap.any():
            email_contents.append("\nAll team salaries are between the floor and cap.")
            email_contents.append(
                f"Salary floor: ${salary_floor.round():,.0f}"
            )
            email_contents.append(
                f"Salary cap: ${salary_cap.round():,.0f}"
            )

            email_contents.append("\nTeam salaries: " + ", ".join([f'${x:,.0f}' for x in team_salaries.values]))

            break

        best_player_to_trade_i, best_player_to_trade_j = find_best_trade(
            df, team_salaries, salary_map
        )
        email_contents.append(
            f"- {best_player_to_trade_i.name} (team {best_player_to_trade_i.team}) for "
            f"{best_player_to_trade_j.name} (team {best_player_to_trade_j.team})"
        )

        index_i = df[df["Player"] == best_player_to_trade_i.name].index.item()
        index_j = df[df["Player"] == best_player_to_trade_j.name].index.item()

        team_number_i = df.loc[index_i, "Team"]
        team_number_j = df.loc[index_j, "Team"]

        df.loc[index_i, "Team"] = team_number_j
        df.loc[index_j, "Team"] = team_number_i

    MAUL_EMAIL = os.getenv("MAUL_EMAIL")
    MAUL_PASSWORD = os.getenv("MAUL_PASSWORD")

    print("\n".join(email_contents))

    with yagmail.SMTP(MAUL_EMAIL, MAUL_PASSWORD) as yag:
        yag.send(
            to="andrewjhynes@gmail.com",
            subject="MAUL test",
            contents="\n".join(email_contents),
        )
    
    print("\nSent email successfully.")
    

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
        columns=["Player", "Salary", "Team"],
    )
    df["Team"] = pd.to_numeric(df["Team"]).astype(int)

    return df


def find_best_trade(
    df: pd.DataFrame, team_salaries: pd.Series, salary_map: dict[str, int]
) -> tuple[Player, Player]:
    team_number_i = int(team_salaries.idxmax())
    team_number_j = int(team_salaries.idxmin())

    player_names_i = df[df["Team"] == team_number_i]["Player"]
    player_names_j = df[df["Team"] == team_number_j]["Player"]

    min_team_salary_difference = 1e9
    best_trade = None

    for player_name_i in player_names_i:
        for player_name_j in player_names_j:
            new_players_i = (set(player_names_i.values) - {player_name_i}) | {
                player_name_j
            }
            new_players_j = (set(player_names_j.values) - {player_name_j}) | {
                player_name_i
            }

            new_team_salary_i = get_team_salary(new_players_i, salary_map)
            new_team_salary_j = get_team_salary(new_players_j, salary_map)

            new_team_salary_difference = abs(new_team_salary_i - new_team_salary_j)

            if new_team_salary_difference < min_team_salary_difference:
                min_team_salary_difference = new_team_salary_difference
                best_trade = (
                    Player(name=player_name_i, team=team_number_i),
                    Player(name=player_name_j, team=team_number_j),
                )

    return best_trade


def get_team_salary(team: list[str], salary_map: dict[str, int]) -> int:
    return sum(salary_map[player] for player in team)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--floor-coeff", type=float, default=1 - 0.0035)
    parser.add_argument("--cap-coeff", type=float, default=1 + 0.0035)

    args = parser.parse_args()

    main(args.floor_coeff, args.cap_coeff)
