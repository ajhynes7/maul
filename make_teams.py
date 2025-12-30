import argparse
import json
import random
from copy import deepcopy
from itertools import chain, combinations
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from skspatial.objects import Point
from sqlmodel import Session, create_engine, select

from models.player import Player


def main(registrations_path: str):
    df = pd.read_csv(registrations_path)

    df["name"] = (
        df["first_name"].str.strip() + " " + df["last_name"].str.strip()
    ).str.strip()

    engine = create_engine("sqlite:///maul.db")

    with Session(engine) as session:
        statement = select(Player)
        parity_players = session.exec(statement).all()

    parity_player_names = [player.name for player in parity_players]

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

    parity_player_ids = [p.id for p in parity_players]
    id_ = max(parity_player_ids) + 1

    for name in non_parity_players:
        player = Player(name=name)
        player.id = id_

        player.games_attended = np.nan
        player.goals = np.nan
        player.assists = np.nan
        player.second_assists = np.nan
        player.d_blocks = np.nan

        if name in extra_stats:
            player_stats = extra_stats[name]

            player.__dict__.update(player_stats)

        registered_players.append(player)

        id_ += 1

    players = registered_players
    player_id_map = {player.id: player for player in players}
    player_ids = list(player_id_map.keys())

    min_cost = (np.inf, np.inf)
    best_teams = None

    min_costs = []

    n_teams = 6
    teams = get_groups(player_ids, n_teams)

    for _ in range(1000):
        random_swap(teams)

        games_attended_ragged = [
            get_team_stats(player_id_map, team, "games_attended") for team in teams
        ]
        unknowns = [np.isnan(x).sum() for x in games_attended_ragged]
        unknown_cost = np.ptp(unknowns)

        games_attended = np.array(pad_with_nans(games_attended_ragged))

        goals = np.array(
            pad_with_nans(
                [get_team_stats(player_id_map, team, "goals") for team in teams]
            )
        )
        assists = np.array(
            pad_with_nans(
                [get_team_stats(player_id_map, team, "assists") for team in teams]
            )
        )
        second_assists = np.array(
            pad_with_nans(
                [
                    get_team_stats(player_id_map, team, "second_assists")
                    for team in teams
                ]
            )
        )
        d_blocks = np.array(
            pad_with_nans(
                [get_team_stats(player_id_map, team, "d_blocks") for team in teams]
            )
        )

        goals_per_game = goals / games_attended
        assists_per_game = assists / games_attended
        second_assists_per_game = second_assists / games_attended
        d_blocks_per_game = d_blocks / games_attended

        mean_goals_per_game = np.nanmean(goals_per_game, axis=1)
        mean_assists_per_game = np.nanmean(assists_per_game, axis=1)
        mean_second_assists_per_game = np.nanmean(second_assists_per_game, axis=1)
        mean_d_blocks_per_game = np.nanmean(d_blocks_per_game, axis=1)

        points = [
            Point(
                [
                    mean_goals_per_game[i],
                    mean_assists_per_game[i],
                    mean_second_assists_per_game[i],
                    mean_d_blocks_per_game[i],
                ]
            )
            for i in range(n_teams)
        ]

        min_costs.append(min_cost)

        max_distance = max_distance_between_points(points)
        cost = (unknown_cost, max_distance)

        if cost < min_cost:
            min_cost = cost
            best_teams = deepcopy(teams)

    teams_with_names = [
        [player_id_map[player_id].name for player_id in team] for team in best_teams
    ]
    df_teams = pd.DataFrame(teams_with_names).transpose()

    print(df_teams.to_markdown(index=False))

    plt.plot([x[1] for x in min_costs])
    plt.xlabel("Iterations")
    plt.ylabel("Cost")

    plt.show()


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


def random_swap(groups: list[list]) -> None:
    group_a, group_b = random.sample(groups, 2)

    index_a = random.randrange(len(group_a))
    index_b = random.randrange(len(group_b))

    group_a[index_a], group_b[index_b] = group_b[index_b], group_a[index_a]


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
