# bt-lab

@context/conventions.md
@context/structure.md

## Identity (One-sentence Definition)

汎用部分 = 複数戦略候補を横断探索しエントリー率・DD・Recovery Factorで継続的に選抜するS1b〜S8のバックテストパイプライン。
固有部分 = 戦略kindの実カタログ・実運用パラメータ・成績（`strategies_md/`は規約のみ公開、中身はダミーkind1つ）。

検証の枠組み・作法を見せるcloneリファレンスであり、答え（戦略の中身）はリポ外に置く。パッケージ配布(PyPI)は行わない — このリポを`pip import`する実利用者が存在しないため。

## Invariants

- `core/`・`lib/`にドメインのエッジ（具体的な戦略ロジック）を置かない。戦略の中身は`strategies_md/`配下のkindにのみ存在する。
- `strategies_md/`には教科書的なダミーkind(`oscillator/rsi_zone`)のみを置く。実カタログ・実運用パラメータ・成績を持ち込まない。
- パイプライン本体(`core/`, `lib/`, `bt.py`)は個々の戦略kindの中身をimportしない（`s2_gen_strategies`が`template.py`を動的に読み込む一方向依存）。
- ファイル書き込みはatomic。パス解決は`lib/env_paths`経由でハードコード禁止。詳細はREADME.md「Scope」に従う。

## Commands

```bash
# 依存インストール
pip install -r requirements.txt

# 合成サンプルデータを生成してパイプラインを一通り実行
python3 examples/sample/generate_data.py
BACKTEST_DATA_ROOT=/tmp/bt-lab-demo python3 bt.py all
```

## Verification

```bash
PYTHONPATH=. pytest -q
```

pandas/pyarrow等が環境にない場合:

```bash
nix-shell -p "python3.withPackages(ps: with ps; [pandas numpy pyarrow pyyaml pytest])" --run "PYTHONPATH=. pytest -q"
```
