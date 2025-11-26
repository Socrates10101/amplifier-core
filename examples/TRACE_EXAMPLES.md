# トレース版サンプル - 実行フローの可視化

実行時のイベントやコンポーネントの発火を詳細に可視化したバージョンです。

## なぜトレース版が必要か

通常のサンプル（`app_standalone.py`）は動作を確認できますが、**内部で何が起こっているか**は見えません。

トレース版（`app_with_trace.py`）は以下を可視化します：
- ✅ どのコンポーネントがいつ呼ばれているか
- ✅ イベントがどの順序で発火しているか
- ✅ フックがいつ実行されているか
- ✅ ツールがどのタイミングで実行されているか
- ✅ コンポーネント間の呼び出し階層

これにより、Amplifier Coreの内部動作を**実際に動かしながら**理解できます。

## クイックスタート

```bash
# 最も基本的なトレース（3つの発火ポイント）
cd examples/01-minimal
python3 app_with_trace.py

# ツール実行フロー
cd examples/03-with-tools
python3 app_with_trace.py

# フックシステム
cd examples/04-with-hooks
python3 app_with_trace.py
```

## トレース版サンプル一覧

### Example 01: 最小構成（トレース版）

**ファイル:** `examples/01-minimal/app_with_trace.py`

**実行:**
```bash
cd examples/01-minimal
python3 app_with_trace.py
```

**表示される情報:**
- 3つの発火ポイントの明確な区切り
- 各ポイントで何が実行されるか
- コンポーネントの生成順序

**出力例:**
```
════════════════════════════════════════════════════════════
  発火ポイント 1/3: AmplifierSession(config)
════════════════════════════════════════════════════════════

  → Session インスタンス生成
  → Session ID: d21e4cae...

════════════════════════════════════════════════════════════
  発火ポイント 2/3: await session.initialize()
════════════════════════════════════════════════════════════

  → Orchestrator をマウント
  → ContextManager をマウント
  → 初期化完了 ✓

════════════════════════════════════════════════════════════
  発火ポイント 3/3: await session.execute(prompt)
════════════════════════════════════════════════════════════

  → Session.execute() が呼ばれました
  → Orchestrator.execute() が呼ばれました
  → レスポンス生成
  → 実行完了 ✓
```

### Example 03: ツールの追加（トレース版）

**ファイル:** `examples/03-with-tools/app_with_trace.py`

**実行:**
```bash
cd examples/03-with-tools
python3 app_with_trace.py
```

**表示される情報:**
- コンポーネントの呼び出し階層
- イベント発火タイミング
- ツール実行フロー
- ターン単位の処理

**出力例:**
```
┌─ [01] Session.execute() prompt="Calculate 15 + 27"
├─ [02]   LoopOrchestrator.execute()
│      [INFO] Starting execution loop...
│      🔔 EVENT: provider:pre
├─ [03]     SmartEchoProvider.complete()
│        [INFO] Calculation detected → tool call
├─ ✓     → ToolCallBlock (calculator)
│      🔔 EVENT: tool:pre
├─ [04]     CalculatorTool.execute()
│        [INFO] Computed: 15 + 27 = 42
├─ ✓     → result=42
│      🔔 EVENT: tool:post
```

### Example 04: フックシステム（トレース版）

**ファイル:** `examples/04-with-hooks/app_with_trace.py`

**実行:**
```bash
cd examples/04-with-hooks
python3 app_with_trace.py
```

**表示される情報:**
- イベント発火順序
- 各フックの実行タイミング
- フックの戻り値（continue/deny）
- セキュリティフックによるブロック

**出力例:**
```
│    🔔 EVENT: tool:pre (About to execute: delete_file...)
├─ [15]   HookRegistry.emit() (2 hooks)
│        🪝 HOOK: LoggingHook → → continue
│      ❌ 🚫 BLOCKED: delete_file
│        🪝 HOOK: SecurityHook → 🚫 deny
│      ⚠️  Denied: Tool 'delete_file' is blocked
```

## トレース記号の説明

### コンポーネント階層
```
┌─  トップレベルのコンポーネント開始
├─  サブコンポーネント開始
│   インデントレベル
└─  コンポーネント終了（戻り値あり）
```

### 情報タイプ
```
ℹ️   INFO: 情報メッセージ
⚠️   WARN: 警告
❌  ERROR: エラー
✅  SUCCESS: 成功
🔔  EVENT: イベント発火
🪝  HOOK: フック実行
⏱️   TIMING: 時間計測
📊  METRICS: メトリクス
```

### フックアクション
```
→  continue: 処理を継続
🚫 deny: 処理をブロック
💉 inject_context: コンテキスト注入
❓ ask_user: ユーザーに確認
```

## 実行フローの読み方

### 1. ステップ番号
```
┌─ [01] Session.execute()
├─ [02]   Orchestrator.execute()
├─ [03]     Provider.complete()
```
- `[01]`, `[02]` がステップ番号
- 実行順序を追跡できる

### 2. インデント
```
┌─ Component A
├─   Component B (Aから呼ばれた)
│      Component C (Bから呼ばれた)
```
- インデントが呼び出し階層を表す
- 深いほど、ネストが深い

### 3. イベントとフック
```
│    🔔 EVENT: tool:pre
├─     HookRegistry.emit() (2 hooks)
│        🪝 HOOK: SecurityHook → → continue
│        🪝 HOOK: LoggingHook → → continue
```
- イベントが発火
- 登録された全フックが実行される
- 各フックの戻り値が表示される

### 4. ターン境界
```
════════════════════════════════════
  TURN 1
════════════════════════════════════
```
- エージェントループのターン区切り
- 各ターンで何が起こったかわかる

## 学習の進め方

### ステップ1: 基本フロー（Example 03）
1. `app_with_trace.py` を実行
2. Session → Orchestrator → Provider の流れを確認
3. ツール実行がどこで起こるか確認
4. ターンのループ構造を理解

### ステップ2: イベントシステム（Example 04）
1. `app_with_trace.py` を実行
2. どのタイミングでイベントが発火するか確認
3. 複数のフックが同じイベントを処理する様子を観察
4. SecurityHookがdenyを返すとどうなるか確認

### ステップ3: 実際のコードと比較
1. トレース出力を見ながら
2. `app_with_trace.py` のソースコードを読む
3. `tracer.enter()` や `tracer.event()` の位置を確認
4. 実際のAmplifier Coreで同じポイントを探す

## デバッグのヒント

### 特定のコンポーネントだけ追跡したい
`app_with_trace.py` を編集して、不要な `tracer.enter()` をコメントアウト：

```python
# tracer.enter("ContextManager", "add_message")  # コメントアウト
self._messages.append(message)
```

### より詳細なログが欲しい
`tracer.log()` を追加：

```python
async def execute(self, input: dict):
    tracer.log(f"Input details: {input}")  # 詳細ログ追加
    result = self._do_calculation(input)
    tracer.log(f"Result details: {result}")  # 詳細ログ追加
    return result
```

### イベントだけ見たい
ステップ番号とインデントを非表示にするには、`ExecutionTracer` を編集

## 次のステップ

1. **通常版と比較**
   - `app_standalone.py` と `app_with_trace.py` を比較
   - トレースコードの追加方法を理解

2. **実際のコードにトレース追加**
   - 自分のコードに `ExecutionTracer` を追加
   - デバッグやドキュメント作成に活用

3. **カスタマイズ**
   - トレース形式を変更（JSON、タイムスタンプ付きなど）
   - ログファイルに出力
   - 特定のイベントだけフィルタ
