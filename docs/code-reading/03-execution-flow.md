# 03. 実行フロー - プロンプト実行の流れ

## フロー全体図

```
session.execute("ユーザーの質問")
    ↓
必須モジュールの取得
    ↓
orchestrator.execute()
    ↓
├─→ hooks.emit(PROMPT_SUBMIT)
│   └─→ フックハンドラー実行
├─→ context.get_messages()
├─→ context.should_compact() / compact()
├─→ hooks.emit(PROVIDER_REQUEST)
├─→ provider.complete(ChatRequest)
│   └─→ (ストリーミング時)
│       ├─→ hooks.emit(CONTENT_BLOCK_START)
│       ├─→ hooks.emit(CONTENT_BLOCK_DELTA) × N
│       └─→ hooks.emit(CONTENT_BLOCK_END)
├─→ hooks.emit(PROVIDER_RESPONSE)
├─→ provider.parse_tool_calls(response)
├─→ FOR EACH tool_call:
│   ├─→ hooks.emit(TOOL_PRE)
│   ├─→ coordinator.process_hook_result()
│   │   ├─→ inject_context → context.add_message()
│   │   ├─→ ask_user → approval_system.request_approval()
│   │   └─→ user_message → display_system.show_message()
│   ├─→ tool.execute(arguments)
│   ├─→ hooks.emit(TOOL_POST)
│   └─→ context.add_message(tool_result)
└─→ hooks.emit(PROMPT_COMPLETE)
    ↓
レスポンス返却
```

## ステップ1: execute()の呼び出し

**コード:** `session.py:224-276`

```python
result = await session.execute("ユーザーの質問")
```

### 1-1. 初期化チェック (`session.py:234-235`)

```python
if not self._initialized:
    await self.initialize()
```

### 1-2. 必須モジュールの取得 (`session.py:237-255`)

```python
orchestrator = self.coordinator.get("orchestrator")
if not orchestrator:
    raise RuntimeError("No orchestrator module mounted")

context = self.coordinator.get("context")
if not context:
    raise RuntimeError("No context manager mounted")

providers = self.coordinator.get("providers")
if not providers:
    raise RuntimeError("No providers mounted")

tools = self.coordinator.get("tools") or {}
hooks = self.coordinator.get("hooks")
```

**取得されるもの:**
- `orchestrator`: 単一のOrchestratorインスタンス
- `context`: 単一のContextManagerインスタンス
- `providers`: `dict[str, Provider]` - 名前でマッピング
- `tools`: `dict[str, Tool]` - 名前でマッピング
- `hooks`: HookRegistryインスタンス

### 1-3. Orchestratorへの委譲 (`session.py:260-267`)

```python
result = await orchestrator.execute(
    prompt=prompt,
    context=context,
    providers=providers,
    tools=tools,
    hooks=hooks,
    coordinator=self.coordinator,  # フック結果処理のため
)
```

## ステップ2: Orchestrator内部の動作

以下は典型的なループオーケストレーター（loop-basicなど）の動作例です。

実際の実装は [Orchestrator実装例](../module-examples/orchestrator-example.md) を参照してください。

### 2-1. プロンプト受信イベント

```python
from amplifier_core.events import PROMPT_SUBMIT

await hooks.emit(PROMPT_SUBMIT, {
    "prompt": prompt,
    "timestamp": datetime.now().isoformat()
})
```

**フックの発火** (`hooks.py:111-186`):

1. **デフォルトフィールドのマージ** (`hooks.py:137-138`)
   ```python
   defaults = {"session_id": "uuid-1234...", "parent_id": None}
   current_data = {**defaults, **data}
   # 結果: {"session_id": "...", "parent_id": None, "prompt": "...", "timestamp": "..."}
   ```

2. **優先順位順にハンドラー実行** (`hooks.py:145-175`)
   ```python
   for hook_handler in sorted_handlers:
       result = await hook_handler.handler(event, current_data)

       if result.action == "deny":
           return result  # 短絡評価

       if result.action == "modify":
           current_data = result.data  # 次のハンドラーに渡す

       if result.action == "inject_context":
           inject_context_results.append(result)
   ```

### 2-2. コンテキスト準備

```python
# 会話履歴の取得
messages = await context.get_messages()

# コンパクション判定
if await context.should_compact():
    await hooks.emit(CONTEXT_PRE_COMPACT, {
        "message_count": len(messages),
        "reason": "token_limit_exceeded"
    })

    await context.compact()

    await hooks.emit(CONTEXT_POST_COMPACT, {
        "old_count": len(messages),
        "new_count": len(await context.get_messages())
    })
```

### 2-3. Provider呼び出し

```python
from amplifier_core.events import PROVIDER_REQUEST, PROVIDER_RESPONSE
from amplifier_core.message_models import ChatRequest

# プロバイダー選択（オーケストレーターのポリシー）
provider = providers["anthropic"]

# リクエストイベント
await hooks.emit(PROVIDER_REQUEST, {
    "provider": provider.name,
    "messages": [m.copy() for m in messages],
    "tools": [t.model_dump() for t in tool_specs],
    "model": "claude-sonnet-4-5-20250929"
})

# ChatRequestの構築
request = ChatRequest(
    messages=messages,
    tools=tool_specs,
    temperature=0.7,
    max_output_tokens=4096
)

# プロバイダー呼び出し
response = await provider.complete(request)

# レスポンスイベント
await hooks.emit(PROVIDER_RESPONSE, {
    "provider": provider.name,
    "response": response.model_dump(),
    "usage": response.usage.model_dump() if response.usage else None
})
```

### 2-4. ストリーミング時のイベント

**コンテンツブロック** (`events.py:24-27`):

```python
# ストリーミング開始
await hooks.emit(CONTENT_BLOCK_START, {
    "type": "text",
    "index": 0
})

# 増分受信（複数回）
await hooks.emit(CONTENT_BLOCK_DELTA, {
    "index": 0,
    "delta": "こんにちは"
})

await hooks.emit(CONTENT_BLOCK_DELTA, {
    "index": 0,
    "delta": "、世界"
})

# ストリーミング終了
await hooks.emit(CONTENT_BLOCK_END, {
    "index": 0,
    "type": "text"
})
```

**思考ブロック**（Anthropic拡張）:

```python
await hooks.emit(THINKING_DELTA, {
    "delta": "まず、ユーザーの質問を分析して..."
})

await hooks.emit(THINKING_FINAL, {
    "thinking": "完全な思考プロセステキスト",
    "signature": "sha256:..."
})
```

### 2-5. ツール実行

```python
from amplifier_core.events import TOOL_PRE, TOOL_POST, TOOL_ERROR

# レスポンスからツール呼び出しを抽出
tool_calls = provider.parse_tool_calls(response)

for tool_call in tool_calls:
    # ツール実行前イベント
    hook_result = await hooks.emit(TOOL_PRE, {
        "tool": tool_call.tool,
        "arguments": tool_call.arguments,
        "id": tool_call.id
    })

    # フック結果の処理
    processed_result = await coordinator.process_hook_result(
        hook_result,
        event="tool:pre",
        hook_name="pre-execution-hooks"
    )

    # deny の場合はスキップ
    if processed_result.action == "deny":
        logger.info(f"Tool '{tool_call.tool}' blocked: {processed_result.reason}")

        # ツールブロックをコンテキストに追加
        await context.add_message({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"[Tool execution blocked: {processed_result.reason}]"
        })
        continue

    # ツール取得
    tool = tools.get(tool_call.tool)
    if not tool:
        logger.error(f"Tool '{tool_call.tool}' not found")
        continue

    try:
        # ツール実行
        result = await tool.execute(tool_call.arguments)

        # ツール実行後イベント
        await hooks.emit(TOOL_POST, {
            "tool": tool_call.tool,
            "arguments": tool_call.arguments,
            "result": result.model_dump(),
            "success": result.success
        })

        # 結果をコンテキストに追加
        await context.add_message({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": str(result.output)
        })

    except Exception as e:
        await hooks.emit(TOOL_ERROR, {
            "tool": tool_call.tool,
            "arguments": tool_call.arguments,
            "error": str(e),
            "error_type": type(e).__name__
        })

        # エラーをコンテキストに追加
        await context.add_message({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"[Error: {str(e)}]"
        })
```

## ステップ3: フック結果処理

**コード:** `coordinator.py:342-501`

詳細は [フックシステム](./04-hook-system.md) を参照してください。

### 3-1. コンテキスト注入

```python
if result.action == "inject_context":
    await coordinator._handle_context_injection(result, hook_name, event)
```

**処理内容** (`coordinator.py:378-439`):

1. サイズ検証（デフォルト10KB制限）
2. 予算チェック（デフォルト10,000トークン/ターン）
3. コンテキストへの追加（ephemeral=Falseの場合のみ）
4. 監査ログ

### 3-2. 承認リクエスト

```python
if result.action == "ask_user":
    return await coordinator._handle_approval_request(result, hook_name)
```

**処理内容** (`coordinator.py:441-486`):

1. 承認システムの確認
2. `approval_system.request_approval()` 呼び出し
3. ユーザーの決定を `HookResult` に変換（deny or continue）

### 3-3. ユーザーメッセージ

```python
if result.user_message:
    coordinator._handle_user_message(result, hook_name)
```

**処理内容** (`coordinator.py:488-501`):

1. 表示システムの確認
2. `display_system.show_message()` 呼び出し

## イベントタイムライン例

```
時刻  イベント                    データ
──────────────────────────────────────────────────
t0    session:start              {session_id, config}
t1    prompt:submit              {prompt: "ファイルを読んで"}
t2    context:include            {messages: [...]}
t3    provider:request           {provider: "anthropic", messages}
t4    content_block:start        {type: "text", index: 0}
t5    content_block:delta        {delta: "ファイルを"}
t6    content_block:delta        {delta: "読みます"}
t7    content_block:end          {index: 0}
t8    provider:response          {response, usage}
t9    tool:pre                   {tool: "filesystem:read", arguments}
      → フック処理:
         - 承認リクエスト（production/読み取り）
         - ユーザーが"Allow"を選択
         - HookResult(action="continue")
t10   tool:post                  {tool: "filesystem:read", result}
t11   provider:request           {messages: [..., tool_result]}
t12   provider:response          {response: "ファイルの内容は..."}
t13   prompt:complete            {response}
```

## 次のステップ

- [フックシステム](./04-hook-system.md)でフック処理の詳細を理解
- [モジュール実装例](../module-examples/)で実際のコードを確認
  - [Orchestrator実装例](../module-examples/orchestrator-example.md)
  - [Provider実装例](../module-examples/provider-example.md)
  - [Tool実装例](../module-examples/tool-example.md)
