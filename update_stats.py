#!/usr/bin/env python3
"""Refresh NFL Perfect Props using nflverse weekly player statistics.

100% means every recorded player-week row, not every official game appearance.
"""
import io
import json
import math
import os
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

# This file is stored in the repository root, next to data.json.
ROOT = Path(__file__).resolve().parent
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
STAT_COLUMNS = {
    'passing_yards', 'completions', 'attempts', 'passing_tds',
    'rushing_yards', 'carries', 'receiving_yards', 'receptions',
    'targets', 'rushing_tds', 'receiving_tds',
    'special_teams_tds', 'fumble_recovery_tds',
}


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
        return sum(number(row, c) for c in (
            'rushing_tds', 'receiving_tds', 'special_teams_tds',
            'fumble_recovery_tds'))
    return number(row, field)


def run():
    req = Request(SOURCE, headers={'User-Agent': 'NFL-Perfect-Props-GitHub-Action'})
    with urlopen(req, timeout=90) as response:
        df = pd.read_csv(io.BytesIO(response.read()), low_memory=False)

    required = {
        'season', 'week', 'season_type', 'player_id',
        'player_display_name', 'position', 'team', 'game_id',
    } | STAT_COLUMNS
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f'Source schema changed; missing {sorted(missing)}')

    df = df[(df['season'] == YEAR) &
            (df['season_type'] == 'REG') &
            df['week'].between(1, 18)].copy()
    if df.empty:
        raise ValueError('No regular-season records; keeping existing dashboard data')

    # Heuristic only: >=10 distinct games does NOT prove the feed is complete.
    complete = sorted(int(w) for w, g in df.groupby('week')
                      if g['game_id'].nunique() >= 10)
    if not complete:
        raise ValueError('No apparently complete weeks; keeping existing data')

    # Require consecutive completed weeks, rather than skipping an incomplete week.
    last_week = 0
    for week in range(1, 19):
        if week not in complete:
            break
        last_week = week
    if last_week == 0:
        raise ValueError('Week 1 is not complete; keeping existing data')

    target = ROOT / 'data.json'
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding='utf-8'))
            old_last_week = max(
                (int(k[1:]) for row in existing for k in row
                 if k.startswith('W') and k[1:].isdigit()), default=0)
        except (ValueError, TypeError):
            raise ValueError('Existing data.json is unreadable; refusing overwrite')
        if last_week < old_last_week:
            raise ValueError(
                f'Feed only complete through Week {last_week}; '
                f'existing data has Week {old_last_week}; refusing downgrade')

    df = df[df['week'] <= last_week]
    if df.duplicated(['player_id', 'week']).any():
        raise ValueError('Duplicate player-week records detected')

    output = []
    for pid, group in df.groupby('player_id', sort=False):
        byweek = {int(row['week']): row for _, row in group.iterrows()}
        # Use latest recorded team and position for display.
        sample = byweek[max(byweek)]
        games = len(byweek)
        pos = str(sample['position'])
        for category, field, step, positions in SPECS:
            if pos not in positions.split():
                continue
            values = [value(r, category, field)
                      for _, r in sorted(byweek.items())]
            minimum = min(values)
            maximum = int(math.floor((minimum + 1e-8) / step) * step)
            if maximum < step:
                continue
            weekly = {
                f'W{w}': (int(value(byweek[w], category, field))
                          if w in byweek else 'DNP / no row')
                for w in range(1, last_week + 1)
            }
            for threshold in range(step, maximum + 1, step):
                output.append({
                    'Player': str(sample['player_display_name']),
                    'Team': str(sample['team']),
                    'Position': pos,
                    'Prop': category,
                    'Threshold': f'{threshold}+',
                    'Games': games,
                    'Minimum': minimum,
                    **weekly,
                })

    if not output:
        raise ValueError('No qualifying records; keeping existing data')
    output.sort(key=lambda r: (
        -r['Games'], r['Prop'], -int(r['Threshold'][:-1]), r['Player']))
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(
        json.dumps(output, separators=(',', ':'), ensure_ascii=False),
        encoding='utf-8')
    temporary.replace(target)
    print(f'Updated {target}: {len(output)} thresholds, '
          f'through Week {last_week}, {len(df)} player-weeks')
    print('Note: Week completeness is heuristic; official appearances are not verified.')


if __name__ == '__main__':
    run()
