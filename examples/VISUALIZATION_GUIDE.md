# 実行フロー可視化ガイド

実行時のイベントとコンポーネントの発火を視覚的に理解するためのガイドです。

## 📊 可視化の全体像

Amplifier Coreの実行フローは、以下の階層で理解できます：

```
Level 1: セッションライフサイクル
  ├─ AmplifierSession(config)     ← 発火ポイント1
  ├─ await session.initialize()   ← 発火ポイント2
  └─ await session.execute()      ← 発火ポイント3

Level 2: コンポーネント相互作用
  ├─ Session → Orchestrator
  ├─ Orchestrator → Context
  ├─ Orchestrator → Provider
  └─ Orchestrator → Tools

Level 3: イベント駆動システム
  ├─ session:start / session:end
  ├─ turn:start / turn:end
  ├─ provider:pre / provider:post
  └─ tool:pre / tool:post

Level 4: フック処理
  ├─ イベント発火
  ├─ 全フックが順次実行
  ├─ HookResult を収集
  └─ アクション判定（continue/deny/inject/ask）
```

## 🎯 学習パス

### パス1: 基礎から理解する

**ステップ1: 3つの発火ポイント（5分）**
```bash
cd examples/01-minimal
python3 app_with_trace.py
```

学べること：
- ✅ セッション作成時に何が起こるか
- ✅ 初期化時にモジュールがどうマウントされるか
- ✅ 実行時の基本フロー

**ステップ2: ツール実行ループ（10分）**
```bash
cd examples/03-with-tools
python3 app_with_trace.py
```

学べること：
- ✅ Provider → ToolCall → Tool の流れ
- ✅ ツール実行結果がどう次のターンに渡されるか
- ✅ 最終レスポンスまでのループ

**ステップ3: イベントとフック（10分）**
```bash
cd examples/04-with-hooks
python3 app_with_trace.py
```

学べること：
- ✅ イベントがどのタイミングで発火するか
- ✅ 複数のフックが同じイベントを処理する様子
- ✅ deny アクションで処理がブロックされる様子

### パス2: 特定のポイントに集中する

**イベントだけ追跡したい:**
```bash
# Example 04 のトレース版を実行して、🔔 EVENT: で grep
cd examples/04-with-hooks
python3 app_with_trace.py | grep "EVENT:"
```

出力例：
```
│    🔔 EVENT: session:start
│    🔔 EVENT: turn:start
│    🔔 EVENT: provider:pre
│    🔔 EVENT: provider:post
│    🔔 EVENT: tool:pre
│    🔔 EVENT: tool:post
│    🔔 EVENT: turn:end
│    🔔 EVENT: session:end
```

**フックの実行だけ見たい:**
```bash
cd examples/04-with-hooks
python3 app_with_trace.py | grep "HOOK:"
```

出力例：
```
│        🪝 HOOK: LoggingHook → → continue
│        🪝 HOOK: TimingHook → → continue
│        🪝 HOOK: SecurityHook → → continue
│        🪝 HOOK: SecurityHook → 🚫 deny  # ← ブロックされた！
```

**ツール実行だけ見たい:**
```bash
cd examples/03-with-tools
python3 app_with_trace.py | grep -E "(CalculatorTool|result=)"
```

## 📖 トレース記号リファレンス

### 構造記号
```
┌─  開始（トップレベル）
├─  開始（ネスト）
│   継続（インデント）
└─  終了（戻り値）
```

### 情報アイコン
```
ℹ️   情報メッセージ
⚠️   警告
❌  エラー・ブロック
✅  成功・許可
🔔  イベント発火
🪝  フック実行
⏱️   時間計測
📊  メトリクス
```

### フックアクション
```
→  continue: 処理を継続
🚫 deny: 処理をブロック
💉 inject_context: コンテキスト注入
❓ ask_user: ユーザーに確認
```

### ステップ番号
```
[01]  実行順序の番号
[02]  この番号で時系列を追跡できる
```

## 🔍 実際の出力例

### Example 01: 基本フロー

```
════════════════════════════════════════════════════════════
  発火ポイント 1/3: AmplifierSession(config)
════════════════════════════════════════════════════════════

  → Session インスタンス生成
  → Session ID: abc123...

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

### Example 03: ツール実行ループ

```
════════════════════════════════════════════════════════════
  TURN 1
════════════════════════════════════════════════════════════

┌─ [02]   LoopOrchestrator.execute()
│      🔔 EVENT: provider:pre
├─ [03]     SmartEchoProvider.complete()
│        [INFO] Calculation detected → tool call
├─ ✓     → ToolCallBlock (calculator)
│      🔔 EVENT: tool:pre
├─ [04]     CalculatorTool.execute()
│        [INFO] Computed: 15 + 27 = 42
├─ ✓     → result=42
│      🔔 EVENT: tool:post

════════════════════════════════════════════════════════════
  TURN 2
════════════════════════════════════════════════════════════

│      🔔 EVENT: provider:pre
├─ [05]     SmartEchoProvider.complete()
│        [INFO] Tool results found → final response
├─ ✓     → TextBlock (final response)
```

### Example 04: フックシステム

```
│    🔔 EVENT: tool:pre (About to execute: delete_file...)
├─ [15]   HookRegistry.emit() (2 hooks)
│        🪝 HOOK: LoggingHook → → continue
│      ❌ 🚫 BLOCKED: delete_file
│        🪝 HOOK: SecurityHook → 🚫 deny
│      ⚠️  Denied: Tool 'delete_file' is blocked for security
├─ ✓   → processed 2 hooks
│    ❌ Tool delete_file execution BLOCKED
```

## 💡 デバッグのヒント

### 問題: どこで止まっているかわからない

**解決策:** ステップ番号を追跡
```
最後に表示されたステップ番号を確認
例: [15] まで進んで止まった → ステップ15の処理を確認
```

### 問題: イベントの順序がわからない

**解決策:** イベントだけフィルタ
```bash
python3 app_with_trace.py | grep "EVENT:"
```

### 問題: フックがいつ実行されているかわからない

**解決策:** フックだけフィルタ
```bash
python3 app_with_trace.py | grep -E "(EVENT:|HOOK:)"
```

### 問題: ツールが実行されているか不明

**解決策:** ツール関連だけフィルタ
```bash
python3 app_with_trace.py | grep -i "tool"
```

## 🎓 上級テクニック

### トレース出力をファイルに保存

```bash
python3 app_with_trace.py > trace.log 2>&1
less trace.log  # ゆっくり読む
```

### 複数実行を比較

```bash
python3 app_with_trace.py > trace1.log 2>&1
# コードを変更
python3 app_with_trace.py > trace2.log 2>&1
diff trace1.log trace2.log  # 差分を確認
```

### 特定のコンポーネントだけ追跡

`app_with_trace.py` を編集：
```python
# 不要なtracer.enter()をコメントアウト
# tracer.enter("ContextManager", "add_message")  # 非表示に
```

## 📚 次のステップ

1. **実際のamplifier-coreと比較**
   - トレース版で流れを理解
   - `/home/dev/workspace/amplifier-core/amplifier_core/` の実装を読む
   - 同じポイントを探す

2. **自分のコードにトレース追加**
   - `ExecutionTracer` クラスをコピー
   - 重要なポイントに `tracer.enter()` を追加
   - 実行して可視化

3. **ドキュメントを読む**
   - [コードリーディングガイド](/docs/code-reading/)
   - [モジュール実装例](/docs/module-examples/)
   - 実装の詳細を理解

4. **カスタムモジュールを実装**
   - トレース版で理解した流れを元に
   - 独自のProvider/Tool/Hookを実装
   - トレースで動作確認
