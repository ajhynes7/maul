import argparse
import math
import os

import numpy as np
import pandas as pd
import yagmail
from sqlmodel import Session, create_engine, select

from models.player import Player


def main(
    percentage: float, trade_rules: bool, include_stats: bool, send_email: bool
) -> None:
    engine = create_engine("sqlite:///maul.db")

    with Session(engine) as session:
        statement = select(Player)
        players = session.exec(statement).all()

    df = pd.DataFrame([player.model_dump() for player in players])

    if (df["salary"] <= 0).any():
        raise ValueError("All salaries should be positive.")

    df["goals_per_game"] = df["goals"] / df["games_attended"]
    df["assists_per_game"] = df["assists"] / df["games_attended"]

    found_trades = False

    team_sums = df.groupby("team").sum()
    team_salaries = team_sums["salary"]

    team_numbers = team_salaries.index
    mean_team_salary = team_salaries.mean()

    rel_diff = percentage / 100
    salary_floor = mean_team_salary * (1 - rel_diff)
    salary_cap = mean_team_salary * (1 + rel_diff)

    salary_range = team_salaries.max() - team_salaries.min()
    email_contents = [
        f"Initial team salary range: ${salary_range:,.0f}\n",
        None,
    ]

    min_cost = math.inf

    for _ in range(10):
        team_sums = df.groupby("team").sum()
        team_salaries = team_sums["salary"]

        teams_under_floor = team_numbers[team_salaries < salary_floor]
        teams_over_cap = team_numbers[team_salaries > salary_cap]

        if not teams_under_floor.any() and not teams_over_cap.any():
            email_contents.append("\nAll team salaries are between the floor and cap.")

            break

        best_trade, min_cost = find_best_trade(
            df,
            trade_rules=trade_rules,
            include_stats=include_stats,
            min_cost=min_cost,
        )

        if not best_trade:
            email_contents.append("\nNo better trade could be found.")
            break

        player_index_i, player_index_j = best_trade

        if player_index_i == player_index_j:
            raise ValueError("The player indices must be different.")

        team_number_i = df.at[player_index_i, "team"]
        team_number_j = df.at[player_index_j, "team"]

        player_name_i = df.at[player_index_i, "name"]
        player_name_j = df.at[player_index_j, "name"]

        if team_number_i == team_number_j:
            raise ValueError("The team numbers must be different.")

        # Trade players
        df.at[player_index_i, "team"] = team_number_j
        df.at[player_index_j, "team"] = team_number_i

        # Avoid trading the same player again.
        df.at[player_index_i, "traded_last_time"] = True
        df.at[player_index_j, "traded_last_time"] = True

        team_sums = df.groupby("team").sum()
        team_salaries = team_sums["salary"]

        salary_range = team_salaries.max() - team_salaries.min()
        found_trades = True

        email_contents.append(
            f"- {player_name_i} (team {team_number_i}) for {player_name_j} (team {team_number_j})"
        )
        email_contents.append(f"\t- New team salary range: ${salary_range:,.0f}")

    email_contents[1] = "Found trades:\n" if found_trades else "No trades found.\n"

    email_contents.append(f"\nSalary floor: ${salary_floor.round():,.0f}")
    email_contents.append(f"Salary cap: ${salary_cap.round():,.0f}")

    team_sums = df.groupby("team").sum()
    email_contents.append(
        "\nTeam salaries: " + ", ".join([f"${x:,.0f}" for x in team_sums["salary"]])
    )
    email_contents.append(
        "\nExpected team goals: "
        + ", ".join([f"{x:.0f}" for x in team_sums["goals_per_game"]])
    )
    email_contents.append(
        "Expected team assists: "
        + ", ".join([f"{x:.0f}" for x in team_sums["assists_per_game"]])
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


def find_best_trade(
    df: pd.DataFrame,
    trade_rules: bool = False,
    include_stats: bool = False,
    min_cost: float | None = None,
) -> tuple[tuple | None, float]:
    n_teams = df.team.max()

    min_cost = min_cost or math.inf
    best_trade = ()

    players_by_team = {
        t: df.index[df["team"] == t].values for t in range(1, n_teams + 1)
    }

    salaries = df["salary"].values
    goals = df["goals_per_game"].values
    assists = df["assists_per_game"].values

    traded_last_time = df["traded_last_time"].values
    trade_counts = df["trade_count"].values

    team_sums = df.groupby("team").sum()
    team_salaries = team_sums["salary"].values
    team_goals = team_sums["goals_per_game"].values
    team_assists = team_sums["assists_per_game"].values

    salary_var = df["salary"].var()

    if include_stats:
        goals_var = df["goals_per_game"].var()
        assists_var = df["assists_per_game"].var()

    team_index_i = np.argmax(team_salaries)
    team_index_j = np.argmin(team_salaries)

    player_indices_i = players_by_team[team_index_i + 1]
    player_indices_j = players_by_team[team_index_j + 1]

    for player_index_i in player_indices_i:
        if trade_rules and (
            traded_last_time[player_index_i] or trade_counts[player_index_i] > 3
        ):
            continue

        for player_index_j in player_indices_j:
            if trade_rules and (
                traded_last_time[player_index_j] or trade_counts[player_index_j] > 3
            ):
                continue

            new_team_salaries = team_salaries.copy()

            new_team_salaries[team_index_i] = (
                new_team_salaries[team_index_i]
                - salaries[player_index_i]
                + salaries[player_index_j]
            )
            new_team_salaries[team_index_j] = (
                new_team_salaries[team_index_j]
                - salaries[player_index_j]
                + salaries[player_index_i]
            )

            cost = new_team_salaries.var() / salary_var

            if include_stats:
                new_team_goals = team_goals.copy()
                new_team_assists = team_assists.copy()

                new_team_goals[team_index_i] = (
                    new_team_goals[team_index_i]
                    - goals[player_index_i]
                    + goals[player_index_j]
                )
                new_team_goals[team_index_j] = (
                    new_team_goals[team_index_j]
                    - goals[player_index_j]
                    + goals[player_index_i]
                )

                new_team_assists[team_index_i] = (
                    new_team_assists[team_index_i]
                    - assists[player_index_i]
                    + assists[player_index_j]
                )
                new_team_assists[team_index_j] = (
                    new_team_assists[team_index_j]
                    - assists[player_index_j]
                    + assists[player_index_i]
                )

                cost_goals = new_team_goals.var() / goals_var
                cost_assists = new_team_assists.var() / assists_var

                cost = cost + cost_goals + cost_assists

            if cost < min_cost:
                min_cost = cost

                best_trade = (player_index_i, player_index_j)

    return best_trade, min_cost


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--percentage", type=float, default=0.35)
    parser.add_argument("--trade-rules", action="store_true")
    parser.add_argument("--include-stats", action="store_true")
    parser.add_argument("--send-email", action="store_true")

    args = parser.parse_args()

    main(args.percentage, args.trade_rules, args.include_stats, args.send_email)
