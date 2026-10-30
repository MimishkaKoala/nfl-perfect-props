#!/usr/bin/env python3
"""Refresh NFL Perfect Props from nflverse weekly player statistics.

Historical 100% is across rows in nflverse, NOT independently verified appearances.
"""
import collections
import io
import json
import math
import os
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
YEAR = int(os.environ.get('NFL_SEASON', '2026'))
SOURCE = f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{YEAR}.csv'
SPECS = [
    ('Passing yards', 'passing_yards', 25, 'QB'),
    ('Pass completions', 'completions', 1, 'QB'),
    ('Pass attempts', 'attempts', 1, 'QB'),
    ('Passing TDs', 'passing_tds', 1, 'QB'),
    ('Rushing yards', 'rushing_yards', 5, 'QB RB FB WR TE'),
    ('Rush attempts', 'carries', 1, 'QB RB FB WR TE'),
    ('Receiving yards', 'receiving_yards', 5, 'WR TE RB FB'),
    ('Receptions', 'receptions', 1, 'WR TE RB FB'),
    ('Targets', 'targets', 1, 'WR TE RB FB'),
    ('Rushing + receiving yards', None, 5, 'QB RB FB WR TE'),
    ('Anytime TD (rush/rec/return)', None, 1, 'QB RB FB WR TE'),
    ('Receiving TDs', 'receiving_tds', 1, 'WR TE RB FB'),
    ('Rushing TDs', 'rushing_tds', 1, 'QB RB FB WR TE'),
]


def number(row, key):
    try:
        v = row.get(key, 0)
        return 0.0 if pd.isna(v) else float(v)
    except (TypeError, ValueError):
        return 0.0


def value(row, category, field):
    if category == 'Rushing + receiving yards':
        return number(row, 'rushing_yards') + number(row, 'receiving_yards')
    if category == 'Anytime TD (rush/rec/return)':
        return sum(number(row, c) for c in ('rushing_tds', 'receiving_tds', 'special_teams_tds', 'fumble_recovery_tds'))
    return number(row, field)


def run():
    req = Request(SOURCE, headers={'User-Agent': 'NFL-Perfect-Props-GitHub-Action'})
    with urlopen(req, timeout=90) as response:
        df = pd.read_csv(io.BytesIO(response.read()), low_memory=False)
    required = {'season', 'week', 'season_type', 'player_id', 'player_display_name', 'position', 'team'}
    if not required.issubset(df.columns):
        raise ValueError(f'Source schema changed; missing {sorted(required - set(df.columns))}')
    df = df[(df['season'] == YEAR) & (df['season_type'] == 'REG') & df['week'].between(1, 18)].copy()
    if df.empty:
        raise ValueError('No regular-season records; keeping existing dashboard data')
    # Only publish weeks whose scheduled Monday has passed. The next week starts on Tuesday;
    # the feed may still be incomplete, so retain only weeks with >= 10 distinct game IDs.
    # A low-game week (e.g. unusual cancellations) will wait for manual review.
    if 'game_id' not in df.columns:
        raise ValueError('Missing game_id; cannot establish week completeness')
    complete = sorted(int(w) for w, g in df.groupby('week') if g['game_id'].nunique() >= 10)
    if not complete:
        raise ValueError('No apparently complete weeks; keeping existing data')
    last_week = max(complete)
    df = df[df['week'] <= last_week]
    # Fail closed on duplicate player-week rows rather than silently inflating hit rates.
    if df.duplicated(['player_id', 'week']).any():
        raise ValueError('Duplicate player-week records detected')
    output = []
    for pid, group in df.groupby('player_id', sort=False):
        byweek = {int(row['week']): row for _, row in group.iterrows()}
        sample = next(iter(byweek.values()))
        games = len(byweek)
        pos = str(sample['position'])
        for category, field, step, positions in SPECS:
            if pos not in positions.split():
                continue
            values = [value(r, category, field) for _, r in sorted(byweek.items())]
            minimum = min(values)
            maximum = int(math.floor((minimum + 1e-8) / step) * step)
            if maximum < step:
                continue
            weekly = {f'W{w}': (int(value(byweek[w], category, field)) if w in byweek else 'DNP / no row') for w in range(1, last_week + 1)}
            for threshold in range(step, maximum + 1, step):
                output.append({
                    'Player': str(sample['player_display_name']),
                    'Team': str(sample['team']), 'Position': pos,
                    'Prop': category, 'Threshold': f'{threshold}+',
                    'Games': games, 'Minimum': minimum, **weekly,
                })
    if not output:
        raise ValueError('No qualifying records; keeping existing data')
    output.sort(key=lambda r: (-r['Games'], r['Prop'], -int(r['Threshold'][:-1]), r['Player']))
    target = ROOT / 'data.json'
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(output, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')
    temporary.replace(target)
    print(f'Updated {target}: {len(output)} thresholds, through Week {last_week}, {len(df)} player-weeks')


if __name__ == '__main__':
    run()
