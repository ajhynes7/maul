import os
import argparse
from dataclasses import dataclass

import pandas as pd
import yagmail

from util import read_parity_sheet


@dataclass
class Player:
    name: str
    team: int


def main(floor_coeff: float, cap_coeff: float, send_email: bool) -> None:
    df = read_parity_sheet()
    salary_map = {player: salary for player, salary in zip(df["name"], df["salary"])}

    found_trades = False
    email_contents = ["No trades required."]

    for _ in range(100):
        team_salaries = df.groupby("team").sum()["salary"]
        mean_team_salary = team_salaries.mean()

        salary_floor = mean_team_salary * floor_coeff
        salary_cap = mean_team_salary * cap_coeff

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

        best_player_to_trade_i, best_player_to_trade_j = find_best_trade(
            df, team_salaries, salary_map
        )
        email_contents.append(
            f"- {best_player_to_trade_i.name} (team {best_player_to_trade_i.team}) for "
            f"{best_player_to_trade_j.name} (team {best_player_to_trade_j.team})"
        )
        found_trades = True

        index_i = df[df["name"] == best_player_to_trade_i.name].index.item()
        index_j = df[df["name"] == best_player_to_trade_j.name].index.item()

        team_number_i = df.loc[index_i, "team"]
        team_number_j = df.loc[index_j, "team"]

        df.loc[index_i, "team"] = team_number_j
        df.loc[index_j, "team"] = team_number_i

    if found_trades:
        email_contents[0] = "Found trades:\n"

    print("\n".join(email_contents))

    if send_email:
        MAUL_EMAIL = os.getenv("MAUL_EMAIL")
        MAUL_PASSWORD = os.getenv("MAUL_PASSWORD")

        if not MAUL_EMAIL or not MAUL_PASSWORD:
            raise AssertionError("Email/password not set.")

        with yagmail.SMTP(MAUL_EMAIL, MAUL_PASSWORD) as yag:
            yag.send(
                to="andrewjhynes@gmail.com",
                subject="MAUL test",
                contents="\n".join(email_contents),
            )

        print("\nSent email successfully.")


def find_best_trade(
    df: pd.DataFrame, team_salaries: pd.Series, salary_map: dict[str, int]
) -> tuple[Player, Player]:
    team_number_i = int(team_salaries.idxmax())
    team_number_j = int(team_salaries.idxmin())

    player_names_i = df[df["team"] == team_number_i]["name"]
    player_names_j = df[df["team"] == team_number_j]["name"]

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

    parser.add_argument("--send-email", type=bool, default=False)

    args = parser.parse_args()

    main(args.floor_coeff, args.cap_coeff, args.send_email)
