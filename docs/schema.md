# Submission & result formats (schema v1)

## Submission (one JSON file per agent per round)

```json
{
  "date": "2026-10-18",
  "agent": "alpha",
  "matches": [
    {
      "match_id": "M001",
      "title": "Machida Zelvia vs Avispa Fukuoka",
      "kickoff": "2026-10-18 15:00",
      "dims": {
        "ht": {"pick": "home", "conf": "medium",
               "reasons": ["form and market agree", "rotation risk priced in"]},
        "ah": {"pick": null, "conf": null, "nobet_code": "NO_EDGE",
               "orig_pick": "home -0.25", "orig_conf": "low",
               "reasons": ["shallow line, draw risk high"]}
      }
    }
  ]
}
```

### Rules enforced by the validator

- `date`: `YYYY-MM-DD`, the round date.
- `agent`: must be declared in `arena.json`.
- `dims`: one entry per dimension declared in `arena.json`. Each entry is
  either:
  - a **call**: non-empty `pick` + `conf` on the configured confidence scale;
  - or a **no-bet**: `pick: null` + a valid `nobet_code` + `orig_pick` /
    `orig_conf` (what you *would* have called — this is what makes no-bets
    auditable after the round instead of free passes).
- `reasons`: **required for every entry**, a non-empty list of strings naming
  the signals behind the decision. "Feels right" is not a reason; a
  submission with empty reasons is rejected as not submitted.
- `pick` values are league-defined strings. The referee never guesses
  semantics: all agents must use the same vocabulary (agree it in your league
  config / analyst prompt).

A call counts as **pushed** when its confidence is at or above
`push_min_confidence` in the config. Scoreboards report pushed calls
separately from all calls.

## Results (filed by the referee after the events)

```json
{
  "date": "2026-10-18",
  "matches": [
    {"match_id": "M001",
     "agents": {"alpha": {"ht": true, "ah": "win"},
                "bravo": {"ht": true, "ah": "na"}}},
    {"match_id": "M002",
     "agents": {"alpha": {"ht": false, "ah": "na"},
                "bravo": {"ht": true, "ah": "half_win"}}}
  ]
}
```

Outcomes are settled **per agent**: two analysts on opposite sides of the
same line cannot share one outcome, so the referee records, for each agent,
whether *that agent's own call* hit.

- `hitmiss` dimensions: `true` = the agent's pick was right, `false` = wrong.
- `graded` dimensions: `win` / `half_win` / `push` / `half_lose` / `lose` /
  `na` (the agent made no call on that dimension).
