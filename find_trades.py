import pandas as pd
from dataclasses import dataclass

ALLOWABLE_RELATIVE_DIFFERENCE = 0.0035


@dataclass
class Player:
    name: str
    team: int


def main():
    df = pd.read_csv("data_2.csv")

    df["Player"] = df["Player"].str.strip()
    df["Salary"] = df["Salary"].str.replace("$", "").str.replace(",", "").astype(float)

    salary_map = {player: salary for player, salary in zip(df["Player"], df["Salary"])}

    while True:
        team_salaries = df.groupby("Team").sum()["Salary"]
        mean_team_salary = team_salaries.mean()

        salary_cap = mean_team_salary * (1 + ALLOWABLE_RELATIVE_DIFFERENCE)
        salary_floor = mean_team_salary * (1 - ALLOWABLE_RELATIVE_DIFFERENCE)

        team_numbers = team_salaries.index
        teams_over_cap = team_numbers[team_salaries > salary_cap]
        teams_under_floor = team_numbers[team_salaries < salary_floor]

        if not teams_over_cap.any() and not teams_under_floor.any():
            print()
            print("All team salaries are between the floor and cap.")
            print(f"Salary floor: {salary_floor}, Salary cap: {salary_cap}")

            print()
            print("Final team salaries:")
            print(team_salaries.values)

            break

        best_player_to_trade_i, best_player_to_trade_j = find_best_trade(
            df, team_salaries, salary_map
        )
        print(f"{best_player_to_trade_i}, {best_player_to_trade_j}")

        index_i = df[df["Player"] == best_player_to_trade_i.name].index.item()
        index_j = df[df["Player"] == best_player_to_trade_j.name].index.item()

        team_number_i = df.loc[index_i, "Team"]
        team_number_j = df.loc[index_j, "Team"]

        df.loc[index_i, "Team"] = team_number_j
        df.loc[index_j, "Team"] = team_number_i


def find_best_trade(
    df: pd.DataFrame, team_salaries: pd.Series, salary_map: dict[str, int]
) -> tuple[Player, Player]:
    team_number_i = int(team_salaries.idxmin())
    team_number_j = int(team_salaries.idxmax())

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
    main()
