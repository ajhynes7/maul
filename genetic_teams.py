from random import randint, choices
from itertools import chain
from functools import partial
from collections import defaultdict

import pandas as pd
import numpy as np


def main():
    df = pd.read_csv("data/maul_4x4_2025.csv")

    df['Player'] = df['Player'].str.strip()
    df['Salary'] = df['Salary'].str.replace('$', '').str.replace(',', '').astype(float)

    nan_salary = df["Salary"].quantile(0.25)
    df["Salary"] = df["Salary"].fillna(value=nan_salary)

    players = list(df["Player"])
    salaries = df["Salary"].values

    n_players = len(players)
    n_teams = 6

    player_numbers = list(df.index)
    n_players = len(players)

    cost_func = partial(get_cost, salaries=salaries, n_players=n_players, n_teams=n_teams)
    selection_func = partial(selection_pair, cost_func=cost_func)

    crossover_func = partial(crossover,  n_players=n_players, n_teams=n_teams)
    mutation_func = partial(mutation, probability=0.9)

    min_cost = 1e7
    prev_min_cost = None
    best_genome = None

    n_population = 10
    population = []

    rng = np.random.default_rng()

    for _ in range(n_population):
        genome = rng.integers(0, high=n_teams, size=n_players)
        
        population.append(genome)

    for iteration in range(1000):
        costs = [cost_func(genome) for genome in population]

        for i, cost in enumerate(costs):
            if cost < min_cost:         
                min_cost = cost
                best_genome = population[i]

                print(iteration, min_cost)

        next_generation = []
        
        for _ in range(n_population):
            parent_1, parent_2 = selection_func(population)

            child = crossover_func(parent_1, parent_2)
            mutation_func(child)
            
            next_generation.append(child)
        
        population = next_generation

    team_dict = defaultdict(list)

    for i, team in enumerate(best_genome):
        team_dict[int(team)].append(players[i])


    max_n_players = max(len(v) for v in team_dict.values())

    for k, v in team_dict.items():
        team_dict[k] = v + [''] * (max_n_players - len(v))

    final_df = pd.DataFrame.from_dict(team_dict)

    print(final_df)

def get_genome(groups: list[list[str]]):
    n_items = sum(len(group) for group in groups)
    
    genome = np.zeros(n_items)
    
    for i, group in enumerate(groups):
        for item in group:
            genome[item] = i

    return genome


def get_team_salaries(salaries, genome: list[int], n_teams: int):
    return [salaries[genome == i].sum() for i in range(n_teams)]


def get_cost(genome: list[int], salaries, n_players: int, n_teams: int):
    expected_n_per_team = int(n_players / n_teams)
    
    team_salaries = get_team_salaries(salaries, genome, n_teams)

    cost = max(team_salaries) - min(team_salaries)

    for i in range(n_teams):
        n_per_team = (genome == i).sum()
        
        if n_per_team < expected_n_per_team or n_per_team > expected_n_per_team + 1:
            return cost ** 2

    return cost


def mutation(genome, probability=0.5):
    n = len(genome)

    index_a = randint(0, n - 1)
    index_b = randint(0, n - 1)
    
    if genome[index_a] != genome[index_b]:
        genome[index_a], genome[index_b] = genome[index_b], genome[index_a]


def crossover(parent_1, parent_2, n_players, n_teams):
    n_per_team = int(n_players / n_teams)
    
    n_1 = len(parent_1)
    n_2 = len(parent_2)
    
    if n_1 != n_2:
        raise ValueError("Parent genomes must have the same length.")

    split_index = randint(0, n_1 - 1)
    child = np.concat((parent_1[:split_index], parent_2[split_index:]))
                          
    return child


def tournament(population, cost_func):
    tournament_contenders = choices(population, k=5)
    tournament_contenders = sorted(tournament_contenders, key=lambda x: cost_func(x))
    
    return tournament_contenders[0]

def selection_pair(population, cost_func):
    parent_1 = tournament(population, cost_func)
    parent_2 = tournament(population, cost_func)

    return parent_1, parent_2


if __name__ == "__main__":
    main()
