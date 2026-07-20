# Conventions

- パス解決はすべて`lib/env_paths`経由。`BACKTEST_DATA_ROOT`（既定`~/bt_data/backtest`）を起点に`bt_data/`・`parquet_data/`・`strategies/`・`logs/`を導出する。ハードコード禁止。
- ファイル書き込みはatomic（`.tmp`へ書いてから`os.replace`）を基本とする。中断時に壊れた出力を残さない。
- `import/feature_registry.yaml`は手書き固定ファイル。自動生成・上書きはしない。S1cが焼き込む特徴量とS2の依存チェックの単一情報源。
- `lib/features.py`の特徴量関数は右寄せ（時点tの値はt以前のデータのみ使用）で、列名はインジケータ名+パラメータのスネーク記法（例: `rsi14`, `bb_upper_20_2p0`）。命名規則は各関数のdocstringに明記する。
- 戦略の`template.py`は標準ライブラリ + pandas/numpyのみimportし、外部設定ファイル参照や動的な`PARAMS_GRID`生成は禁止（`strategies_md/HOWTO.md`の制約）。S2が読むのは`template.py`のみで、`SPEC.md`は人間向けドキュメント。
- `apply_entry_flag`は`entry_flag`(bool)/`buy_sell`('BUY'/'SELL'/pd.NA)/`trend_dir`('UP'/'DOWN'/pd.NA)の3カラムを書く契約。BUY/SELL両方向を1関数内で扱い、同一バーで両条件が成立する場合はここで排他化する。
- エントリーは1本ずらしの次バーで判定する設計（先読みバイアスを避けるため）。EOD強制決済もパイプライン側が持つ。
- テストは`tests/test_{module}.py`が`core/{module}.py`・`lib/{module}.py`に1対1対応する。pytest、合成データのみを使い実データ・ネットワーク・特定の実行環境に依存しない。
- 各stageスクリプトは`core/<name>.py`として単独実行可能（`python3 core/s5_position_engine.py --help`）。`bt.py`はこれらをサブプロセスとして束ねるだけで、ロジックを持たない。
