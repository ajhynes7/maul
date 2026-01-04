import argparse
import json
import random
from copy import deepcopy
from itertools import chain, combinations
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from skspatial.objects import Point
from sqlmodel import Session, create_engine, select

from models.player import Player

N_TEAMS = 6


def main(registrations_path: str):
    engine = create_engine("sqlite:///maul.db")

    with Session(engine) as session:
        statement = select(Player)
        parity_players = session.exec(statement).all()

    players = get_registered_players(registrations_path, parity_players)

    player_id_map = {player.id: player for player in players}
    player_ids = list(player_id_map.keys())

    min_cost = (np.inf, np.inf)
    best_teams = None
    costs = []

    for _ in range(5):
        teams = get_groups(player_ids, N_TEAMS)
        cost = evaluate_teams(player_id_map, teams)

        for _ in range(1000):
            costs.append(cost)
            teams_with_swap = random_swap(teams)
            cost_with_swap = evaluate_teams(player_id_map, teams_with_swap)

            if cost_with_swap < cost:
                teams = deepcopy(teams_with_swap)
                cost = cost_with_swap

        if cost < min_cost:
            min_cost = cost
            best_teams = deepcopy(teams)

    print(min_cost)
    teams_with_names = [
        [player_id_map[player_id].name for player_id in team] for team in best_teams
    ]
    df_teams = pd.DataFrame(teams_with_names).transpose()

    print(df_teams.to_markdown(index=False))

    plt.plot([cost[1] for cost in costs])
    plt.xlabel("Iterations")
    plt.ylabel("Cost")

    plt.show()


def get_registered_players(
    registrations_path: str, parity_players: list[Player]
) -> list[Player]:
    parity_player_names = [player.name for player in parity_players]

    df = pd.read_csv(registrations_path)

    df["name"] = (
        df["first_name"].str.strip() + " " + df["last_name"].str.strip()
    ).str.strip()

    name_fixes = json.loads(Path("data/name_fixes.json").read_text())
    extra_stats = json.loads(Path("data/extra_stats.json").read_text())

    registered_player_names = df["name"]
    registered_player_names = set(
        registered_player_names.map(lambda x: name_fixes[x] if x in name_fixes else x)
    )
    registered_players = [
        player for player in parity_players if player.name in registered_player_names
    ]
    non_parity_players = set(registered_player_names) - set(parity_player_names)
    print(f"Non-parity players: {non_parity_players - set(extra_stats.keys())}")

    parity_player_ids = [p.id for p in parity_players]
    id_ = max(parity_player_ids) + 1

    for name in non_parity_players:
        player = Player(id=id_, name=name)

        if name in extra_stats:
            player_stats = extra_stats[name]
            player.__dict__.update(player_stats)

        registered_players.append(player)
        id_ += 1

    return registered_players


def evaluate_teams(player_id_map: dict[int, Player], teams: list[list[int]]):
    games_attended_ragged = [
        get_team_stats(player_id_map, team, "games_attended") for team in teams
    ]
    unknowns = [(x == 0).sum() for x in games_attended_ragged]
    unknown_cost = np.ptp(unknowns)

    goals_per_team = mean_stats_per_team(player_id_map, teams, "goals_per_game")
    assists_per_team = mean_stats_per_team(player_id_map, teams, "assists_per_game")
    second_assists_per_team = mean_stats_per_team(
        player_id_map, teams, "second_assists_per_game"
    )
    completed_passes_per_team = mean_stats_per_team(
        player_id_map, teams, "completed_passes_per_game"
    )
    d_blocks_per_team = mean_stats_per_team(player_id_map, teams, "d_blocks_per_game")

    points = [
        Point(
            [
                goals_per_team[i],
                assists_per_team[i],
                second_assists_per_team[i],
                completed_passes_per_team[i],
                d_blocks_per_team[i],
            ]
        )
        for i in range(len(teams))
    ]

    max_distance = max_distance_between_points(points)
    cost = (unknown_cost, max_distance)

    return cost


def mean_stats_per_team(
    player_id_map: dict, teams: list[list[int]], stat: str
) -> np.ndarray:
    stats_per_team = np.array(
        pad_with_nans([get_team_stats(player_id_map, team, stat) for team in teams])
    )

    return np.nanmean(
        scipy.stats.zscore(stats_per_team, axis=None, nan_policy="omit"), axis=1
    )


def max_distance_between_points(points: list[Point]) -> float:
    max_distance = 0

    for point_a, point_b in combinations(points, 2):
        distance = point_a.distance_point(point_b)

        if distance > max_distance:
            max_distance = distance

    return max_distance


def get_team_stats(
    player_id_map: dict[int, Player], team: list[int], stat: str
) -> list[float]:
    team_players = [player_id_map[player_id] for player_id in team]

    return np.array([getattr(player, stat) for player in team_players])


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


def random_swap(groups: list[list]) -> list[list]:
    groups_copy = deepcopy(groups)

    group_a, group_b = random.sample(groups_copy, 2)

    index_a = random.randrange(len(group_a))
    index_b = random.randrange(len(group_b))

    group_a[index_a], group_b[index_b] = group_b[index_b], group_a[index_a]

    return groups_copy


def pad_with_nans(rows: list) -> np.ndarray:
    n_rows = len(rows)
    max_length = max(len(row) for row in rows)

    new_array = np.full((n_rows, max_length), np.nan, dtype=float)

    for i, row in enumerate(rows):
        new_array[i, : len(row)] = row

    return new_array


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path", type=Path, help="The path to the registrations CSV file."
    )

    args = parser.parse_args()

    main(args.path)
