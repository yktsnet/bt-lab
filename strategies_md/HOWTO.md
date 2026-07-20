# strategies_md ガイド

戦略カタログの管理規約。本書は配下すべてのファイルが従う。

---

## 1. 位置づけ

`strategies_md/` は backtest パイプラインの **戦略仕様の唯一の正しいソース**。kind 単位で「思想 (SPEC.md)」と「実装 (template.py)」を併置する。`core/s2_gen_strategies.py` は `template.py` を読み込み、`PARAMS_GRID` を直積展開して `$BACKTEST_DATA_ROOT/strategies/<kind>/<slug>.py` を生成する。

---

## 2. ディレクトリ構成

```
strategies_md/
├── HOWTO.md                       ← 本書
└── <category>/
    └── <kind>/
        ├── SPEC.md
        └── template.py
```

---

## 3. ファイル責務

| ファイル | 役割 | 機械可読 |
|---|---|---|
| `HOWTO.md` | カタログ全体の規約 (本書) | × |
| `<kind>/SPEC.md` | 個別kindの思想・位置・根拠・弱点 | × |
| `<kind>/template.py` | 機械可読実装 (PARAMS_GRID + 関数群) | ○ |

`s2_gen_strategies.py` が読むのは `template.py` のみ。

---

## 4. 命名規則

| 対象 | 規則 | 例 |
|---|---|---|
| カテゴリ名 | snake_case 単数形 | `oscillator`, `price_action` |
| kind名 | snake_case | `rsi_zone`, `ma_cross` |
| ディレクトリ名 | = kind名 と完全一致 | `rsi_zone/` |
| ファイル名 | 固定 | `SPEC.md`, `template.py` |
| 戦略.py slug (生成物) | `<key1><val1>_<key2><val2>` (key昇順) | `distance_from_mid20_rsi_period14.py` |
| 戦略ID (生成物) | `<kind>__<slug>` | `rsi_zone__distance_from_mid20_rsi_period14` |

---

## 5. template.py 仕様

`s2_gen_strategies.py` が import する。**純Pythonとして valid**。プレースホルダー文字列置換は使わない。

### 必須シンボル

```python
KIND: str                    # = ディレクトリ名
CATEGORY: str                # 親カテゴリ名
DESCRIPTION: str             # 1行説明
PARAMS_GRID: dict[str, list] # 直積展開元

def required_features(params: dict) -> list[str]: ...
def apply_indicators(df, params: dict): ...
def apply_entry_flag(df, params: dict): ...
```

### apply_entry_flag 出力規約

`core/s3_calc_positions.py`以降との互換維持のため、以下の3カラムを書く。

| カラム | 型 | 意味 |
|---|---|---|
| `entry_flag` | bool | エントリー成立 |
| `buy_sell` | `'BUY'` / `'SELL'` / `pd.NA` | 方向 |
| `trend_dir` | `'UP'` / `'DOWN'` / `pd.NA` | 相場文脈 |

- BUY/SELL両方向を1関数内で扱う
- 同一barで両方向条件が成立する場合は `apply_entry_flag` 内で排他化する
- 関数は破壊的に df に列を書き、df を return する

### 制約

- 標準ライブラリ + `pandas`, `numpy` のみ import
- 外部設定ファイル参照禁止 (yaml読み込み等)
- `PARAMS_GRID` は dict literal で直接記述 (動的生成禁止)
- list の値は静的に解決可能なリテラルのみ

### 雛形

```python
"""
<kind> - <DESCRIPTION>

詳細思想は SPEC.md を参照。
"""
import pandas as pd
import numpy as np

KIND = "rsi_zone"
CATEGORY = "oscillator"
DESCRIPTION = "RSI が中立から離れた領域での反転"

PARAMS_GRID = {
    "rsi_period": [14, 21],
    "distance_from_mid": [20, 25, 30],
}


def required_features(params: dict) -> list[str]:
    return [f"rsi{params['rsi_period']}"]


def apply_indicators(df, params: dict):
    return df


def apply_entry_flag(df, params: dict):
    df["entry_flag"] = False
    df["buy_sell"] = pd.NA
    df["trend_dir"] = pd.NA

    rsi_period = params["rsi_period"]
    distance = params["distance_from_mid"]
    v = df[f"rsi{rsi_period}"]
    upper = 50 + distance
    lower = 50 - distance

    sell = v >= upper
    buy = v <= lower

    df.loc[sell, "entry_flag"] = True
    df.loc[sell, "buy_sell"] = "SELL"
    df.loc[sell, "trend_dir"] = "UP"

    df.loc[buy, "entry_flag"] = True
    df.loc[buy, "buy_sell"] = "BUY"
    df.loc[buy, "trend_dir"] = "DOWN"

    return df
```

（この`rsi_zone`の雛形は`strategies_md/oscillator/rsi_zone/`にそのまま置いてある教科書的なダミー実装）

---

## 6. SPEC.md 仕様

### 必須セクション (この4つのみ)

```markdown
# <kind>

## 思想
このkindが何を捉えようとしているか。背後の市場仮説。

## 親カテゴリでの位置
同じ <category>/ 配下の兄弟kindと比べて何が違うか。重複していないか。
ここでカテゴリ内のMECEを担保する。

## パラメータ根拠
PARAMS_GRID の各軸・各値がなぜその選択か。

## 弱点・留意点
このkindが効かない相場、誤検知パターン、運用上の注意。
```

---

## 7. パラメータ設計指針

- **軸数**: 最大 3
- **各軸の値数**: 2〜3
- **1 kind あたり戦略数**: 4〜6 が目安、上限 8
- **値の決め方**: 等分散 (8/14/21 のような均等3点) より、**意味分散** (標準値・ノイズ低減版・厳格版 のような根拠ベース) を優先
- 値の根拠は SPEC.md `## パラメータ根拠` に必ず書く

軸を増やすより値を絞るほうが共倒れを避けられる。

---

## 8. レビュー観点

- [ ] `template.py` が python として import 可能 (構文エラーなし)
- [ ] 必須シンボル (`KIND, CATEGORY, DESCRIPTION, PARAMS_GRID` + 3関数) が全て存在
- [ ] `KIND` がディレクトリ名と一致
- [ ] `CATEGORY` が親ディレクトリ名と一致
- [ ] `apply_entry_flag` が3カラム (`entry_flag, buy_sell, trend_dir`) を書く
- [ ] BUY/SELL両方向の条件が記述されている (片側固定になっていない)
- [ ] `required_features` の戻り値が `import/feature_registry.yaml` の precompute に存在
- [ ] PARAMS_GRID の各軸の値の根拠が SPEC.md に書かれている
- [ ] SPEC.md に `## 親カテゴリでの位置` があり、兄弟kindとの差別化が記述されている

---

## 9. 用語

| 用語 | 意味 |
|---|---|
| kind | 戦略の種別 (例: rsi_zone) |
| パラメータ | 1 kind 内で振る変数 (例: rsi_period=14) |
| 戦略 | kind × パラメータ1組合せ |
| グリッド | PARAMS_GRID。各軸の値リスト |
| 直積展開 | グリッドからパラメータ組合せ列挙 |
| slug | パラメータ値で構成されるファイル名 |
| 戦略.py | 直積展開後にs2が生成する個別ファイル |
