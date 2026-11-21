# Blind 2-week replay, 2026-11-09 to 2026-11-20 (10 trading days)

Headline variant: **proxy** (pre-registered rule: strict if CME covers >= 80% of needed ZQ prices).

## Data coverage

```
{
 "days": [
  "2026-11-09",
  "2026-11-10",
  "2026-11-11",
  "2026-11-12",
  "2026-11-13",
  "2026-11-16",
  "2026-11-17",
  "2026-11-18",
  "2026-11-19",
  "2026-11-20"
 ],
 "zq_needed": 30,
 "zq_cme": 0,
 "zq_yahoo": 30,
 "cme_vs_yahoo_pairs": 0,
 "cme_vs_yahoo_max_abs_diff": null,
 "effr_source": "nyfed",
 "effr_days": 120,
 "headline_variant": "proxy"
}
```

## Variant: strict

| Date | Meeting | Eligible | Reason / gate | Dir | L gap | L signal | H gap | H signal | Trade |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-09 | 2026-12-09 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-09 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-09 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-10 | 2026-12-09 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-10 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-10 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-11 | 2026-12-09 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-11 | 2027-01-27 | False | C2(b): active leg has no live quote |  |  |  |  |  | None |
| 2026-11-11 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-12 | 2026-12-09 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-12 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-12 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-13 | 2026-12-09 | False | empty book and no earlier price (cannot classify) |  |  |  |  |  | None |
| 2026-11-13 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-13 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-16 | 2026-12-09 | True | ZQ price from yahoo, not CME settlement | L | -0.39 | -1.69 | -1.52 | -2.82 | False |
| 2026-11-16 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-16 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-17 | 2026-12-09 | False | empty book and no earlier price (cannot classify) |  |  |  |  |  | None |
| 2026-11-17 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-17 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-18 | 2026-12-09 | False | empty book and no earlier price (cannot classify) |  |  |  |  |  | None |
| 2026-11-18 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-18 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-19 | 2026-12-09 | True | ZQ price from yahoo, not CME settlement | L | 0.52 | -0.77 | -2.43 | -3.72 | False |
| 2026-11-19 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-19 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-20 | 2026-12-09 | True | ZQ price from yahoo, not CME settlement | H | -2.16 | -3.49 | 0.25 | -1.09 | False |
| 2026-11-20 | 2027-01-27 | False | active leg fails bid > 0, ask < 1, ask > bid |  |  |  |  |  | None |
| 2026-11-20 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |

Positions:

- none

## Variant: proxy

| Date | Meeting | Eligible | Reason / gate | Dir | L gap | L signal | H gap | H signal | Trade |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-09 | 2026-12-09 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-09 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-09 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-10 | 2026-12-09 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-10 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-10 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-11 | 2026-12-09 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-11 | 2027-01-27 | False | C2(b): active leg has no live quote |  |  |  |  |  | None |
| 2026-11-11 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-12 | 2026-12-09 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-12 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-12 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-13 | 2026-12-09 | False | empty book and no earlier price (cannot classify) |  |  |  |  |  | None |
| 2026-11-13 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-13 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-16 | 2026-12-09 | True |  | L | -0.39 | -1.69 | -1.52 | -2.82 | False |
| 2026-11-16 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-16 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-17 | 2026-12-09 | False | empty book and no earlier price (cannot classify) |  |  |  |  |  | None |
| 2026-11-17 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-17 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-18 | 2026-12-09 | False | empty book and no earlier price (cannot classify) |  |  |  |  |  | None |
| 2026-11-18 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-18 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-19 | 2026-12-09 | True |  | L | 0.52 | -0.77 | -2.43 | -3.72 | False |
| 2026-11-19 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-19 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-20 | 2026-12-09 | True |  | H | -2.16 | -3.49 | 0.25 | -1.09 | False |
| 2026-11-20 | 2027-01-27 | False | active leg fails bid > 0, ask < 1, ask > bid |  |  |  |  |  | None |
| 2026-11-20 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |

Positions:

- none

## Variant: fresh60

| Date | Meeting | Eligible | Reason / gate | Dir | L gap | L signal | H gap | H signal | Trade |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-09 | 2026-12-09 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-09 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-09 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-10 | 2026-12-09 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-10 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-10 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-11 | 2026-12-09 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-11 | 2027-01-27 | False | C2(b): active leg has no live quote |  |  |  |  |  | None |
| 2026-11-11 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-12 | 2026-12-09 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-12 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-12 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-13 | 2026-12-09 | False | empty book and no earlier price (cannot classify) |  |  |  |  |  | None |
| 2026-11-13 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-13 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-16 | 2026-12-09 | True | active-leg quote older than 60 min: KXFED-26DEC-T4.25 | L | -0.39 | -1.69 | -1.52 | -2.82 | False |
| 2026-11-16 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-16 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-17 | 2026-12-09 | False | empty book and no earlier price (cannot classify) |  |  |  |  |  | None |
| 2026-11-17 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-17 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-18 | 2026-12-09 | False | empty book and no earlier price (cannot classify) |  |  |  |  |  | None |
| 2026-11-18 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-18 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-19 | 2026-12-09 | True | active-leg quote older than 60 min: KXFED-26DEC-T4.00, KXFED-26DEC-T4.25 | L | 0.52 | -0.77 | -2.43 | -3.72 | False |
| 2026-11-19 | 2027-01-27 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-19 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |
| 2026-11-20 | 2026-12-09 | True | active-leg quote older than 60 min: KXFED-26DEC-T4.00, KXFED-26DEC-T4.25 | H | -2.16 | -3.49 | 0.25 | -1.09 | False |
| 2026-11-20 | 2027-01-27 | False | active leg fails bid > 0, ask < 1, ask > bid |  |  |  |  |  | None |
| 2026-11-20 | 2027-03-17 | False | C4: ladder does not cover both tails |  |  |  |  |  | None |

Positions:

- none

## Active-leg quote age at 15:00 (headline variant, minutes since last candle)

- KXFED-26DEC-T4.00: n=3, median 0
- KXFED-26DEC-T4.25: n=3, median 0
