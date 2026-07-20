# Structure

```
bt-lab/
├── bt.py                        # 全段の単一CLIエントリーポイント（bt.py --help）
├── bin/
│   ├── bt                         # AI/スクリプト向け非対話実行（シェル非依存）
│   └── bt-python                  # pandas/pyarrow入りpython3の解決
├── zsh/
│   └── bt.sh                      # 人間の対話利用向け（source すると bt/bt-py が使える。tab補完つき）
├── core/                        # S1b〜S8パイプライン本体
│   ├── s1_export_parquet.py       # JSONL → parquet(year=YYYY/MM.parquet)
│   ├── s1_enrich_parquet.py       # 特徴量列を焼き込み
│   ├── s2_gen_strategies.py       # strategies_md → strategies/<kind>/<slug>.py（冪等）
│   ├── s3_calc_positions.py       # 戦略をparquetに適用してエントリー計算
│   ├── s4_ban_build.py            # エントリー率 + Jaccard重複排除 → banリスト
│   ├── s5_position_engine.py      # TP/SL/EOD判定
│   ├── s6_position_pips.py        # pos_eventsにpips_net列を付与
│   ├── s7_position_summary.py     # 月次・四半期・年次サマリー
│   ├── s8_strategy_rank.py        # DDフィルタ + 直近N月ランキング
│   ├── s_monthly_sim.py           # 単月シミュレーション
│   └── s_monthly_backfill.py      # 複数月の月次シムをバックフィル
├── lib/                          # 共有ライブラリ
│   ├── env_paths.py                # BACKTEST_DATA_ROOT等のパス解決。ハードコード禁止の唯一の情報源
│   ├── features.py                 # 素材特徴量計算（RSI/EMA/ATR/Bollinger等の純関数群）
│   ├── feature_registry.py         # feature_registry.yamlのロード
│   ├── grid.py                     # PARAMS_GRIDの直積展開
│   ├── generated_strategy.py       # 生成済み戦略ファイルから呼ばれるapply_kind_strategy
│   ├── session_util.py             # セッション・時間帯まわりのユーティリティ
│   ├── cli_common.py               # 各stageスクリプト共通のCLI引数処理
│   └── yaml_loader.py              # YAML読み込みの薄いラッパ
├── import/
│   └── feature_registry.yaml     # 手書き固定ファイル。自動生成・上書き禁止
├── strategies_md/                # 戦略カタログ（HOWTO.mdの規約に従う）
│   ├── HOWTO.md                    # カタログ全体の管理規約
│   └── oscillator/rsi_zone/        # 教科書的なダミーkind（実カタログは非公開）
│       ├── SPEC.md
│       └── template.py
├── examples/sample/              # 合成データ生成（実データは同梱しない）
│   ├── generate_data.py
│   └── data/sample_m5_2025.jsonl
└── tests/                        # core/・lib/を1対1でミラー配置
```

## データフロー

```
JSONL bars ──s1_export_parquet──▶ parquet(year=YYYY/MM.parquet)
                                        │
                          s1_enrich_parquet（特徴量焼き込み）
                                        │
        strategies_md/<kind>/template.py ──s2_gen_strategies──▶ strategies/<kind>/<slug>.py
                                        │
                          s3_calc_positions（entry_flag/buy_sell/trend_dir）
                                        │
                          s4_ban_build（エントリー率 + 重複排除）
                                        │
                          s5_position_engine（TP/SL/EOD判定）
                                        │
                          s6_position_pips（pips_net付与）
                                        │
                          s7_position_summary（月次/四半期/年次）
                                        │
                          s8_strategy_rank（DDフィルタ + ランキング）
```

`bt.py`が上記を配線する層。各段は`core/<stage>.py`として独立実行可能で、`bt.py <stage>`はサブプロセス起動の薄いラッパ。`strategies_md/`は`core/`・`lib/`から一方向にしか参照されず、逆にパイプライン本体が個々の戦略kindの中身を知ることはない。
