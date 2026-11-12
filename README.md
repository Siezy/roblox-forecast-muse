# roblox-forecast-muse

Forecast entry for the make.fun competition
`roblox-up-and-coming-forecast-01` (Roblox Up-and-Coming chart, 72h,
$500 pool).

## How it works

`main.py` (Python 3, standard library only, deterministic, offline) reads
the hourly snapshots of the Roblox Up-and-Coming chart (`history.ndjson`)
and writes `forecast.json`: for each top-10 place, a probability
distribution over universe IDs, plus an ordered top-10 guess.

The model is a **time-decayed rank kernel** with momentum:

- For each game and each place `k`, accumulate mass over every snapshot:
  `weight = 0.5^(age / 12h) * exp(-(rank - k)^2 / (2 * 4^2))`.
  Recent snapshots matter more (12h half-life); a game's mass spreads
  over neighbouring places via the Gaussian kernel (sigma 4).
- A **momentum multiplier** (capped at 4x) rewards games that climbed in
  rank or grew in `playing` over the last 48h. Without momentum the
  model is just a static chart; the momentum is what catches the next
  risers.
- Per place, mass is normalised to `1 - 0.25`, keeping 25% as an
  unnamed share for games not listed. Rows with a rounded probability
  of 0 are dropped (naming a game at p = 0 scores the floor instead of
  its unnamed share).
- `top10` is the 10 games with the most total mass across places.

## Backtest

Scored with the competition's log-score over hourly archive reads
(3 days of archived chart history beyond the kit).

| window | this model | house baseline (static chart) |
|---|---|---:|
| practice Nov 8-10 | -34.14 | -43.51 |
| 6 rolling windows (mean) | -36.23 | -45.77 |

That is about +9 nats per scored hour over the baseline. The oracle
(test-window frequencies) is -15.41, so the model is roughly halfway
between baseline and oracle.

Models tried and rejected: plain static chart (-43.5), pure momentum
exponential smoothing, a diffusion-based smoother that loads the
unnamed share, and a game-age exit rule (games do keep appearing on
the chart past 28 days, so no such rule is applied).

## Usage

```bash
MAKEFUN_INPUT_DIR=/input MAKEFUN_OUTPUT_DIR=/output python3 main.py
```
