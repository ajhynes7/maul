import os
import math
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

    if (df["salary"] <= 0).any():
        raise ValueError("All salaries should be positive.")

    df["attendance_factor"] = df["games_attended"] / df["games_attended"].max()

    df["goals_per_game"] = df["goals"] / df["games_attended"]
    df["assists_per_game"] = df["assists"] / df["games_attended"]

    df["expected_goals_per_game"] = df["goals_per_game"] * df["attendance_factor"]
    df["expected_assists_per_game"] = df["assists_per_game"] * df["attendance_factor"]

    found_trades = False
    email_contents = ["No trades required."]

    min_cost = math.inf

    for _ in range(10):
        team_sums = df.groupby("team").sum()
        team_salaries = team_sums["salary"]
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

            break

        best_trade, min_cost = find_best_trade(df, trade_rules, min_cost=min_cost)

        try:
            (player_name_i, team_i), (player_name_j, team_j) = best_trade
        except TypeError:
            email_contents.append("\nNo better trade could be found.")
            break

        email_contents.append(
            f"- {player_name_i} (team {team_i}) for {player_name_j} (team {team_j})"
        )
        found_trades = True

        index_i = df[df["name"] == player_name_i].index.item()
        index_j = df[df["name"] == player_name_j].index.item()

        if index_i == index_j:
            raise ValueError("The player indices must be different.")

        team_number_i = df.at[index_i, "team"]
        team_number_j = df.at[index_j, "team"]

        if team_number_i == team_number_j:
            raise ValueError("The team numbers must be different.")

        df.at[index_i, "team"] = team_number_j
        df.at[index_j, "team"] = team_number_i

        # Avoid trading the same player again.
        df.at[index_i, "traded_last_time"] = True
        df.at[index_j, "traded_last_time"] = True

    if found_trades:
        email_contents[0] = "Found trades:\n"

    email_contents.append(
        "\nTeam salaries: " + ", ".join([f"${x:,.0f}" for x in team_salaries])
    )
    email_contents.append(
        "\nExpected team goals: "
        + ", ".join([f"{x:.0f}" for x in team_sums["expected_goals_per_game"]])
    )
    email_contents.append(
        "\nExpected team assists: "
        + ", ".join([f"{x:.0f}" for x in team_sums["expected_assists_per_game"]])
    )

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


def find_best_trade(df: pd.DataFrame, trade_rules: bool, min_cost: float = None):
    n_teams = df.team.max()

    min_cost = min_cost or math.inf
    best_trade = None

    salary_var = df["salary"].var()
    goals_var = df["expected_goals_per_game"].var()
    assists_var = df["expected_assists_per_game"].var()

    for i in range(n_teams - 1):
        team_number_i = i + 1
        player_indices_i = df[df["team"] == team_number_i].index

        for j in range(i + 1, n_teams):
            team_number_j = j + 1
            player_indices_j = df[df["team"] == team_number_j].index

            for player_index_i in player_indices_i:
                row_i = df.loc[player_index_i]

                if trade_rules and (row_i.traded_last_time or row_i.trade_count > 3):
                    continue

                for player_index_j in player_indices_j:
                    row_j = df.loc[player_index_j]

                    if trade_rules and (
                        row_j.traded_last_time or row_j.trade_count > 3
                    ):
                        continue

                    df_copy = df.copy(deep=True)
                    df_copy.at[player_index_i, "team"] = team_number_j
                    df_copy.at[player_index_j, "team"] = team_number_i

                    sums_by_team = df_copy.groupby("team").sum()
                    cost_salary = sums_by_team["salary"].var() / salary_var
                    cost_goals = (
                        sums_by_team["expected_goals_per_game"].var() / goals_var
                    )
                    cost_assists = (
                        sums_by_team["expected_assists_per_game"].var() / assists_var
                    )
                    cost = cost_salary + cost_goals + cost_assists

                    if cost < min_cost:
                        min_cost = cost

                        best_trade = (
                            (row_i["name"], team_number_i),
                            (row_j["name"], team_number_j),
                        )

    return best_trade, min_cost


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--rel-diff", type=float, default=0.0035)
    parser.add_argument("--trade-rules", action="store_true")
    parser.add_argument("--send-email", action="store_true")

    args = parser.parse_args()

    main(args.rel_diff, args.trade_rules, args.send_email)
