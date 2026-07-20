[🇯🇵 日本語](README.md) | [🇬🇧 English](README.en.md)

# bt-lab

A backtest exploration pipeline that evaluates multiple strategy candidates side by side and ranks them by entry rate, drawdown, and Recovery Factor. Rather than searching for a single winning strategy, the point of this repo is the mechanism that keeps selecting "which candidates are still surviving."

A static, single-strategy backtest gives no guarantee that the strategy will keep working. This repo fixes an operating model where every change to the candidate pool re-ranks all candidates through an 8-stage pipeline (S1b–S8), keeping only the ones that hold up across multiple periods. **The actual strategy catalog, real trading parameters, and performance figures are not published.** The format for placing strategies under `strategies_md/` is published as a convention, but the content is meant to be filled in with the user's own hypotheses — it exists as an implementation neither in the package nor in this repo (see [Scope](#scope) for where the line is drawn).

![demo](examples/sample/demo.gif)

(The demo uses synthetic data and a dummy strategy. Regenerate with `nix-shell -p vhs "python3.withPackages(ps: with ps; [pandas numpy pyarrow pyyaml])" --run 'vhs examples/sample/demo.tape'`)

## Quick Start

```bash
pip install -r requirements.txt

# Run the full pipeline against synthetic sample data
python3 examples/sample/generate_data.py
BACKTEST_DATA_ROOT=/tmp/bt-lab-demo python3 bt.py all
```

The normal way to use this is to bring your own real data (no data is bundled with the repo; see [docs/fetch-data.md](docs/fetch-data.md) for how to fetch it). Drop M5 OHLC JSONL (`time_utc`/`open`/`high`/`low`/`close`) at `$BACKTEST_DATA_ROOT/bt_data/*_m5_*.jsonl` and `bt.py s1b` picks it up.

```bash
export BACKTEST_DATA_ROOT=~/bt_data/backtest   # default; same path even if unset
python3 bt.py s1b                    # JSONL → parquet
python3 bt.py s1c                    # bake indicator features into parquet
python3 bt.py s2                     # strategies_md → generate strategy files (idempotent)
python3 bt.py s3                     # apply strategies to parquet, compute entries
python3 bt.py s4                     # ban filter: entry-rate bounds + dedup
python3 bt.py s5 --tp-pips 40 --sl-pips 15   # TP/SL/EOD resolution
python3 bt.py s6                     # aggregate pips
python3 bt.py s7                     # monthly / quarterly / yearly summary
python3 bt.py s8 --rank-months 6 --rf-min 2.5   # ranking
python3 bt.py all                    # run S1b–S8 straight through
python3 bt.py flow                   # interactive phase-by-phase runner
```

For non-interactive use from AI/scripts, use `bin/bt <stage> [args]` (a shell-independent executable). Run `bt.py --help` to list all stages, or `bt.py <stage> --help` for a stage's arguments.

For interactive human use, there's `zsh/bt.sh`. Add `source /path/to/bt-lab/zsh/bt.sh` to your `.zshrc` and you get `bt` (reinterprets a bare call as `bt.py flow`, with tab completion) and `bt-py` (for invoking individual scripts directly).

## Architecture

```mermaid
flowchart TD
    subgraph P1["Data prep (s1b/s1c)"]
        A[JSONL bars] --> B[parquet] --> C[+features]
    end
    subgraph P2["Strategy & entry (s2/s3/s4)"]
        D["strategies/&lt;kind&gt;/*.py"] --> E[positions] --> F["ban list (dedup)"]
    end
    subgraph P3["Position engine (s5)"]
        G[pos_events (TP/SL/EOD resolution)]
    end
    subgraph P4["Aggregate & rank (s6/s7/s8)"]
        H[+pips_net] --> I[monthly/quarterly/yearly summary] --> J[rank (DD-filtered leaderboard)]
    end
    P1 --> P2 --> P3 --> P4
```

Same 4-way split as the phases in `bt.py flow`'s interactive menu (the `PHASES` definition in `bt.py`).

`bt.py` is the single entry point wiring the 8 stages above (S1b–S8). Each stage can also be run directly as an independent CLI via `core/<stage>.py`. `strategies_md/` is the single source of truth for strategy specs: `s2` reads each kind's `template.py` and expands `PARAMS_GRID` into individual strategy files (convention documented in [strategies_md/HOWTO.md](strategies_md/HOWTO.md)).

## Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| Data processing | pandas / numpy / pyarrow | Needed for bar-level indicator math and columnar storage (parquet) to keep S1b–S8 fast on repeated runs |
| CLI | stdlib (subprocess dispatch) | Lets each stage run as an independent process, wiring both non-interactive use from AI/scripts (`bin/bt`) and interactive human use (`bt.py flow`) off the same stage definitions |
| Strategy definitions | Pure Python (`template.py`) + Markdown (`SPEC.md`) | Places a machine-readable implementation (grid expansion, entry logic) next to a human-readable rationale (hypothesis, reasoning, weaknesses) per kind, so the catalog is self-documenting |
| Config | YAML (`feature_registry.yaml`) | Single source of truth for which features S1c bakes in and what S2 checks dependencies against; handwritten and fixed, never auto-generated |
| Tests | pytest | Unit tests mirror `src` 1:1, using only synthetic data with no dependency on real data |

## Adding Strategies

1 kind = 1 directory. The standard way to add one is to copy `strategies_md/oscillator/rsi_zone/` and replace its contents.

```
strategies_md/
  <category>/
    <kind>/
      SPEC.md        # rationale, position among sibling kinds, parameter reasoning, weaknesses
      template.py     # KIND/CATEGORY/DESCRIPTION/PARAMS_GRID + 3 functions
```

```bash
python3 bt.py s2   # scans every kind under strategies_md/ and generates strategies/<kind>/<slug>.py
```

Naming rules, `template.py`'s required symbols, the `apply_entry_flag` output contract (the three columns `entry_flag`/`buy_sell`/`trend_dir`), and parameter design guidelines (max 3 axes, 2–3 values each) all follow [strategies_md/HOWTO.md](strategies_md/HOWTO.md). The pipeline core (`core/`, `lib/`) never knows the content of any individual kind, so adding strategies never requires touching the engine.

## Design Decisions

Full write-ups are in [docs/design-decisions.md](docs/design-decisions.md).

- **Continuous selection among many candidates, not optimizing a single strategy** — Endlessly tuning one strategy makes it hard to notice when it stops working. Growing the candidate pool and keeping only survivors at the top of the ranking turns degradation detection itself into the pipeline's job.
- **Catalog pairs SPEC.md (rationale) with template.py (implementation)** — A machine-readable implementation alone loses "why this condition," while a human-readable rationale alone can't be reproduced. Pairing both per kind makes `strategies_md/` itself the single source of truth.
- **Ban via entry-rate filter + Jaccard dedup** — Expanding `PARAMS_GRID` as a cartesian product produces many near-identical strategies. Naively ranking all of them lets highly correlated candidates dominate the top, so duplicates are thinned out before comparison.
- **Ranking applies a DD filter before Recovery Factor** — Ranking on total pips alone lets high-drawdown candidates slip through. Survivability is filtered first, then candidates are ordered by capital efficiency.
- **Each stage (S1b–S8) is an independent CLI** — Prioritizes being able to re-run and verify one stage at a time, so changing a parameter only requires redoing the affected stage. As a side effect, intermediate results persist as files, helping both debugging and reproducibility.
- **The pipeline core never imports strategy content** — `s2` dynamically loads `template.py` as a one-way dependency, so adding any number of strategies never changes engine-side code.
- **No real data or real catalog is bundled** — `examples/` contains only synthetic data and a dummy kind. Verifying the pipeline mechanism doesn't require real data, which also lines up with the decision not to publish the edge (the content of the strategies).

## Scope

**Focus**

- An end-to-end S1b–S8 pipeline that explores multiple strategy candidates and continuously selects among them by entry rate, DD, and Recovery Factor
- A catalog convention that separates strategy specs into "rationale" (SPEC.md) and "implementation" (template.py), plus generation of strategy files from it
- A narrowing technique for when candidates multiply: entry-rate filtering and Jaccard-based dedup for building a ban list

**Out-of-Scope (where the public/private line is drawn)**

The pipeline (S1b–S8) and the catalog convention (HOWTO.md) are method, not edge. The edge is the content of individual strategy kinds — which indicator conditions work in which market regime.

| | Content |
|---|---|
| Published (the question) | Why continuous selection among many candidates instead of one static strategy (avoiding backtest staleness) |
| Published (the method) | S1b–S8 pipeline design, strategy catalog convention, ban (dedup), DD-filtered ranking |
| Not published (the answer) | The real strategy catalog, real trading parameters, performance, currency pairs |

`strategies_md/` holds exactly one textbook-style dummy kind (`rsi_zone`). The actual strategy catalog stays private and runs in a separate research environment.

## Development

```bash
pip install -r requirements.txt
PYTHONPATH=. pytest -q
```

The synthetic data under `examples/sample/` can be regenerated with `python3 examples/sample/generate_data.py` (a seeded random walk, not real data).

## License

MIT
