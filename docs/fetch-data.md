# 実データの取得

`core/s1_export_parquet.py`（`bt.py s1b`）が読むのは、`$BACKTEST_DATA_ROOT/bt_data/`配下の`*_m5_*.jsonl`。1行1バーのJSON Lines形式で、以下のキーを持つ。

```json
{"time_utc": "2025-01-06T00:00:00Z", "open": 150.0, "high": 150.012, "low": 149.948, "close": 149.967}
```

- `time_utc`: ISO8601、UTC
- `open`/`high`/`low`/`close`: 数値

## 取得元の例

M5足のFXデータはAPI key不要で取得できる[dukascopy-node](https://github.com/Leo4815162342/dukascopy-node)が手軽。

```bash
npx dukascopy-node -i eurusd -from 2025-01-01 -to 2025-03-31 -t m5 -f json
```

出力されるJSONの列名(`timestamp`/`open`/`high`/`low`/`close`)は上記スキーマと異なるため、`time_utc`をISO8601文字列に変換した上で`$BACKTEST_DATA_ROOT/bt_data/<pair>_m5_<year>.jsonl`として保存する。変換は数行のスクリプトで足りる規模のため、本リポでは変換ツールを同梱していない。

対象通貨ペア・取得元はデータ取得の都合で決めてよく、パイプライン側(`core/`・`lib/`)は特定のペアに依存しない。
