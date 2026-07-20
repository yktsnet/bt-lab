# VHS demo: bt-lab
# 生成: リポルートで `nix-shell -p vhs "python3.withPackages(ps: with ps; [pandas numpy pyarrow pyyaml])" --run 'vhs examples/sample/demo.tape'`
# 示したいこと: template.pyのPARAMS_GRID(直積展開元)から、s2が戦略ファイルを機械的に生成する
# 尺規範: 10秒前後

Output examples/sample/demo.gif

Set FontSize 18
Set Width 1000
Set Height 600
Set Theme "Catppuccin Mocha"
Set TypingSpeed 20ms

Hide
Type "export BACKTEST_DATA_ROOT=/tmp/bt-lab-demo"
Enter
Type "rm -rf /tmp/bt-lab-demo"
Enter
Type "clear"
Enter
Show

Type "# PARAMS_GRIDの直積展開から戦略ファイルが生成される"
Enter
Sleep 500ms

Type "cat strategies_md/oscillator/rsi_zone/template.py | grep -A3 PARAMS_GRID"
Enter
Sleep 2500ms

Type "ls $BACKTEST_DATA_ROOT/strategies/rsi_zone/"
Enter
Sleep 1500ms

Type@12ms "python3 bt.py s2"
Enter
Sleep 2000ms

Type "ls $BACKTEST_DATA_ROOT/strategies/rsi_zone/"
Enter
Sleep 3000ms
