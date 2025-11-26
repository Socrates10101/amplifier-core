# 07. コンポーネントライフサイクル - 各コンポーネントの生成から破棄まで

このガイドでは、session.pyで定義される各コンポーネントのライフサイクルを追跡します。

## 全体のライフサイクル概要

```
作成 → 初期化 → 実行 → クリーンアップ
  ↓       ↓       ↓         ↓
  新規    ロード   実行      破棄
```

## 1. AmplifierSession のライフサイクル

### 1-1. 作成フェーズ

**トリガー:** ユーザーが `AmplifierSession(config)` を呼び出す

**コード:** `session.py:28-82`

```python
# ユーザーコード
session = AmplifierSession(config)

# 内部処理
def __init__(self, config, ...):
    # 1. 設定検証
    if not config:
        raise ValueError("Configuration is required")
    if not config.get("session", {}).get("orchestrator"):
        raise ValueError("Configuration must specify session.orchestrator")
    if not config.get("session", {}).get("context"):
        raise ValueError("Configuration must specify session.context")

    # 2. ID生成
    self.session_id = session_id or str(uuid.uuid4())
    self.parent_id = parent_id

    # 3. 設定とステータスの保存
    self.config = config
    self.status = SessionStatus(session_id=self.session_id)
    self._initialized = False

    # 4. Coordinatorの作成 ← ★重要
    self.coordinator = ModuleCoordinator(
        session=self,
        approval_system=approval_system,
        display_system=display_system,
    )

    # 5. デフォルトフィールドの設定 ← ★重要
    self.coordinator.hooks.set_default_fields(
        session_id=self.session_id,
        parent_id=self.parent_id
    )

    # 6. Loaderの作成
    self.loader = loader or ModuleLoader(coordinator=self.coordinator)
```

**作成されるオブジェクト:**
- `AmplifierSession` インスタンス
- `ModuleCoordinator` インスタンス
- `HookRegistry` インスタンス（Coordinator内部で作成）
- `ModuleLoader` インスタンス
- `SessionStatus` インスタンス

**状態:**
```python
session._initialized = False
session.coordinator.mount_points = {
    "orchestrator": None,
    "providers": {},
    "tools": {},
    "context": None,
    "hooks": HookRegistry(),
    "module-source-resolver": None
}
```

---

### 1-2. 初期化フェーズ

**トリガー:** ユーザーが `await session.initialize()` を呼び出す

**コード:** `session.py:95-222`

```python
# ユーザーコード
await session.initialize()

# 内部処理
async def initialize(self):
    if self._initialized:
        return

    # 各モジュールを順番にロード
    # 1. Orchestrator
    # 2. Context Manager
    # 3. Providers
    # 4. Tools
    # 5. Hooks
```

#### サブフェーズ1: Orchestratorのロード

**コード:** `session.py:107-131`

```
1. 設定解析
   orchestrator_spec = config.get("session", {}).get("orchestrator")
   └─ "loop-basic" または {"module": "loop-basic", "config": {...}}

2. Loaderでロード
   orchestrator_mount = await self.loader.load(orchestrator_id, ...)
   ↓
   loader.py:144-220 load()
   ├─ ソース解決
   │  └─ ModuleSourceResolver.resolve() または直接発見
   │
   ├─ エントリーポイントロード
   │  └─ loader.py:249-269 _load_entry_point()
   │      ├─ importlib.metadata.entry_points(group="amplifier.modules")
   │      ├─ ep.load() でmount関数を取得
   │      └─ mount_with_config() ラッパーを返す
   │
   └─ mount関数を返す

3. mount関数の実行
   cleanup = await orchestrator_mount(self.coordinator)
   ↓
   モジュールの mount(coordinator, config) が実行される
   ↓
   例: amplifier_module_loop_basic.mount()
   ├─ orchestrator = BasicLoopOrchestrator(config)
   │   └─ orchestrator.__init__()
   │       ├─ self._max_turns = config.get("max_turns", 10)
   │       ├─ self._provider_name = config.get("provider")
   │       ├─ self._temperature = config.get("temperature", 0.7)
   │       └─ self._max_tokens = config.get("max_tokens", 4096)
   │
   ├─ await coordinator.mount("orchestrator", orchestrator)
   │   ↓
   │   coordinator.py:147-180 mount()
   │   └─ self.mount_points["orchestrator"] = orchestrator
   │       logger.info(f"Mounted {orchestrator.__class__.__name__} at orchestrator")
   │
   └─ return cleanup_function (またはNone)

4. cleanup関数の登録
   if cleanup:
       self.coordinator.register_cleanup(cleanup)
       ↓
       coordinator.py:227-229 register_cleanup()
       └─ self._cleanup_functions.append(cleanup)
```

**状態変化:**
```python
# 前
session.coordinator.mount_points["orchestrator"] = None

# 後
session.coordinator.mount_points["orchestrator"] = <BasicLoopOrchestrator instance>
session.coordinator._cleanup_functions = [cleanup_function]  # あれば
```

#### サブフェーズ2: Context Managerのロード

**コード:** `session.py:133-154`

```
同じパターン:
1. 設定解析 → context_id = "context-simple"
2. loader.load(context_id, ...)
3. context_mount(self.coordinator)
   ├─ context = SimpleContextManager(config)
   │   └─ context.__init__()
   │       ├─ self._max_messages = config.get("max_messages", 100)
   │       ├─ self._max_tokens = config.get("max_tokens", 8000)
   │       ├─ self._messages = []
   │       └─ self._total_tokens = 0
   │
   └─ coordinator.mount("context", context)
4. cleanup関数の登録
```

**状態変化:**
```python
session.coordinator.mount_points["context"] = <SimpleContextManager instance>
```

#### サブフェーズ3: Providersのロード

**コード:** `session.py:156-171`

```
FOR EACH provider_config in config["providers"]:
    1. module_id = provider_config.get("module")  # "provider-anthropic"

    2. loader.load(module_id, provider_config.get("config"), ...)

    3. provider_mount(self.coordinator)
       ├─ provider = AnthropicProvider(config)
       │   └─ provider.__init__()
       │       ├─ self.name = "anthropic"
       │       ├─ self._api_key = config.get("api_key")
       │       ├─ self._client = AsyncAnthropic(api_key=...)
       │       ├─ self.request_count = 0
       │       ├─ self.total_input_tokens = 0
       │       └─ self.total_output_tokens = 0
       │
       ├─ coordinator.mount("providers", provider, name="anthropic")
       │   ↓
       │   coordinator.py:147-180 mount()
       │   └─ self.mount_points["providers"]["anthropic"] = provider
       │
       ├─ (オプション) フック登録
       │   coordinator.hooks.register(
       │       "provider:request",
       │       provider.on_request,
       │       priority=0,
       │       name="anthropic-logger"
       │   )
       │   ↓
       │   hooks.py:64-96 register()
       │   ├─ hook_handler = HookHandler(
       │   │       handler=provider.on_request,
       │   │       priority=0,
       │   │       name="anthropic-logger"
       │   │   )
       │   ├─ self._handlers["provider:request"].append(hook_handler)
       │   └─ self._handlers["provider:request"].sort()  # 優先順位順
       │
       ├─ (オプション) コントリビューション登録
       │   coordinator.register_contributor(
       │       "metrics.providers",
       │       "provider-anthropic",
       │       lambda: {"requests": provider.request_count, ...}
       │   )
       │   ↓
       │   coordinator.py:257-285 register_contributor()
       │   └─ self.channels["metrics.providers"].append({
       │           "name": "provider-anthropic",
       │           "callback": lambda: {...}
       │       })
       │
       └─ return cleanup_function

    4. cleanup関数の登録
```

**状態変化:**
```python
session.coordinator.mount_points["providers"] = {
    "anthropic": <AnthropicProvider instance>
}
session.coordinator.hooks._handlers = {
    "provider:request": [<HookHandler for anthropic-logger>]
}
session.coordinator.channels = {
    "metrics.providers": [{"name": "provider-anthropic", "callback": ...}]
}
```

#### サブフェーズ4: Toolsのロード

**コード:** `session.py:173-188`

```
FOR EACH tool_config in config["tools"]:
    1. module_id = tool_config.get("module")  # "tool-bash"

    2. loader.load(module_id, ...)

    3. tool_mount(self.coordinator)
       ├─ tool = BashTool(config)
       │   └─ tool.__init__()
       │       ├─ self.name = "bash"
       │       ├─ self.description = "Execute shell commands..."
       │       ├─ self._timeout = config.get("timeout", 30)
       │       ├─ self.execution_count = 0
       │       └─ self.failure_count = 0
       │
       ├─ coordinator.mount("tools", tool, name="bash")
       │   └─ mount_points["tools"]["bash"] = tool
       │
       ├─ (オプション) カスタムイベント宣言
       │   coordinator.register_contributor(
       │       "observability.events",
       │       "tool-bash",
       │       lambda: ["bash:execute", "bash:complete", ...]
       │   )
       │
       └─ return None  # cleanup不要
```

**状態変化:**
```python
session.coordinator.mount_points["tools"] = {
    "bash": <BashTool instance>,
    "filesystem": <FilesystemTool instance>
}
session.coordinator.channels = {
    "observability.events": [
        {"name": "tool-bash", "callback": lambda: [...]},
        {"name": "tool-filesystem", "callback": lambda: [...]}
    ],
    ...
}
```

#### サブフェーズ5: Hooksのロード

**コード:** `session.py:193-208`

```
FOR EACH hook_config in config["hooks"]:
    1. module_id = hook_config.get("module")  # "hook-security"

    2. loader.load(module_id, ...)

    3. hook_mount(self.coordinator)
       ├─ hook = SecurityHook(config)
       │   └─ hook.__init__()
       │       ├─ self._blocked_commands = config.get("blocked_commands", [...])
       │       └─ self._protected_paths = config.get("protected_paths", [...])
       │
       ├─ coordinator.hooks.register(
       │       "tool:pre",
       │       hook.handle_tool_pre,
       │       priority=0,  # 最高優先度
       │       name="security-hook"
       │   )
       │   ↓
       │   hooks.py:64-96 register()
       │   └─ _handlers["tool:pre"].append(HookHandler(...))
       │
       └─ return None
```

**状態変化:**
```python
session.coordinator.hooks._handlers = {
    "tool:pre": [
        <HookHandler for security-hook, priority=0>,
        <HookHandler for logging-hook, priority=999>
    ],
    "provider:request": [...],
    ...
}
```

#### 初期化完了

**コード:** `session.py:210-218`

```python
# 1. 初期化フラグを設定
self._initialized = True

# 2. セッションフォークイベント（子セッションの場合のみ）
if self.parent_id:
    from .events import SESSION_FORK
    await self.coordinator.hooks.emit(SESSION_FORK, {"parent": self.parent_id})
    ↓
    hooks.py:111-186 emit()
    └─ FOR EACH handler in _handlers["session:fork"]:
        └─ await handler("session:fork", {
               "session_id": self.session_id,
               "parent_id": self.parent_id,
               "parent": self.parent_id
           })

logger.info(f"Session {self.session_id} initialized successfully")
```

**最終状態:**
```python
session._initialized = True
session.coordinator.mount_points = {
    "orchestrator": <BasicLoopOrchestrator>,
    "providers": {"anthropic": <AnthropicProvider>},
    "tools": {"bash": <BashTool>, "filesystem": <FilesystemTool>},
    "context": <SimpleContextManager>,
    "hooks": <HookRegistry with handlers>,
    "module-source-resolver": None
}
session.coordinator._cleanup_functions = [cleanup1, cleanup2, ...]
session.coordinator.hooks._handlers = {
    "session:fork": [...],
    "tool:pre": [...],
    "provider:request": [...],
    ...
}
session.coordinator.channels = {
    "observability.events": [...],
    "metrics.providers": [...],
    "metrics.tools": [...],
    ...
}
```

---

### 1-3. 実行フェーズ

**トリガー:** ユーザーが `await session.execute(prompt)` を呼び出す

**コード:** `session.py:224-276`

```python
# ユーザーコード
result = await session.execute("Hello, Claude!")

# 内部処理
async def execute(self, prompt: str) -> str:
    # 1. 初期化チェック
    if not self._initialized:
        await self.initialize()

    # 2. 必須モジュールの取得
    orchestrator = self.coordinator.get("orchestrator")
    context = self.coordinator.get("context")
    providers = self.coordinator.get("providers")
    tools = self.coordinator.get("tools") or {}
    hooks = self.coordinator.get("hooks")

    # 検証
    if not orchestrator:
        raise RuntimeError("No orchestrator module mounted")
    if not context:
        raise RuntimeError("No context manager mounted")
    if not providers:
        raise RuntimeError("No providers mounted")

    # 3. ステータス更新
    self.status.status = "running"

    # 4. Orchestratorに委譲 ← ★ここからOrchestrator内部へ
    result = await orchestrator.execute(
        prompt=prompt,
        context=context,
        providers=providers,
        tools=tools,
        hooks=hooks,
        coordinator=self.coordinator,
    )

    # 5. ステータス更新
    self.status.status = "completed"

    return result
```

#### Orchestrator内部の実行

**コード:** Orchestratorモジュール内部（例: `amplifier_module_loop_basic`）

```
orchestrator.execute() 内部:

1. プロンプト受信イベント
   await hooks.emit(PROMPT_SUBMIT, {"prompt": prompt})
   ↓
   hooks.py:111-186 emit()
   ├─ デフォルトフィールドをマージ
   │  current_data = {
   │      "session_id": session.session_id,
   │      "parent_id": session.parent_id,
   │      "prompt": prompt
   │  }
   │
   ├─ handlers = self._handlers.get("prompt:submit", [])
   │  = [<HookHandler priority=10>, <HookHandler priority=999>]
   │
   └─ FOR EACH handler (優先順位順):
       ├─ result = await handler.handler("prompt:submit", current_data)
       │   ↓
       │   フックモジュールの handler(event, data) が実行される
       │   └─ return HookResult(action="continue")
       │
       ├─ IF result.action == "deny":
       │   └─ return result  # 短絡評価
       │
       ├─ IF result.action == "modify":
       │   └─ current_data = result.data
       │
       └─ IF result.action == "inject_context":
           └─ inject_context_results.append(result)

2. コンテキスト準備
   messages = await context.get_messages()
   ↓
   context_instance.get_messages() が実行される
   └─ return self._messages.copy()

3. ツール仕様生成
   tool_specs = []
   FOR tool in tools.values():
       tool_specs.append(tool.get_tool_spec())
       ↓
       tool_instance.get_tool_spec() が実行される
       └─ return {"name": "bash", "description": "...", ...}

4. プロバイダー呼び出し
   ├─ await hooks.emit(PROVIDER_REQUEST, {...})
   │
   ├─ request = ChatRequest(
   │       messages=messages,
   │       tools=tool_specs,
   │       temperature=self._temperature,
   │       max_output_tokens=self._max_tokens
   │   )
   │
   ├─ response = await provider.complete(request)
   │   ↓
   │   provider_instance.complete(request) が実行される
   │   ├─ self.request_count += 1
   │   ├─ Anthropic APIにリクエスト送信
   │   ├─ レスポンス受信
   │   ├─ ChatResponseに変換
   │   ├─ 統計更新
   │   │  self.total_input_tokens += response.usage.input_tokens
   │   │  self.total_output_tokens += response.usage.output_tokens
   │   └─ return ChatResponse(...)
   │
   └─ await hooks.emit(PROVIDER_RESPONSE, {...})

5. ツール呼び出し処理
   tool_calls = provider.parse_tool_calls(response)

   IF tool_calls が空:
       └─ レスポンステキストを返して終了

   FOR EACH tool_call:
       ├─ await hooks.emit(TOOL_PRE, {...})
       │
       ├─ processed = await coordinator.process_hook_result(...)
       │   ↓
       │   coordinator.py:342-501 process_hook_result()
       │   ├─ IF result.action == "inject_context":
       │   │   await _handle_context_injection(...)
       │   │   ↓
       │   │   ├─ サイズ検証
       │   │   ├─ 予算チェック
       │   │   │  self._current_turn_injections += tokens
       │   │   ├─ context.add_message({...})
       │   │   │   ↓
       │   │   │   context_instance.add_message(message)
       │   │   │   └─ self._messages.append(message)
       │   │   │       self._total_tokens += tokens
       │   │   └─ logger.info("Hook context injection", ...)
       │   │
       │   ├─ IF result.action == "ask_user":
       │   │   return await _handle_approval_request(...)
       │   │   ↓
       │   │   ├─ decision = await approval_system.request_approval(...)
       │   │   └─ return HookResult(deny or continue)
       │   │
       │   └─ IF result.user_message:
       │       display_system.show_message(...)
       │
       ├─ IF processed.action == "deny":
       │   └─ ツール実行をスキップ
       │
       ├─ tool = tools.get(tool_call.tool)
       │
       ├─ result = await tool.execute(tool_call.arguments)
       │   ↓
       │   tool_instance.execute(input) が実行される
       │   ├─ self.execution_count += 1
       │   ├─ コマンド実行（例: asyncio.create_subprocess_shell）
       │   ├─ 統計更新
       │   │  self.total_duration += duration
       │   └─ return ToolResult(success=True, output=...)
       │
       ├─ await hooks.emit(TOOL_POST, {...})
       │
       └─ await context.add_message({
               "role": "tool",
               "content": result.output
           })
           ↓
           context_instance.add_message(message)
           └─ self._messages.append(message)

6. ループ継続または終了
   IF tool_calls がある:
       └─ ステップ4に戻る（プロバイダー呼び出し）
   ELSE:
       └─ 最終レスポンスを返す

7. プロンプト完了イベント
   await hooks.emit(PROMPT_COMPLETE, {"response": final_response})

   return final_response
```

**状態変化:**
```python
# 実行前
context._messages = [...]
context._total_tokens = 500
provider.request_count = 0
tool.execution_count = 0

# 実行後
context._messages = [..., user_message, assistant_message, tool_message, ...]
context._total_tokens = 2500
provider.request_count = 3
provider.total_input_tokens = 1500
provider.total_output_tokens = 1000
tool.execution_count = 5
tool.total_duration = 2.5
```

---

### 1-4. クリーンアップフェーズ

**トリガー:** ユーザーが `await session.cleanup()` を呼び出す

**コード:** `session.py:278-280`

```python
# ユーザーコード
await session.cleanup()

# 内部処理
async def cleanup(self):
    await self.coordinator.cleanup()
    ↓
    coordinator.py:324-336 cleanup()
    └─ FOR cleanup_fn in reversed(self._cleanup_functions):
           ├─ IF callable(cleanup_fn):
           │   ├─ IF iscoroutinefunction(cleanup_fn):
           │   │   await cleanup_fn()
           │   │   ↓
           │   │   モジュールのcleanup関数が実行される
           │   │   例: provider.close()
           │   │       └─ await self._client.close()
           │   │
           │   └─ ELSE:
           │       cleanup_fn()
           │
           └─ logger.debug("Cleanup function executed")
```

**状態変化:**
```python
# クリーンアップ後
provider._client = None  # 接続クローズ
# その他のリソース解放
```

---

## 2. 各コンポーネントの詳細ライフサイクル

### 2-1. ModuleCoordinator

**作成:** `session.py:71-75`
```python
self.coordinator = ModuleCoordinator(session=self, ...)
↓
coordinator.py:51-92 __init__
├─ self._session = session
├─ self.mount_points = {...}
├─ self._cleanup_functions = []
├─ self._capabilities = {}
├─ self.channels = {}
├─ self.hooks = HookRegistry()
├─ self.approval_system = approval_system
├─ self.display_system = display_system
└─ self._current_turn_injections = 0
```

**使用中:**
- `coordinator.mount()` - モジュールのマウント
- `coordinator.get()` - モジュールの取得
- `coordinator.process_hook_result()` - フック結果の処理
- `coordinator.register_capability()` - 能力の登録
- `coordinator.register_contributor()` - コントリビューターの登録
- `coordinator.collect_contributions()` - 貢献の収集
- `coordinator.reset_turn()` - ターン境界でのリセット

**クリーンアップ:** `coordinator.py:324-336`

---

### 2-2. HookRegistry

**作成:** `coordinator.py:72` (Coordinator内部で作成)
```python
self.hooks = HookRegistry()
↓
hooks.py:60 __init__
└─ self._handlers = defaultdict(list)
```

**使用中:**
- `hooks.set_default_fields()` - デフォルトフィールド設定
- `hooks.register()` - ハンドラー登録
- `hooks.emit()` - イベント発行
- `hooks.list_handlers()` - ハンドラー一覧取得

---

### 2-3. ModuleLoader

**作成:** `session.py:81`
```python
self.loader = ModuleLoader(coordinator=self.coordinator)
↓
loader.py:44-55 __init__
├─ self._loaded_modules = {}
├─ self._module_info = {}
├─ self._search_paths = None
└─ self._coordinator = coordinator
```

**使用中:**
- `loader.load()` - モジュールのロード

---

### 2-4. モジュール（Provider, Tool, etc.）

**ロード:** `loader.py:144-220`
```
loader.load(module_id, config, source)
├─ ソース解決
├─ エントリーポイント検索
├─ mount関数の取得
└─ mount_with_config() ラッパーを返す
```

**マウント:** モジュールの `mount(coordinator, config)`
```
mount(coordinator, config)
├─ instance = MyModule(config)
├─ coordinator.mount("providers", instance, name="my-provider")
├─ hooks.register(...) (オプション)
├─ register_contributor(...) (オプション)
└─ return cleanup_function (オプション)
```

**使用中:**
- Provider: `provider.complete(request)`
- Tool: `tool.execute(input)`
- Orchestrator: `orchestrator.execute(...)`
- Context: `context.add_message()`, `context.get_messages()`

**クリーンアップ:** `cleanup_function()` が実行される

---

## まとめ: 完全なライフサイクル図

```
User Code:
    session = AmplifierSession(config)
        ↓
    [作成フェーズ]
    ├─ Session.__init__()
    │  ├─ 設定検証
    │  ├─ ID生成
    │  ├─ Coordinator.__init__()
    │  │  ├─ mount_points初期化
    │  │  └─ HookRegistry.__init__()
    │  ├─ hooks.set_default_fields()
    │  └─ Loader.__init__()
    │
    await session.initialize()
        ↓
    [初期化フェーズ]
    ├─ Session.initialize()
    │  ├─ loader.load("loop-basic")
    │  │  ├─ エントリーポイント検索
    │  │  └─ mount関数取得
    │  ├─ orchestrator_mount(coordinator)
    │  │  ├─ Orchestrator.__init__()
    │  │  ├─ coordinator.mount("orchestrator", ...)
    │  │  └─ return cleanup
    │  ├─ (同様にContext, Providers, Tools, Hooksをロード)
    │  └─ hooks.emit(SESSION_FORK) (子セッションの場合)
    │
    await session.execute(prompt)
        ↓
    [実行フェーズ]
    ├─ Session.execute()
    │  ├─ モジュール取得
    │  └─ orchestrator.execute(...)
    │      ├─ hooks.emit(PROMPT_SUBMIT)
    │      │  └─ FOR EACH handler: handler(event, data)
    │      ├─ context.get_messages()
    │      ├─ hooks.emit(PROVIDER_REQUEST)
    │      ├─ provider.complete(request)
    │      │  └─ Anthropic API呼び出し
    │      ├─ hooks.emit(PROVIDER_RESPONSE)
    │      ├─ FOR EACH tool_call:
    │      │  ├─ hooks.emit(TOOL_PRE)
    │      │  ├─ coordinator.process_hook_result()
    │      │  │  ├─ _handle_context_injection()
    │      │  │  │  └─ context.add_message()
    │      │  │  ├─ _handle_approval_request()
    │      │  │  └─ _handle_user_message()
    │      │  ├─ tool.execute(arguments)
    │      │  ├─ hooks.emit(TOOL_POST)
    │      │  └─ context.add_message(tool_result)
    │      └─ hooks.emit(PROMPT_COMPLETE)
    │
    await session.cleanup()
        ↓
    [クリーンアップフェーズ]
    └─ Session.cleanup()
       └─ coordinator.cleanup()
          └─ FOR EACH cleanup_fn (逆順):
             └─ cleanup_fn()
                └─ モジュールのリソース解放
```

---

## 次のステップ

- [00-getting-started.md](./00-getting-started.md)で最初のステップを確認
- [02-startup-flow.md](./02-startup-flow.md)で初期化の詳細を学ぶ
- [03-execution-flow.md](./03-execution-flow.md)で実行フローを理解
