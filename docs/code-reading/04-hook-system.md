# 04. フックシステム - イベントとフック処理の詳細

## フックシステムとは

フックシステムは、カーネルが発行するライフサイクルイベントを観測し、動作を制御するメカニズムです。

**主な機能:**
- イベントの観測（ログ、監査）
- 動作の制御（deny, modify）
- コンテキスト注入（自動フィードバックループ）
- ユーザー承認リクエスト（動的パーミッション）

## HookResultのアクション

```python
from amplifier_core.models import HookResult

# 1. continue: 通常通り進行
HookResult(action="continue")

# 2. deny: 操作をブロック
HookResult(action="deny", reason="Production file write blocked")

# 3. modify: イベントデータを変更
HookResult(action="modify", data={"tool": "bash", "arguments": modified_args})

# 4. inject_context: エージェントのコンテキストに注入
HookResult(
    action="inject_context",
    context_injection="Linter found 3 errors",
    context_injection_role="system"
)

# 5. ask_user: ユーザー承認を要求
HookResult(
    action="ask_user",
    approval_prompt="Allow write to production/config.py?",
    approval_options=["Allow once", "Allow always", "Deny"]
)
```

## フック実行フロー

**コード:** `hooks.py:111-186`

```
hooks.emit(event, data)
    ↓
デフォルトフィールドマージ
    ↓
FOR EACH handler (優先順位順):
    ├─→ result = handler(event, data)
    ├─→ IF action == "deny":
    │       RETURN deny (短絡評価)
    ├─→ IF action == "modify":
    │       data = result.data (次のハンドラーに渡す)
    ├─→ IF action == "inject_context":
    │       収集リストに追加
    └─→ IF action == "ask_user":
            最初の1つを保持
    ↓
全ハンドラー完了後:
├─→ inject_contextをマージ
└─→ 特別なアクションがあればそれを返す、なければcontinue
```

### デフォルトフィールドのマージ

**コード:** `hooks.py:135-138`

```python
defaults = getattr(self, "_defaults", {})
current_data = {**(defaults or {}), **(data or {})}
```

**設定方法** (`session.py:78`):

```python
session.coordinator.hooks.set_default_fields(
    session_id=session.session_id,
    parent_id=session.parent_id
)
```

**結果:**

```python
# emit時
await hooks.emit("tool:pre", {"tool": "bash", "arguments": {...}})

# ハンドラーが受け取るデータ
{
    "session_id": "uuid-1234...",
    "parent_id": None,
    "tool": "bash",
    "arguments": {...}
}
```

### 優先順位とハンドラー実行

**コード:** `hooks.py:64-96`

```python
coordinator.hooks.register(
    event="tool:pre",
    handler=my_hook,
    priority=10,  # 低い数値 = 高い優先度
    name="my-hook"
)
```

**実行順序:**

```python
# 登録された順序
hooks.register("tool:pre", hook_a, priority=50)
hooks.register("tool:pre", hook_b, priority=10)  # 最初に実行される
hooks.register("tool:pre", hook_c, priority=30)

# 実行順序: hook_b (10) → hook_c (30) → hook_a (50)
```

### 短絡評価（deny）

**コード:** `hooks.py:154-156`

```python
if result.action == "deny":
    logger.info(f"Event '{event}' denied by handler '{hook_handler.name}': {result.reason}")
    return result  # 即座に終了、以降のハンドラーは実行されない
```

**例:**

```python
async def security_hook(event, data):
    if event == "tool:pre" and data["tool"] == "bash":
        if "rm -rf" in data["arguments"].get("command", ""):
            return HookResult(
                action="deny",
                reason="Dangerous command blocked"
            )
    return HookResult(action="continue")

# 登録
hooks.register("tool:pre", security_hook, priority=0, name="security")
```

### データ連鎖（modify）

**コード:** `hooks.py:158-160`

```python
if result.action == "modify" and result.data is not None:
    current_data = result.data
    logger.debug(f"Handler '{hook_handler.name}' modified event data")
```

**例:**

```python
async def sanitizer_hook(event, data):
    if event == "tool:pre" and data["tool"] == "bash":
        # 危険な引数を削除
        sanitized_args = remove_dangerous_flags(data["arguments"])
        return HookResult(
            action="modify",
            data={**data, "arguments": sanitized_args}
        )
    return HookResult(action="continue")
```

### コンテキスト注入のマージ

**コード:** `hooks.py:163-165`, `188-219`

```python
if result.action == "inject_context" and result.context_injection:
    inject_context_results.append(result)

# 全ハンドラー完了後
if inject_context_results:
    special_result = self._merge_inject_context_results(inject_context_results)
```

**マージロジック:**

```python
def _merge_inject_context_results(self, results):
    if len(results) == 1:
        return results[0]

    # すべての注入内容を結合
    combined_content = "\n\n".join(
        result.context_injection
        for result in results
        if result.context_injection
    )

    # 最初のresultの設定を使用
    first = results[0]
    return HookResult(
        action="inject_context",
        context_injection=combined_content,
        context_injection_role=first.context_injection_role,
        ephemeral=first.ephemeral,
        suppress_output=first.suppress_output,
    )
```

## フック結果処理（Coordinator）

**コード:** `coordinator.py:342-501`

Orchestratorがフック結果を受け取った後、Coordinatorが処理をルーティングします。

```python
processed = await coordinator.process_hook_result(
    result=hook_result,
    event="tool:pre",
    hook_name="security-hook"
)
```

### パターン1: コンテキスト注入

**コード:** `coordinator.py:378-439`

```python
async def _handle_context_injection(self, result, hook_name, event):
    content = result.context_injection

    # 1. サイズ検証
    size_limit = self.injection_size_limit  # デフォルト: 10KB
    if size_limit and len(content) > size_limit:
        raise ValueError(f"Context injection exceeds {size_limit} bytes")

    # 2. 予算チェック
    budget = self.injection_budget_per_turn  # デフォルト: 10,000トークン
    tokens = len(content) // 4

    if budget and self._current_turn_injections + tokens > budget:
        logger.warning("Hook injection budget exceeded")

    self._current_turn_injections += tokens

    # 3. コンテキストへの追加（ephemeral=Falseの場合のみ）
    if not result.ephemeral:
        message = {
            "role": result.context_injection_role,
            "content": content,
            "metadata": {
                "source": "hook",
                "hook_name": hook_name,
                "event": event,
                "timestamp": datetime.now().isoformat(),
            },
        }
        await context.add_message(message)

    # 4. 監査ログ
    logger.info("Hook context injection", extra={...})
```

**ephemeralフラグ:**

- `ephemeral=False` (デフォルト): コンテキスト履歴に永続的に保存
- `ephemeral=True`: 現在のターンのみ有効（Orchestratorが一時的に追加）

**例:**

```python
async def linter_hook(event, data):
    if event == "tool:post" and data["tool"] == "filesystem:write":
        errors = run_linter(data["result"]["output"])

        if errors:
            return HookResult(
                action="inject_context",
                context_injection=f"Linter errors:\n{errors}",
                context_injection_role="system",
                ephemeral=False,  # 永続的に保存
                user_message=f"Found {len(errors)} linting issues",
                user_message_level="warning"
            )
    return HookResult(action="continue")
```

### パターン2: 承認リクエスト

**コード:** `coordinator.py:441-486`

```python
async def _handle_approval_request(self, result, hook_name):
    prompt = result.approval_prompt or "Allow this operation?"
    options = result.approval_options or ["Allow", "Deny"]

    # 1. 承認システムの確認
    if self.approval_system is None:
        return HookResult(action="deny", reason="No approval system available")

    try:
        # 2. ユーザーへの承認リクエスト
        decision = await self.approval_system.request_approval(
            prompt=prompt,
            options=options,
            timeout=result.approval_timeout,
            default=result.approval_default
        )

        # 3. 決定の処理
        if decision == "Deny":
            return HookResult(action="deny", reason=f"User denied: {prompt}")

        return HookResult(action="continue")

    except ApprovalTimeoutError:
        # タイムアウト時はデフォルトアクションを適用
        if result.approval_default == "deny":
            return HookResult(action="deny", reason="Approval timeout - denied by default")
        return HookResult(action="continue")
```

**例:**

```python
async def production_guard(event, data):
    if event == "tool:pre" and data["tool"] == "filesystem:write":
        path = data["arguments"].get("path", "")

        if path.startswith("/production/"):
            return HookResult(
                action="ask_user",
                approval_prompt=f"Allow write to {path}?",
                approval_options=["Allow once", "Allow always", "Deny"],
                approval_timeout=300.0,
                approval_default="deny"
            )
    return HookResult(action="continue")
```

### パターン3: ユーザーメッセージ

**コード:** `coordinator.py:488-501`

```python
def _handle_user_message(self, result, hook_name):
    if not result.user_message:
        return

    if self.display_system is None:
        logger.info(f"Hook message: {result.user_message}")
        return

    self.display_system.show_message(
        message=result.user_message,
        level=result.user_message_level,  # info/warning/error
        source=f"hook:{hook_name}"
    )
```

**例:**

```python
async def progress_hook(event, data):
    if event == "tool:post":
        return HookResult(
            action="continue",
            user_message=f"✓ {data['tool']} completed",
            user_message_level="info"
        )
    return HookResult(action="continue")
```

## HookResultの全機能

**モデル定義:** `models.py:35-221`

```python
class HookResult(BaseModel):
    # コアアクション
    action: Literal["continue", "deny", "modify", "inject_context", "ask_user"]

    # 汎用フィールド
    data: dict | None = None
    reason: str | None = None

    # コンテキスト注入
    context_injection: str | None = None
    context_injection_role: Literal["system", "user", "assistant"] = "system"
    ephemeral: bool = False
    append_to_last_tool_result: bool = False

    # 承認ゲート
    approval_prompt: str | None = None
    approval_options: list[str] | None = None
    approval_timeout: float = 300.0
    approval_default: Literal["allow", "deny"] = "deny"

    # 出力制御
    suppress_output: bool = False
    user_message: str | None = None
    user_message_level: Literal["info", "warning", "error"] = "info"
```

## 実装例

詳細な実装例は以下を参照：

- [Hook実装例 - ロギング](../module-examples/hook-example.md#ロギングフック)
- [Hook実装例 - セキュリティ](../module-examples/hook-example.md#セキュリティフック)
- [Hook実装例 - Linter統合](../module-examples/hook-example.md#linterフック)

## 次のステップ

- [コントリビューションチャネル](./05-contribution-channels.md)でプルベース集約を理解
- [Hook実装例](../module-examples/hook-example.md)で実際のコードを確認
