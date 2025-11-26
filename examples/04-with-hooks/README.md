# Example 04: フックシステム

フックシステムを使ってイベントを観測し、動作を制御するサンプルです。

## 学べること

1. **Hookの実装**
   - イベントを観測する
   - `HookResult` で動作を制御
   - 複数のフックを登録

2. **イベント駆動アーキテクチャ**
   - `session:start`, `session:end`
   - `provider:pre`, `provider:post`
   - `tool:pre`, `tool:post`

3. **HookResult のアクション**
   - `continue`: 処理を続行
   - `deny`: 処理をブロック
   - `inject_context`: コンテキストに情報を注入
   - `ask_user`: ユーザーに承認を求める

## 実行方法

```bash
cd examples/04-with-hooks
python3 app_standalone.py
```

### 🔍 フック実行を可視化（トレース版）

イベントとフックの実行タイミングを詳細に表示：

```bash
python3 app_with_trace.py
```

トレース版では以下が可視化されます：
- イベント発火順序（`session:start`、`turn:start` など）
- 各フックの実行タイミング
- フックの戻り値（`continue` / `deny`）
- セキュリティフックによるブロック処理

詳細は [../TRACE_EXAMPLES.md](../TRACE_EXAMPLES.md) を参照。

## 学習ポイント

### Hook の実装

```python
class LoggingHook:
    async def handle_event(self, event: str, data: dict) -> HookResult:
        print(f"[Hook] {event}: {data.get('message', '')}")
        return HookResult(action="continue")

class TimingHook:
    async def handle_event(self, event: str, data: dict) -> HookResult:
        if event == "session:start":
            self.start_time = time.time()
        elif event == "session:end":
            duration = time.time() - self.start_time
            print(f"[Hook] Session duration: {duration:.2f}s")

        return HookResult(action="continue")
```

### イベント登録

```python
# フックを登録
hooks.register("session:start", logging_hook.handle_event)
hooks.register("session:end", logging_hook.handle_event)
hooks.register("provider:pre", logging_hook.handle_event)
hooks.register("tool:pre", timing_hook.handle_event)
```

### イベント発火

```python
# Orchestrator内でイベントを発火
await hooks.emit("provider:pre", {
    "provider": provider.name,
    "message": "Calling provider..."
})

result = await provider.complete(request)

await hooks.emit("provider:post", {
    "provider": provider.name,
    "message": "Provider call completed"
})
```
