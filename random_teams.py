import math
import random
from itertools import chain

import pandas as pd


def main():
    df = pd.read_csv("data/maul_4x4_2025.csv")

    df["Player"] = df["Player"].str.strip()
    df["Salary"] = df["Salary"].str.replace("$", "").str.replace(",", "").astype(float)

    nan_salary = round(df["Salary"].quantile(0.25))
    df["Salary"] = df["Salary"].fillna(value=nan_salary)

    salary_map = {player: salary for player, salary in zip(df["Player"], df["Salary"])}

    players = list(df["Player"])
    groups = get_groups(players, 6)
    assert sum(len(group) for group in groups) == len(df)

    final_teams, min_salary_range = minimize_salary_range(
        players, salary_map, 6, 100_000
    )
    for team in final_teams:
        team = team + [""] * (8 - len(team))

    team_dicts = {
        f"Team {i + 1}": team + [""] * (8 - len(team))
        for i, team in enumerate(final_teams)
    }
    final_df = pd.DataFrame.from_dict(team_dicts)

    print(f"Salary range: ${min_salary_range}")
    print(final_df)


def get_groups(people: list, n_groups: int) -> list[str]:
    n_people = len(people)
    n_per_group = int(n_people / n_groups)

    shuffled_people = random.sample(people, n_people)

    groups = []

    for i in range(n_groups):
        groups.append(shuffled_people[i * n_per_group : i * n_per_group + n_per_group])

    selected_people = list(chain.from_iterable(groups))
    extra_people = set(shuffled_people) - set(selected_people)

    for i, person in enumerate(extra_people):
        groups[i].append(person)

    return groups


def get_team_salary(team: list[str], salary_map: dict[str, int]) -> int:
    return sum(salary_map[player] for player in team)


def minimize_salary_range(
    players: list[str], salary_map: dict[str, int], n_teams: int, n_iterations: int
) -> tuple[list[str], float]:
    min_salary_range = math.inf
    final_teams = []

    for _ in range(n_iterations):
        teams = get_groups(players, n_teams)

        total_salaries = []

        for team in teams:
            total_salaries.append(get_team_salary(team, salary_map))

        salary_range = max(total_salaries) - min(total_salaries)

        if salary_range < min_salary_range:
            min_salary_range = salary_range
            final_teams = teams

    return final_teams, min_salary_range


if __name__ == "__main__":
    main()
