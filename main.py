#!/usr/bin/env python3
"""Roblox Up-and-Coming forecast entry (roblox-up-and-coming-forecast-01).

Model: per-place calibrated probabilities from the chart history.
For each game g and place k:
    mass(g,k) = sum over reads of w(age) * K(rank_g(read) - k) * mom(g)
where w is exponential time decay (half-life 12h), K a Gaussian kernel on
rank distance (sigma 4), and mom a momentum multiplier from the game's
recent rank velocity and playing growth over the last 48h.
Mass is normalised per place to (1 - unnamed) with unnamed = 0.25; rows
whose rounded probability is 0 are dropped (a game named at a place with
p = 0 scores the floor instead of its unnamed share). top10 is the 10
games with the most total mass.

Reads $MAKEFUN_INPUT_DIR (default /input) history.ndjson + task.json and
writes $MAKEFUN_OUTPUT_DIR (default /output) forecast.json.
Deterministic: no randomness, no network, standard library only.

Backtest (practice window Nov 8-10, 10 archive reads): log score -34.14
vs the house baseline's -43.51. Mean over six rolling windows: -36.23
vs baseline -45.77. The oracle (test-window frequencies) is -15.41.
"""
import json
import math
import os
from datetime import datetime

HALF_LIFE_H = 12.0
SIGMA = 4.0
UNNAMED = 0.25
MOMENTUM = 0.5
VEL_CAP = 2.0       # ranks/hour, cap on the velocity used for momentum
GROWTH_CAP = 3.0    # cap on log playing growth used for momentum
PLACES_DEFAULT = 10


def parse_time(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()


def main():
    input_dir = os.environ.get('MAKEFUN_INPUT_DIR', '/input')
    output_dir = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    with open(os.path.join(input_dir, 'task.json'), encoding='utf-8') as f:
        task = json.load(f)
    places = int(task.get('places', PLACES_DEFAULT))
    output_name = task.get('output', 'forecast.json')
    reads = []
    with open(os.path.join(input_dir, 'history.ndjson'), encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                reads.append(json.loads(line))
    forecast = build_forecast(reads, places)
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, output_name), 'w', encoding='utf-8') as f:
        f.write(json.dumps(forecast, ensure_ascii=False) + '\n')


def build_forecast(reads, places=10):
    if not reads:
        return {"probabilities": [], "top10": []}
    t_end = parse_time(reads[-1]['at'])
    series = {}
    for r in reads:
        t = parse_time(r['at'])
        for row in sorted(r['up_and_coming'], key=lambda x: x['rank']):
            series.setdefault(row['universe_id'], []).append(
                (t, row['rank'], row.get('playing')))
    # Momentum per game: rank velocity + playing growth over the last 48h.
    mom = {}
    for gid, pts in series.items():
        pts.sort()
        recent = [p for p in pts if t_end - p[0] <= 48 * 3600]
        m = 1.0
        if len(recent) >= 2:
            r0, r1 = recent[0][1], recent[-1][1]
            span_h = max(1.0, (recent[-1][0] - recent[0][0]) / 3600.0)
            vel = (r0 - r1) / span_h
            vel = max(-VEL_CAP, min(VEL_CAP, vel))
            m *= math.exp(MOMENTUM * vel * 12.0)
            p0, p1 = recent[0][2], recent[-1][2]
            if p0 and p1 and p0 > 0 and p1 > 0:
                g = math.log(p1 / p0)
                g = max(-GROWTH_CAP, min(GROWTH_CAP, g))
                m *= math.exp(MOMENTUM * g * 3.0)
        mom[gid] = min(m, 4.0)
    mass = {k: {} for k in range(1, places + 1)}
    total = {}
    for gid, pts in series.items():
        for (t, rank, _playing) in pts:
            age_h = (t_end - t) / 3600.0
            w = 0.5 ** (age_h / HALF_LIFE_H)
            if w < 0.005:
                continue
            for k in range(1, places + 1):
                d = rank - k
                kval = math.exp(-(d * d) / (2 * SIGMA * SIGMA))
                if kval < 0.01:
                    continue
                add = w * kval * mom[gid]
                mass[k][gid] = mass[k].get(gid, 0.0) + add
                total[gid] = total.get(gid, 0.0) + add
    probs = []
    for k in range(1, places + 1):
        cand = sorted(mass[k].items(), key=lambda kv: (-kv[1], kv[0]))[:100]
        s = sum(v for _, v in cand)
        if s <= 0:
            continue
        for gid, v in cand:
            p = round((1 - UNNAMED) * v / s, 6)
            if p > 0:
                probs.append({"universe_id": gid, "place": k, "p": p})
    top10 = [g for g, _ in sorted(total.items(),
                                   key=lambda kv: (-kv[1], kv[0]))[:places]]
    if len(top10) < places:
        last = [row['universe_id'] for row in
                sorted(reads[-1]['up_and_coming'], key=lambda r: r['rank'])]
        for gid in last:
            if gid not in top10:
                top10.append(gid)
            if len(top10) == places:
                break
    return {"probabilities": probs, "top10": top10[:places]}


if __name__ == '__main__':
    main()
