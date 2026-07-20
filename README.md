[🇯🇵 日本語](README.md) | [🇬🇧 English](README.en.md)

# bt-lab

複数戦略候補を横断的に検証し、エントリー率・ドローダウン・Recovery Factorでランキングするバックテスト探索パイプライン。単一の勝ち戦略を探すのではなく、「どの戦略候補が生き残るか」を継続的に選抜する仕組みそのものが本体である。

静的な1戦略のバックテストは、その戦略が今後も効き続けるかを保証しない。本リポは戦略を増やす・減らす・条件を変えるたびに全候補を再ランキングし、複数期間で崩れない候補だけを残す運用を、S1b〜S8の8段パイプラインとして固定した。**戦略候補の実カタログ・実運用パラメータ・成績は公開しない**。それらは`strategies_md/`に置く形式こそ規約として公開するが、中身は利用者が自分の仮説で埋めるものであり、パッケージにもリポにも実装として存在しない（線引きは [Scope](#scope) を参照）。

![demo](examples/sample/demo.gif)

（デモは合成データ×ダミー戦略。`nix-shell -p vhs "python3.withPackages(ps: with ps; [pandas numpy pyarrow pyyaml])" --run 'vhs examples/sample/demo.tape'`で再生成できる）

## Quick Start

```bash
pip install -r requirements.txt

# 合成サンプルデータで一通り回す
python3 examples/sample/generate_data.py
BACKTEST_DATA_ROOT=/tmp/bt-lab-demo python3 bt.py all
```

標準の使い方は実データを自分で用意して回すこと（リポにデータは同梱しない。取得手順は[docs/fetch-data.md](docs/fetch-data.md)）。M5足のOHLC JSONL（`time_utc`/`open`/`high`/`low`/`close`）を`$BACKTEST_DATA_ROOT/bt_data/*_m5_*.jsonl`に置けば`bt.py s1b`から通る。

```bash
export BACKTEST_DATA_ROOT=~/bt_data/backtest   # 既定値。未設定でもこのパス
python3 bt.py s1b                    # JSONL → parquet
python3 bt.py s1c                    # parquetへ特徴量焼き込み
python3 bt.py s2                     # strategies_md → 戦略ファイル生成（冪等）
python3 bt.py s3                     # 戦略をparquetに適用してエントリー計算
python3 bt.py s4                     # エントリー率 + 重複排除でBanフィルタ
python3 bt.py s5 --tp-pips 40 --sl-pips 15   # TP/SL/EOD判定
python3 bt.py s6                     # pips集計
python3 bt.py s7                     # 月次・四半期・年次サマリー
python3 bt.py s8 --rank-months 6 --rf-min 2.5   # ランキング
python3 bt.py all                    # S1b〜S8を通しで実行
python3 bt.py flow                   # 対話形式でフェーズを選んで実行
```

AI/スクリプトからの非対話実行には`bin/bt <stage> [args]`（シェル非依存の実行可能スクリプト）を使う。`bt.py --help`で全stage一覧、`bt.py <stage> --help`で各段の引数を確認できる。

## Architecture

```mermaid
flowchart LR
    A[JSONL bars] -->|s1_export_parquet| B[parquet\nyear/month]
    B -->|s1_enrich_parquet| C[+features\nRSI/EMA/ATR...]
    C -->|s2_gen_strategies| D["strategies/<kind>/*.py\n(strategies_mdから生成)"]
    D -->|s3_calc_positions| E[positions\nentry_flag/buy_sell]
    E -->|s4_ban_build| F["ban list\n(重複排除)"]
    F -->|s5_position_engine| G[pos_events\nTP/SL/EOD判定]
    G -->|s6_position_pips| H[+pips_net]
    H -->|s7_position_summary| I[月次/四半期/年次\nsummary]
    I -->|s8_strategy_rank| J[rank\nDDフィルタ済み順位表]
```

`bt.py`が上記8段(S1b〜S8)を配線する単一エントリーポイント。各段は独立したCLIとしても`core/<stage>.py`から直接実行できる。`strategies_md/`が戦略仕様の唯一の正しいソースで、`s2`がkind単位の`template.py`を読み込み`PARAMS_GRID`を直積展開して個別戦略ファイルを生成する（規約は[strategies_md/HOWTO.md](strategies_md/HOWTO.md)）。

## Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| データ処理 | pandas / numpy / pyarrow | バー単位の指標計算・列指向ストレージ(parquet)によるS1b〜S8の高速な繰り返し実行に必要 |
| CLI | 標準ライブラリ(subprocess dispatch) | 各段を独立プロセスとして呼べる形にし、AI/スクリプトからの非対話実行(`bin/bt`)と人間の対話実行(`bt.py flow`)を同じstage定義から配線する |
| 戦略定義 | 純Python(`template.py`) + Markdown(`SPEC.md`) | 機械可読な実装(直積展開・エントリー判定)と人間可読な思想(仮説・根拠・弱点)を1kindごとに併置し、カタログ全体がドキュメントとして自己完結する |
| 設定 | YAML(`feature_registry.yaml`) | S1cが焼き込む特徴量とS2の依存チェックの単一情報源。手書き固定ファイルとして扱い自動生成しない |
| テスト | pytest | `src`を1対1でミラーする単体テスト構成。合成データのみを使い実データに依存しない |

## Adding Strategies

1 kind = 1ディレクトリ。`strategies_md/oscillator/rsi_zone/`をコピーして中身を差し替えるのが増やし方の標準形。

```
strategies_md/
  <category>/
    <kind>/
      SPEC.md        # 思想・親カテゴリでの位置・パラメータ根拠・弱点
      template.py     # KIND/CATEGORY/DESCRIPTION/PARAMS_GRID + 3関数
```

```bash
python3 bt.py s2   # strategies_md/ 配下の全kindを走査し、strategies/<kind>/<slug>.py を生成
```

命名規則・`template.py`の必須シンボル・`apply_entry_flag`の出力規約（`entry_flag`/`buy_sell`/`trend_dir`の3カラム）・パラメータ設計指針（軸数上限3、値数2〜3）は[strategies_md/HOWTO.md](strategies_md/HOWTO.md)に従う。パイプライン本体(`core/`, `lib/`)は個々のkindの中身を一切知らない設計で、戦略を増やしてもエンジンには手を入れない。

## Design Decisions

判断の全文は [docs/design-decisions.md](docs/design-decisions.md) を参照。

- **単一戦略の最適化でなく複数候補の継続的選抜** — 1戦略をチューニングし続けると、その戦略が効かなくなった局面に気づけない。候補を増やし、生き残ったものだけをランキング上位に残す運用にすることで、劣化の検知自体をパイプラインの仕事にする
- **カタログはSPEC.md(思想)とtemplate.py(実装)を併置する** — 機械可読な実装だけでは「なぜその条件か」が失われ、人間可読な思想だけでは再現できない。両方を1kindに併置し、`strategies_md/`自体が唯一の正しいソースになる
- **エントリー率フィルタ + Jaccard重複排除でBanする** — パラメータの直積展開は似た条件の戦略を大量に生む。素朴に全部ランキングすると相関の高い候補が上位を占有するため、重複を先に間引いてから比較する
- **ランキングはDDフィルタを通した上でRecovery Factor基準にする** — 総pipsだけで選ぶとドローダウンが大きい候補が紛れ込む。生存可能性を先にフィルタしてから収益効率で並べる
- **各段(S1b〜S8)を独立したCLIに分割する** — 1段ずつ再実行・検証できることを優先し、パラメータを変えて特定の段だけやり直す運用に対応する。副作用として途中結果がファイルとして残り、デバッグと再現性の両方に効く
- **パイプライン本体は戦略の中身をimportしない** — `s2`が`template.py`を動的に読み込む一方向依存にすることで、戦略を何個追加してもエンジン側のコードは変わらない
- **実データ・実カタログは同梱しない** — `examples/`は合成データとダミーkindのみ。パイプラインの仕組みを検証するのに実データは要らず、エッジ(戦略の中身)を公開しないという線引きとも一致する

## Scope

**Focus**

- 複数戦略候補を横断探索し、エントリー率・DD・Recovery Factorで継続的に選抜するS1b〜S8のパイプライン一気通貫実装
- 戦略仕様を「思想(SPEC.md)」と「実装(template.py)」に分離するカタログ規約と、そこからの戦略ファイル自動生成
- エントリー率フィルタ・Jaccard重複排除によるBanリスト構築という、候補が増えすぎたときの絞り込み手法

**Out-of-Scope（公開 / 非公開の線）**

パイプライン(S1b〜S8)・カタログ規約(HOWTO.md)は作法であり、エッジではない。エッジは「どの指標条件がどの局面で効くか」という個々の戦略kindの中身。

| | 内容 |
|---|---|
| 出す（問い） | なぜ単一戦略でなく複数候補の継続的選抜か（静的バックテストの陳腐化回避） |
| 出す（手法） | S1b〜S8のパイプライン設計・戦略カタログ規約・Ban(重複排除)・DDフィルタ付きランキング |
| 出さない（答え） | 戦略kindの実カタログ・実運用パラメータ・成績・通貨ペア |

`strategies_md/`には教科書的なダミーkind（`rsi_zone`）を1つだけ置く。実際の戦略カタログは非公開のまま研究環境側で運用する。

## Development

```bash
pip install -r requirements.txt
PYTHONPATH=. pytest -q
```

`examples/sample/`の合成データは`python3 examples/sample/generate_data.py`で再生成できる（シード付き乱数ウォークであり実データではない）。

## License

MIT
