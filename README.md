<h1 align="center">Analyst Arena</h1>

<p align="center">
  <strong>A multi-agent prediction league where ground truth is the referee.</strong><br>
  Locked pre-event calls · mandatory reasoning · divergence-only review · evidence-gated shared learning
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Python 3.8+" src="https://img.shields.io/badge/python-3.8+-blue.svg">
  <img alt="Dependencies: none" src="https://img.shields.io/badge/dependencies-none-brightgreen.svg">
  <a href="https://github.com/mayberonger430059-art/Analyst-arena/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/mayberonger430059-art/Analyst-arena?style=social"></a>
</p>

Several AI analysts (different models, different frameworks, or the same model
with different playbooks) independently predict the same events. Every call is
locked in *before* the event, with its reasoning attached. Reality settles the
score. Only the disagreements are reviewed, and lessons enter the shared
knowledge base only after enough evidence accumulates — so the league breeds a
champion instead of averaging opinions into mush.

Single-file Python, standard library only, no dependencies.

## See it in action

A demo round (football preset, two analysts, three matches — data in
[`examples/football/`](examples/football/)):

```text
$ python3 arena.py --config examples/football/arena.json board

===== 2026-10-18 scoreboard =====
[Alpha (market-first)]         ah pushed 1.0/1 (100.0%) | ht pushed 2/2 (100.0%), all 2/3 | no-bet 1
[Bravo (fundamentals-first)]   ah pushed 0.5/2 (25.0%)  | ht pushed 2/2 (100.0%), all 2/3 | no-bet 1

$ python3 arena.py --config examples/football/arena.json diverge 2026-10-18
DIVERGENCE M003 [ah]: Alpha (market-first)=home -0.5 vs Bravo (fundamentals-first)=away +0.5

$ python3 arena.py --config examples/football/arena.json learn-add "…" "…" --n 3 --level L2
Evidence gate: n=3 < 10, stored as L1 (observation only). Lessons graduate
only after enough samples accumulate.
```

## Track record — from the production league

This framework was extracted from a live football-prediction operation
(China Sports Lottery fixtures, analysed daily, every round settled and
reviewed in the open — losing rounds included, nothing deleted).
Cumulative, audited figures as of **2026-10-21**:

| Scope | Record | Hit rate |
|---|---|---|
| Medium-confidence calls (1X2 + Asian handicap) | 78 / 118 | **66.1%** |
| Medium-confidence totals (over/under) | 28 / 42 | **66.7%** |
| BTTS signals (tracked, never pushed) | 49 / 77 | **63.6%** |
| Best single round — pushed calls, 2026-10-18 | 7 / 8 | **87.5%** |
| Asian handicap, all calls (headline metric — the hardest market) | 71 / 135 | 52.6% |

Read the table the way the league reads it: confidence tiers are calibrated,
not decorative — medium-and-above is the push threshold, and the handicap
line is published alongside the flattering numbers on purpose. A league that
only shows its wins is marketing, not a scoreboard.

## Why

Letting LLMs "debate" usually produces consensus theater: the loudest model
wins and nobody can tell afterwards who was actually right. Analyst Arena
replaces debate with a scoreboard:

1. **Independent submissions, locked pre-event.** Each analyst submits JSON
   calls per event and per dimension, with a confidence level — or an explicit
   *no-bet* with a reason code and the call they *would* have made.
2. **Mandatory reasoning.** A call without `reasons` is rejected. Reasons are
   the raw material for attribution after the round: *which signal won?*
3. **Ground truth settles, per analyst.** Outcomes are recorded per analyst
   (two analysts on opposite sides of the same line cannot share one
   outcome); the scoreboard tracks pushed calls (confidence at or above the
   league threshold) separately from all calls.
4. **Divergence-only review.** Rounds are reviewed only where pushed calls
   disagreed. Consensus rounds carry no information. Each review answers three
   questions: who won, on which signal, and which step the loser missed.
5. **Evidence-gated learning.** A lesson graduates into the shared knowledge
   base only after `learning_min_samples` (default 10) supporting samples.
   One lucky round teaches nothing. Shared entries are graded L1
   (observation) / L2 (candidate) / L3 (rule), and demoted after repeated
   failed validation.
6. **Managed convergence.** Sharing makes analysts converge and destroys the
   diversity that makes the league valuable — so only *verified statistical
   facts* (L2/L3) are shared. Each analyst keeps its own weights and priors.

The league is not meant to run forever: it exists to grow a champion. When one
analyst's transferable rules consistently win, promote them into your
production system and retire the arena.

## Quickstart

```bash
git clone https://github.com/mayberonger430059-art/Analyst-arena.git
cd Analyst-arena

python3 arena.py --config examples/football/arena.json init
python3 arena.py --config examples/football/arena.json submit examples/football/demo_alpha.json
python3 arena.py --config examples/football/arena.json submit examples/football/demo_bravo.json
python3 arena.py --config examples/football/arena.json settle examples/football/demo_results.json
python3 arena.py --config examples/football/arena.json board
python3 arena.py --config examples/football/arena.json diverge 2026-10-18
python3 arena.py --config examples/football/arena.json learn-list
```

## Make it yours

Everything league-specific lives in one config file (`arena.json`):

```json
{
  "agents": {"alpha": "Alpha", "bravo": "Bravo"},
  "confidences": ["high", "medium", "low"],
  "push_min_confidence": "medium",
  "dimensions": {
    "winner": {"kind": "hitmiss"},
    "spread": {"kind": "graded"}
  },
  "nobet_codes": ["LOW_CONFIDENCE", "INSUFFICIENT_INFO", "CONFLICTING_SIGNALS", "NO_EDGE", "OTHER"],
  "learning_min_samples": 10,
  "db": "data/arena.db"
}
```

- `hitmiss` dimensions settle with `true`/`false` per analyst.
- `graded` dimensions settle with `win` / `half_win` / `push` / `half_lose` /
  `lose` / `na` (half outcomes earn half a point; pushes are excluded) — for
  handicap lines, price targets, or any graded forecast.
- Run a stock-picking league, an election-forecast league, a model-vs-model
  benchmark: change the config, keep the engine.

Submission and result formats are specified in [docs/schema.md](docs/schema.md).
A ready-to-use prompt for analyst agents (any LLM) is in
[prompts/analyst_prompt.md](prompts/analyst_prompt.md).

## Rules of fair play

- No simulated results passed off as real analysis; demo data is labelled.
- No editing submissions after lock-in; `submitted_at` is always recorded.
- No hindsight: analysis written after seeing the outcome is not a prediction.

## 中文说明

分析师擂台赛：多个 AI 分析师在事件发生前独立提交预测（必须附关键依据，
否则校验不通过），结果出来后由事实逐人结算记分。复盘只拆"分歧场"——大家
都看对的场次没有信息量；每条经验要累计足够样本（默认 n≥10）才能进共享
知识库，防止把运气当规律。共享只收验证过的统计事实，各家保留自己的权重
风格，避免越共享越趋同。目标不是让擂台永远办下去，而是养出一个冠军，把
它的可迁移规则并入你的生产系统。

起源：本框架最初为足球赛事分析而建（配置见 `examples/football/`），现已
通用化，可用于任何"多方预测 + 事实裁决"的场景。

生产环境战绩（体彩足球，每日分析、逐轮结算、全量复盘不删失败轮；截至
2026-10-21 累计）：中信心方向 78/118 = **66.1%**、中信心大小球 28/42 =
66.7%、BTTS 信号 49/77 = 63.6%、最佳单轮推送 7/8 = 87.5%（2026-10-18）；
主指标亚盘全量 71/135 = 52.6%（最难的市场，照实列出）。

## License

MIT
