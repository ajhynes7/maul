import os
import numpy as np
import argparse

import pandas as pd
import yagmail

from models.player import Player
from sqlmodel import Session, select, create_engine


def main(relative_difference: float, trade_rules: bool, send_email: bool) -> None:
    engine = create_engine("sqlite:///maul.db")

    with Session(engine) as session:
        statement = select(Player)
        players = session.exec(statement).all()

    df = pd.DataFrame([player.model_dump() for player in players])

    salary_map = {player: salary for player, salary in zip(df["name"], df["salary"])}

    found_trades = False
    email_contents = ["No trades required."]

    prev_team_salary_range = 1e9

    for _ in range(10):
        team_salaries = df.groupby("team").sum()["salary"]
        team_salary_range = team_salaries.max() - team_salaries.min()

        if team_salary_range > prev_team_salary_range:
            raise ValueError(
                "Unable to find trades. Consider increasing the relative difference."
            )

        prev_team_salary_range = team_salary_range

        mean_team_salary = team_salaries.mean()

        salary_floor = mean_team_salary * (1 - relative_difference)
        salary_cap = mean_team_salary * (1 + relative_difference)

        team_numbers = team_salaries.index
        teams_under_floor = team_numbers[team_salaries < salary_floor]
        teams_over_cap = team_numbers[team_salaries > salary_cap]

        if not teams_under_floor.any() and not teams_over_cap.any():
            email_contents.append("\nAll team salaries are between the floor and cap.")

            email_contents.append(f"Salary floor: ${salary_floor.round():,.0f}")
            email_contents.append(f"Salary cap: ${salary_cap.round():,.0f}")

            email_contents.append(
                "\nTeam salaries: "
                + ", ".join([f"${x:,.0f}" for x in team_salaries.values])
            )

            break

        (player_name_i, team_i), (player_name_j, team_j) = find_best_trade(
            df, team_salaries, salary_map, trade_rules
        )
        email_contents.append(
            f"- {player_name_i} (team {team_i}) for {player_name_j} (team {team_j})"
        )
        found_trades = True

        index_i = df[df["name"] == player_name_i].index.item()
        index_j = df[df["name"] == player_name_j].index.item()

        if index_i == index_j:
            raise ValueError("The player indices must be different.")

        team_number_i = df.loc[index_i, "team"]
        team_number_j = df.loc[index_j, "team"]

        if team_number_i == team_number_j:
            raise ValueError("The team numbers must be different.")

        df.loc[index_i, "team"] = team_number_j
        df.loc[index_j, "team"] = team_number_i

        # Avoid trading the same player again.
        df.loc[index_i, "traded_last_time"] = True
        df.loc[index_j, "traded_last_time"] = True

    if found_trades:
        email_contents[0] = "Found trades:\n"

    print("\n".join(email_contents))

    if send_email:
        MAUL_EMAIL = os.getenv("MAUL_EMAIL")
        MAUL_PASSWORD = os.getenv("MAUL_PASSWORD")

        if not MAUL_EMAIL or not MAUL_PASSWORD:
            raise ValueError("Email/password not set.")

        with yagmail.SMTP(MAUL_EMAIL, MAUL_PASSWORD) as yag:
            yag.send(
                to="andrewjhynes@gmail.com",
                subject="MAUL test",
                contents="\n".join(email_contents),
            )

        print("\nSent email successfully.")


def find_best_trade(
    df: pd.DataFrame,
    team_salaries: pd.Series,
    salary_map: dict[str, int],
    trade_rules: bool,
):
    team_number_i = int(team_salaries.idxmax())
    team_number_j = int(team_salaries.idxmin())

    player_indices_i = df[df["team"] == team_number_i]["name"].index
    player_indices_j = df[df["team"] == team_number_j]["name"].index

    min_team_salary_difference = 1e9
    best_trade = None

    for player_index_i in player_indices_i:
        row_i = df.loc[player_index_i]

        if row_i.salary is None:
            print(row_i)

        if trade_rules and (row_i.traded_last_time or row_i.trade_count > 3):
            continue

        for player_index_j in player_indices_j:
            row_j = df.loc[player_index_j]

            if trade_rules and (row_j.traded_last_time or row_i.trade_count > 3):
                continue

            new_player_indices_i = (set(player_indices_i) - {player_index_i}) | {
                player_index_j
            }
            new_player_indices_j = (set(player_indices_j) - {player_index_j}) | {
                player_index_i
            }

            new_player_names_i = df["name"].loc[list(new_player_indices_i)]
            new_player_names_j = df["name"].loc[list(new_player_indices_j)]

            new_team_salary_i = get_team_salary(new_player_names_i, salary_map)
            new_team_salary_j = get_team_salary(new_player_names_j, salary_map)

            new_team_salary_difference = abs(new_team_salary_i - new_team_salary_j)

            if np.isnan(new_team_salary_difference):
                raise ValueError("Encountered a NaN team salary difference.")

            if new_team_salary_difference < min_team_salary_difference:
                min_team_salary_difference = new_team_salary_difference

                best_trade = (
                    (row_i["name"], team_number_i),
                    (row_j["name"], team_number_j),
                )

    return best_trade


def get_team_salary(team: list[str], salary_map: dict[str, int]) -> int:
    return sum(salary_map[player] for player in team)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--rel-diff", type=float, default=0.0035)
    parser.add_argument("--trade-rules", action="store_true")
    parser.add_argument("--send-email", action="store_true")

    args = parser.parse_args()

    main(args.rel_diff, args.trade_rules, args.send_email)
