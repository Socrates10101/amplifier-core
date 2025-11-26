# 06. デバッグとトレーシング

## ログレベルの設定

### 全体のログレベル

```python
import logging

# カーネル全体
logging.getLogger("amplifier_core").setLevel(logging.DEBUG)

# すべてのログ
logging.basicConfig(level=logging.DEBUG)
```

### コンポーネント別のログレベル

```python
# 特定コンポーネントのみ
logging.getLogger("amplifier_core.hooks").setLevel(logging.DEBUG)
logging.getLogger("amplifier_core.loader").setLevel(logging.INFO)
logging.getLogger("amplifier_core.coordinator").setLevel(logging.WARNING)
```

### モジュール別のログレベル

```python
# 特定のモジュール
logging.getLogger("amplifier_module_tool_bash").setLevel(logging.DEBUG)
logging.getLogger("amplifier_module_provider_anthropic").setLevel(logging.INFO)
```

## セッション状態の確認

### デフォルトフィールド

```python
# セッション作成後
print(session.coordinator.hooks._defaults)
# → {'session_id': 'uuid-1234...', 'parent_id': None}
```

### マウント状態

```python
# 初期化後
print(session.coordinator.mount_points)
# {
#   'orchestrator': <OrchestratorInstance>,
#   'providers': {
#     'anthropic': <AnthropicProvider>,
#     'openai': <OpenAIProvider>
#   },
#   'tools': {
#     'bash': <BashTool>,
#     'filesystem': <FilesystemTool>
#   },
#   'context': <ContextManager>,
#   'hooks': <HookRegistry>,
#   'module-source-resolver': None
# }
```

### 特定のマウントポイント

```python
# Orchestratorの確認
orchestrator = session.coordinator.get("orchestrator")
print(type(orchestrator).__name__)

# すべてのProvidersの確認
providers = session.coordinator.get("providers")
for name, provider in providers.items():
    print(f"{name}: {type(provider).__name__}")

# 特定のToolの確認
bash_tool = session.coordinator.get("tools", "bash")
print(bash_tool)
```

## フックハンドラーの確認

### すべてのハンドラー一覧

```python
handlers = session.coordinator.hooks.list_handlers()
print(handlers)
# {
#   'tool:pre': ['approval-hook', 'logging-hook'],
#   'provider:request': ['request-logger'],
#   'session:start': ['metrics-collector'],
#   ...
# }
```

### 特定イベントのハンドラー

```python
tool_pre_handlers = session.coordinator.hooks.list_handlers("tool:pre")
print(tool_pre_handlers)
# {'tool:pre': ['approval-hook', 'logging-hook']}
```

### ハンドラーの詳細情報

```python
# 内部データ構造にアクセス（デバッグ用）
for event, handlers in session.coordinator.hooks._handlers.items():
    print(f"{event}:")
    for handler in handlers:
        print(f"  - {handler.name} (priority={handler.priority})")
```

## コントリビューションチャネルの確認

### 登録されたチャネル

```python
print(session.coordinator.channels.keys())
# dict_keys(['observability.events', 'capabilities', 'metrics'])
```

### 特定チャネルの貢献者

```python
contributors = session.coordinator.channels.get("observability.events", [])
for contrib in contributors:
    print(f"{contrib['name']}: {contrib['callback']}")
```

### 貢献内容の確認

```python
events = await session.coordinator.collect_contributions("observability.events")
print(events)
# [
#   ["filesystem:read", "filesystem:write"],
#   ["bash:execute", "bash:complete"],
# ]
```

## イベントトレーシング

### イベントロギングフックの追加

```python
async def event_tracer(event: str, data: dict) -> HookResult:
    """すべてのイベントをログに記録"""
    print(f"[EVENT] {event}")
    print(f"  Data: {json.dumps(data, indent=2, default=str)}")
    return HookResult(action="continue")

# すべてのイベントに登録
from amplifier_core.events import ALL_EVENTS

for event in ALL_EVENTS:
    session.coordinator.hooks.register(
        event,
        event_tracer,
        priority=999,  # 最後に実行
        name="event-tracer"
    )
```

### 特定イベントのトレース

```python
async def tool_tracer(event: str, data: dict) -> HookResult:
    """ツール関連イベントのみトレース"""
    if event.startswith("tool:"):
        print(f"[TOOL] {event}")
        print(f"  Tool: {data.get('tool')}")
        print(f"  Arguments: {data.get('arguments')}")
    return HookResult(action="continue")

session.coordinator.hooks.register("tool:pre", tool_tracer, priority=999)
session.coordinator.hooks.register("tool:post", tool_tracer, priority=999)
session.coordinator.hooks.register("tool:error", tool_tracer, priority=999)
```

## コンテキストの確認

### メッセージ履歴

```python
context = session.coordinator.get("context")
messages = await context.get_messages()

for i, msg in enumerate(messages):
    print(f"Message {i}:")
    print(f"  Role: {msg['role']}")
    print(f"  Content: {msg['content'][:100]}...")
    if 'metadata' in msg:
        print(f"  Metadata: {msg['metadata']}")
```

### コンパクション状態

```python
should_compact = await context.should_compact()
print(f"Should compact: {should_compact}")
```

## セッション統計

### 基本統計

```python
print(session.status.to_dict())
# {
#   'session_id': 'uuid-1234...',
#   'started_at': '2025-11-26T10:30:00',
#   'status': 'running',
#   'total_messages': 42,
#   'tool_invocations': 15,
#   'tool_successes': 14,
#   'tool_failures': 1,
#   'total_input_tokens': 5000,
#   'total_output_tokens': 3000,
#   'estimated_cost': 0.05
# }
```

### カスタム統計収集

```python
async def stats_hook(event: str, data: dict) -> HookResult:
    """統計を収集"""
    if event == "provider:response":
        usage = data.get("usage", {})
        session.status.total_input_tokens += usage.get("input_tokens", 0)
        session.status.total_output_tokens += usage.get("output_tokens", 0)

    if event == "tool:post":
        session.status.tool_invocations += 1
        if data.get("success"):
            session.status.tool_successes += 1
        else:
            session.status.tool_failures += 1

    return HookResult(action="continue")

session.coordinator.hooks.register("provider:response", stats_hook)
session.coordinator.hooks.register("tool:post", stats_hook)
```

## エラーのデバッグ

### エラーハンドリングフック

```python
async def error_debugger(event: str, data: dict) -> HookResult:
    """エラーイベントを詳細にログ"""
    if event.endswith(":error"):
        print(f"[ERROR] {event}")
        print(f"  Error: {data.get('error')}")
        print(f"  Error Type: {data.get('error_type')}")
        print(f"  Context: {json.dumps(data, indent=2, default=str)}")

        # 最後のエラーを保存
        session.status.last_error = {
            "event": event,
            "error": data.get("error"),
            "error_type": data.get("error_type"),
            "timestamp": datetime.now().isoformat()
        }

    return HookResult(action="continue")

session.coordinator.hooks.register("tool:error", error_debugger)
session.coordinator.hooks.register("provider:error", error_debugger)
```

### スタックトレースの取得

```python
import traceback

async def error_tracer(event: str, data: dict) -> HookResult:
    """エラー時のスタックトレースを記録"""
    if event.endswith(":error"):
        print(f"[ERROR TRACE] {event}")
        print(traceback.format_exc())

    return HookResult(action="continue")
```

## パフォーマンス測定

### イベント実行時間の測定

```python
import time

event_timings = {}

async def timing_hook(event: str, data: dict) -> HookResult:
    """イベント実行時間を測定"""
    start_time = time.time()

    # イベント名をデータに保存して後で参照
    event_key = f"{event}:{time.time()}"

    # 実際の処理は他のフックに任せる
    result = HookResult(action="continue")

    # 終了時間を記録
    duration = time.time() - start_time
    if event not in event_timings:
        event_timings[event] = []
    event_timings[event].append(duration)

    return result

# すべてのイベントに登録
for event in ALL_EVENTS:
    session.coordinator.hooks.register(
        event,
        timing_hook,
        priority=0,  # 最初に実行
        name="timing-hook"
    )

# セッション終了後
for event, timings in event_timings.items():
    avg_time = sum(timings) / len(timings)
    print(f"{event}: avg={avg_time:.3f}s, count={len(timings)}")
```

## デバッグ用設定

### 詳細ログ設定

```python
config = {
    "session": {
        "orchestrator": "loop-basic",
        "context": "context-simple",
        "injection_budget_per_turn": None,  # 無制限（デバッグ用）
        "injection_size_limit": None,       # 無制限（デバッグ用）
    },
    "providers": [...],
    "tools": [...],
    "hooks": [
        {
            "module": "hook-logger",
            "config": {
                "level": "DEBUG",
                "log_all_events": True,
                "log_full_messages": True
            }
        }
    ]
}
```

### テスト用コーディネーター

**コード:** `testing.py`

```python
from amplifier_core.testing import TestCoordinator

# デバッグ機能付きコーディネーター
coordinator = TestCoordinator(session, debug=True)

# すべてのイベントを自動的にログ
coordinator.enable_event_logging()

# ハンドラー呼び出しをトレース
coordinator.enable_handler_tracing()
```

## トラブルシューティング

### モジュールが見つからない

```python
# 利用可能なモジュールを確認
available = await session.loader.discover()
for module in available:
    print(f"{module.id}: {module.type} at {module.mount_point}")

# sys.pathを確認
import sys
print("sys.path:", sys.path)
```

### フックが実行されない

```python
# 登録を確認
handlers = session.coordinator.hooks.list_handlers()
if "tool:pre" not in handlers:
    print("No handlers registered for tool:pre")

# イベント名のタイポをチェック
from amplifier_core.events import ALL_EVENTS
if "tool:pre" not in ALL_EVENTS:
    print("Invalid event name")
```

### コンテキスト注入が反映されない

```python
# 予算設定を確認
budget = session.coordinator.injection_budget_per_turn
limit = session.coordinator.injection_size_limit
current = session.coordinator._current_turn_injections

print(f"Budget: {budget}, Limit: {limit}, Current: {current}")

# ephemeralフラグを確認
# ephemeral=Trueの場合、コンテキストには保存されない
```

## 次のステップ

- [モジュール実装例](../module-examples/)で実際のコードを確認
- 各コンポーネントの詳細ドキュメントを参照
  - [起動フロー](./02-startup-flow.md)
  - [実行フロー](./03-execution-flow.md)
  - [フックシステム](./04-hook-system.md)
