# 00. 開発者向けスタートガイド - 最初の一歩から実行まで

このガイドでは、開発者がAmplifier Coreを使い始める最初のステップから、コードがどのように発火してsession.pyのコンポーネントにつながるのかを追跡します。

## ステップ1: プロジェクトのセットアップ

### 1-1. インストール

```bash
# Amplifier Coreのインストール
pip install amplifier-core

# または、開発用にクローン
git clone https://github.com/microsoft/amplifier-core.git
cd amplifier-core
pip install -e .
```

### 1-2. 最小限のPythonスクリプトを作成

**ファイル: `app.py`**

```python
import asyncio
from amplifier_core import AmplifierSession


async def main():
    """メイン関数 - ここがすべての起点"""

    # 設定を定義
    config = {
        "session": {
            "orchestrator": "loop-basic",
            "context": "context-simple"
        },
        "providers": [
            {
                "module": "provider-anthropic",
                "config": {
                    "api_key": "your-api-key-here"
                }
            }
        ],
        "tools": [
            {"module": "tool-bash", "config": {}},
            {"module": "tool-filesystem", "config": {}}
        ],
        "hooks": []
    }

    # ★ ここが発火ポイント1: セッション作成
    # → session.py:28-82 の __init__ が呼ばれる
    session = AmplifierSession(config)

    # ★ ここが発火ポイント2: モジュール初期化
    # → session.py:95-222 の initialize() が呼ばれる
    await session.initialize()

    # ★ ここが発火ポイント3: プロンプト実行
    # → session.py:224-276 の execute() が呼ばれる
    result = await session.execute("Hello, what can you help me with?")

    print(result)

    # クリーンアップ
    await session.cleanup()


# Pythonスクリプトのエントリーポイント
if __name__ == "__main__":
    asyncio.run(main())
```

このスクリプトを実行：

```bash
python app.py
```

## ステップ2: 実行の流れ - 詳細な追跡

### 発火ポイント1: `AmplifierSession(config)`

**あなたのコード:**
```python
session = AmplifierSession(config)
```

**内部で何が起こるか:**

#### → `session.py:28-82` の `__init__` が呼ばれる

```python
def __init__(
    self,
    config: dict[str, Any],
    loader: ModuleLoader | None = None,
    session_id: str | None = None,
    parent_id: str | None = None,
    approval_system: "ApprovalSystem | None" = None,
    display_system: "DisplaySystem | None" = None,
):
```

**実行される処理:**

```
1. 設定検証 (session.py:56-61)
   ├─ config が空でないかチェック
   ├─ session.orchestrator が存在するかチェック
   └─ session.context が存在するかチェック

2. ID生成 (session.py:64-65)
   ├─ session_id = "uuid-1234-5678-..." を生成
   └─ parent_id = None (トップレベルセッションの場合)

3. ModuleCoordinator作成 (session.py:71-75)
   └─ coordinator = ModuleCoordinator(session=self, ...)
       ↓
       coordinator.py:51-92 の __init__ が呼ばれる
       ├─ マウントポイント初期化
       │  ├─ "orchestrator": None
       │  ├─ "providers": {}
       │  ├─ "tools": {}
       │  ├─ "context": None
       │  ├─ "hooks": HookRegistry()  ← hooks.py:60 で作成
       │  └─ "module-source-resolver": None
       ├─ cleanup_functions = []
       ├─ capabilities = {}
       └─ channels = {}

4. デフォルトフィールド設定 (session.py:78)
   └─ coordinator.hooks.set_default_fields(
          session_id=self.session_id,
          parent_id=self.parent_id
      )
      ↓
      hooks.py:101-109 の set_default_fields が呼ばれる
      └─ self._defaults = {"session_id": "...", "parent_id": None}

5. ModuleLoader作成 (session.py:81)
   └─ loader = ModuleLoader(coordinator=self.coordinator)
       ↓
       loader.py:44-55 の __init__ が呼ばれる
       ├─ _loaded_modules = {}
       ├─ _module_info = {}
       ├─ _search_paths = None
       └─ _coordinator = coordinator
```

**この時点での状態:**

```python
session.session_id = "uuid-1234-5678-..."
session.parent_id = None
session.config = {設定内容}
session._initialized = False
session.coordinator = ModuleCoordinator(...)
session.loader = ModuleLoader(...)
```

---

### 発火ポイント2: `await session.initialize()`

**あなたのコード:**
```python
await session.initialize()
```

**内部で何が起こるか:**

#### → `session.py:95-222` の `initialize()` が呼ばれる

```
1. 初期化チェック (session.py:100-101)
   if self._initialized:
       return  # 既に初期化済みならスキップ

2. Orchestratorのロード (session.py:107-131)
   ├─ orchestrator_id = "loop-basic" を取得
   ├─ loader.load("loop-basic", config, source) を呼び出し
   │   ↓
   │   loader.py:144-220 の load() が呼ばれる
   │   ├─ ソース解決 (ModuleSourceResolver or エントリーポイント)
   │   │   ↓
   │   │   loader.py:249-269 の _load_entry_point() または
   │   │   loader.py:271-292 の _load_filesystem()
   │   │   ├─ importlib.metadata.entry_points() でエントリーポイント検索
   │   │   └─ ep.load() でモジュールの mount 関数をロード
   │   │
   │   └─ mount関数を返す
   │
   ├─ orchestrator_mount(self.coordinator) を呼び出し
   │   ↓
   │   モジュールの mount 関数が実行される
   │   (例: amplifier_module_loop_basic:mount)
   │   ├─ orchestrator = BasicLoopOrchestrator(config)
   │   └─ coordinator.mount("orchestrator", orchestrator)
   │       ↓
   │       coordinator.py:147-180 の mount() が呼ばれる
   │       └─ mount_points["orchestrator"] = orchestrator
   │
   └─ cleanup関数があれば登録

3. Context Managerのロード (session.py:133-154)
   ├─ context_id = "context-simple" を取得
   ├─ loader.load("context-simple", config, source)
   │   └─ (同じローディングプロセス)
   │
   ├─ context_mount(self.coordinator)
   │   └─ coordinator.mount("context", context_instance)
   │       └─ mount_points["context"] = context_instance
   │
   └─ cleanup関数があれば登録

4. Providersのロード (session.py:156-171)
   FOR EACH provider in config["providers"]:
       ├─ loader.load("provider-anthropic", config, source)
       │   ↓
       │   モジュールのmount関数実行
       │   ├─ provider = AnthropicProvider(config)
       │   ├─ coordinator.mount("providers", provider, name="anthropic")
       │   │   └─ mount_points["providers"]["anthropic"] = provider
       │   │
       │   ├─ (オプション) フック登録
       │   │   coordinator.hooks.register("provider:request", handler, ...)
       │   │   └─ hooks.py:64-96 の register() が呼ばれる
       │   │       └─ _handlers["provider:request"].append(HookHandler(...))
       │   │
       │   ├─ (オプション) コントリビューション登録
       │   │   coordinator.register_contributor("metrics", "provider-anthropic", callback)
       │   │   └─ coordinator.py:257-285 が呼ばれる
       │   │       └─ channels["metrics"].append({"name": "...", "callback": ...})
       │   │
       │   └─ cleanup関数を返す
       │
       └─ cleanup関数があれば登録

5. Toolsのロード (session.py:173-188)
   FOR EACH tool in config["tools"]:
       └─ (Providersと同じローディングプロセス)
           └─ mount_points["tools"]["bash"] = bash_tool
           └─ mount_points["tools"]["filesystem"] = filesystem_tool

6. Hooksのロード (session.py:193-208)
   FOR EACH hook in config["hooks"]:
       └─ (同じローディングプロセス)
           └─ フックハンドラーが hooks.register() で登録される

7. 初期化完了フラグ (session.py:210)
   self._initialized = True

8. セッションフォークイベント (session.py:212-216)
   IF self.parent_id:
       hooks.emit(SESSION_FORK, {"parent": parent_id})
```

**この時点での状態:**

```python
session._initialized = True
session.coordinator.mount_points = {
    "orchestrator": <BasicLoopOrchestrator instance>,
    "providers": {
        "anthropic": <AnthropicProvider instance>
    },
    "tools": {
        "bash": <BashTool instance>,
        "filesystem": <FilesystemTool instance>
    },
    "context": <SimpleContextManager instance>,
    "hooks": <HookRegistry with registered handlers>,
    "module-source-resolver": None
}
session.coordinator.hooks._handlers = {
    "provider:request": [<HookHandler>, ...],
    "tool:pre": [<HookHandler>, ...],
    # ...
}
session.coordinator.channels = {
    "metrics": [{"name": "provider-anthropic", "callback": ...}, ...],
    # ...
}
```

---

### 発火ポイント3: `await session.execute(prompt)`

**あなたのコード:**
```python
result = await session.execute("Hello, what can you help me with?")
```

**内部で何が起こるか:**

#### → `session.py:224-276` の `execute()` が呼ばれる

```
1. 初期化チェック (session.py:234-235)
   if not self._initialized:
       await self.initialize()

2. 必須モジュールの取得 (session.py:237-255)
   ├─ orchestrator = coordinator.get("orchestrator")
   │   └─ coordinator.py:203-225 の get()
   │       └─ return mount_points["orchestrator"]
   │           = <BasicLoopOrchestrator instance>
   │
   ├─ context = coordinator.get("context")
   │   └─ return mount_points["context"]
   │       = <SimpleContextManager instance>
   │
   ├─ providers = coordinator.get("providers")
   │   └─ return mount_points["providers"]
   │       = {"anthropic": <AnthropicProvider instance>}
   │
   ├─ tools = coordinator.get("tools") or {}
   │   └─ return mount_points["tools"]
   │       = {"bash": <BashTool>, "filesystem": <FilesystemTool>}
   │
   └─ hooks = coordinator.get("hooks")
       └─ return mount_points["hooks"]
           = <HookRegistry instance>

3. ステータス更新 (session.py:258)
   self.status.status = "running"

4. Orchestratorへの委譲 (session.py:260-267)
   result = await orchestrator.execute(
       prompt="Hello, what can you help me with?",
       context=context,
       providers=providers,
       tools=tools,
       hooks=hooks,
       coordinator=self.coordinator
   )
   ↓
   ★ ここから Orchestrator の内部処理が始まる
   (詳細は次のセクション)

5. ステータス更新と結果返却 (session.py:269-270)
   self.status.status = "completed"
   return result
```

---

## ステップ3: Orchestrator内部の実行フロー

**Orchestratorの `execute()` が呼ばれた後:**

```
orchestrator.execute() 内部:
  ↓
1. プロンプト受信イベント発行
   await hooks.emit(PROMPT_SUBMIT, {"prompt": "Hello, ..."})
   ↓
   hooks.py:111-186 の emit() が呼ばれる
   ├─ デフォルトフィールドをマージ
   │  current_data = {
   │      "session_id": "uuid-...",
   │      "parent_id": None,
   │      "prompt": "Hello, ..."
   │  }
   │
   ├─ FOR EACH handler in _handlers["prompt:submit"]:
   │   ├─ result = await handler(event, current_data)
   │   ├─ IF result.action == "deny": return deny
   │   ├─ IF result.action == "modify": current_data = result.data
   │   └─ IF result.action == "inject_context": 収集
   │
   └─ return HookResult(action="continue", ...)

2. コンテキスト準備
   messages = await context.get_messages()
   ↓
   context_instance.get_messages() が呼ばれる
   └─ return self._messages.copy()

3. ツール仕様の生成
   tool_specs = []
   FOR EACH tool in tools.values():
       tool_specs.append(tool.get_tool_spec())
       ↓
       tool_instance.get_tool_spec() が呼ばれる
       └─ return {"name": "bash", "description": "...", ...}

4. プロバイダー呼び出し
   ├─ リクエストイベント発行
   │  await hooks.emit(PROVIDER_REQUEST, {...})
   │
   ├─ ChatRequestの構築
   │  request = ChatRequest(
   │      messages=messages,
   │      tools=tool_specs,
   │      temperature=0.7,
   │      max_output_tokens=4096
   │  )
   │
   ├─ プロバイダー呼び出し
   │  response = await provider.complete(request)
   │  ↓
   │  provider_instance.complete(request) が呼ばれる
   │  ├─ Anthropic APIにリクエスト送信
   │  ├─ レスポンス受信
   │  └─ ChatResponseに変換して返す
   │
   └─ レスポンスイベント発行
      await hooks.emit(PROVIDER_RESPONSE, {...})

5. ツール呼び出しのパース
   tool_calls = provider.parse_tool_calls(response)
   ↓
   provider_instance.parse_tool_calls(response) が呼ばれる
   └─ return [ToolCall(tool="bash", arguments={...}), ...]

6. IF tool_calls が空:
   └─ レスポンステキストを返して終了

7. IF tool_calls が存在:
   FOR EACH tool_call in tool_calls:
       ├─ ツール実行前イベント
       │  hook_result = await hooks.emit(TOOL_PRE, {
       │      "tool": "bash",
       │      "arguments": {"command": "ls"}
       │  })
       │
       ├─ フック結果処理
       │  processed = await coordinator.process_hook_result(hook_result, ...)
       │  ↓
       │  coordinator.py:342-501 の process_hook_result() が呼ばれる
       │  ├─ IF result.action == "inject_context":
       │  │   await _handle_context_injection(...)
       │  │   ↓
       │  │   coordinator.py:378-439
       │  │   ├─ サイズ検証
       │  │   ├─ 予算チェック
       │  │   ├─ context.add_message({
       │  │   │       "role": "system",
       │  │   │       "content": injection,
       │  │   │       "metadata": {...}
       │  │   │   })
       │  │   └─ 監査ログ
       │  │
       │  ├─ IF result.action == "ask_user":
       │  │   await _handle_approval_request(...)
       │  │   ↓
       │  │   coordinator.py:441-486
       │  │   ├─ approval_system.request_approval(...)
       │  │   └─ return HookResult(deny or continue)
       │  │
       │  └─ IF result.user_message:
       │      display_system.show_message(...)
       │
       ├─ IF processed.action == "deny":
       │   └─ ツール実行をスキップ
       │
       ├─ ツール取得
       │  tool = tools.get("bash")
       │
       ├─ ツール実行
       │  result = await tool.execute({"command": "ls"})
       │  ↓
       │  tool_instance.execute(input) が呼ばれる
       │  ├─ コマンド実行
       │  └─ return ToolResult(success=True, output="...")
       │
       ├─ ツール実行後イベント
       │  await hooks.emit(TOOL_POST, {
       │      "tool": "bash",
       │      "result": result.model_dump()
       │  })
       │
       └─ 結果をコンテキストに追加
          await context.add_message({
              "role": "tool",
              "content": result.output
          })
          ↓
          context_instance.add_message(message) が呼ばれる
          └─ self._messages.append(message)

8. ループ継続（最大ターン数まで）
   └─ ステップ4に戻る（プロバイダー呼び出し）

9. 最終レスポンス返却
   await hooks.emit(PROMPT_COMPLETE, {"response": final_response})
   return final_response
```

---

## 完全な実行フロー図

```
┌─────────────────────────────────────────────────────────────┐
│ app.py                                                      │
│                                                             │
│ if __name__ == "__main__":                                 │
│     asyncio.run(main())  ← Python実行の起点                 │
└─────────────────┬───────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────────┐
│ async def main():                                           │
│                                                             │
│   ★1. session = AmplifierSession(config)                   │
│       ↓                                                     │
│       session.py:28-82 __init__                            │
│       ├─ 設定検証                                           │
│       ├─ session_id生成                                     │
│       ├─ ModuleCoordinator作成                             │
│       │  └─ coordinator.py:51-92 __init__                 │
│       │      ├─ マウントポイント初期化                      │
│       │      └─ HookRegistry作成                           │
│       │          └─ hooks.py:60 __init__                  │
│       ├─ hooks.set_default_fields(session_id, parent_id)  │
│       │  └─ hooks.py:101-109                              │
│       └─ ModuleLoader作成                                  │
│           └─ loader.py:44-55 __init__                     │
│                                                             │
│   ★2. await session.initialize()                          │
│       ↓                                                     │
│       session.py:95-222 initialize                         │
│       ├─ Orchestratorロード                                │
│       │  └─ loader.py:144-220 load                        │
│       │      ├─ エントリーポイント検索                      │
│       │      │  └─ loader.py:249-269 _load_entry_point   │
│       │      └─ mount関数実行                              │
│       │          └─ モジュールの mount(coordinator, config)│
│       │              └─ coordinator.mount("orchestrator", ...)│
│       │                  └─ coordinator.py:147-180        │
│       ├─ Context Managerロード                             │
│       ├─ Providersロード                                   │
│       │  └─ FOR EACH provider:                            │
│       │      ├─ loader.load(...)                          │
│       │      └─ mount(coordinator, config)                │
│       │          ├─ coordinator.mount("providers", ...)   │
│       │          ├─ hooks.register(...) (オプション)       │
│       │          └─ register_contributor(...) (オプション) │
│       ├─ Toolsロード                                       │
│       └─ Hooksロード                                       │
│                                                             │
│   ★3. result = await session.execute(prompt)              │
│       ↓                                                     │
│       session.py:224-276 execute                           │
│       ├─ モジュール取得                                     │
│       │  └─ coordinator.get("orchestrator/context/...")   │
│       │      └─ coordinator.py:203-225                    │
│       └─ orchestrator.execute(...)                         │
│           ↓                                                 │
│           Orchestratorモジュール内部                        │
│           ├─ hooks.emit(PROMPT_SUBMIT)                    │
│           │  └─ hooks.py:111-186 emit                     │
│           │      └─ FOR EACH handler: handler(event, data)│
│           ├─ context.get_messages()                        │
│           ├─ provider.complete(request)                    │
│           │  └─ Providerモジュール内部                     │
│           │      └─ Anthropic API呼び出し                  │
│           ├─ provider.parse_tool_calls(response)           │
│           └─ FOR EACH tool_call:                           │
│               ├─ hooks.emit(TOOL_PRE)                      │
│               ├─ coordinator.process_hook_result(...)      │
│               │  └─ coordinator.py:342-501                │
│               │      ├─ _handle_context_injection         │
│               │      │  └─ context.add_message(...)        │
│               │      ├─ _handle_approval_request          │
│               │      │  └─ approval_system.request_approval│
│               │      └─ _handle_user_message              │
│               │          └─ display_system.show_message   │
│               ├─ tool.execute(arguments)                   │
│               │  └─ Toolモジュール内部                     │
│               ├─ hooks.emit(TOOL_POST)                     │
│               └─ context.add_message(tool_result)          │
│                                                             │
│   print(result)                                            │
│   await session.cleanup()                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## よくある質問

### Q1: モジュールはどこから発見されるのか？

**A:** 3つの方法があります：

1. **エントリーポイント** (`loader.py:249-269`)
   ```toml
   # pyproject.toml
   [project.entry-points."amplifier.modules"]
   loop-basic = "amplifier_module_loop_basic:mount"
   ```

2. **ファイルシステム** (`loader.py:271-292`)
   ```python
   # amplifier_module_loop_basic/__init__.py
   async def mount(coordinator, config):
       ...
   ```

3. **ModuleSourceResolver** (カスタム解決戦略)
   ```python
   # git, ローカルファイル、パッケージから取得
   source_resolver.resolve(module_id, source_uri)
   ```

### Q2: フックはいつ登録されるのか？

**A:** モジュールの `mount()` 関数内で登録されます：

```python
async def mount(coordinator, config):
    # モジュールインスタンス作成
    hook = MyHook(config)

    # フック登録
    coordinator.hooks.register(
        event="tool:pre",
        handler=hook.handle_event,
        priority=0,
        name="my-hook"
    )
    # ↓
    # hooks.py:64-96 の register() が実行される
    # ↓
    # _handlers["tool:pre"].append(HookHandler(...))
```

### Q3: イベントはどのタイミングで発行されるのか？

**A:** Orchestratorモジュール内で発行されます：

```python
# Orchestrator内部
async def execute(self, prompt, context, providers, tools, hooks, coordinator):
    # 1. プロンプト受信時
    await hooks.emit(PROMPT_SUBMIT, {"prompt": prompt})

    # 2. プロバイダー呼び出し前
    await hooks.emit(PROVIDER_REQUEST, {...})

    # 3. プロバイダー呼び出し後
    await hooks.emit(PROVIDER_RESPONSE, {...})

    # 4. ツール実行前
    await hooks.emit(TOOL_PRE, {...})

    # 5. ツール実行後
    await hooks.emit(TOOL_POST, {...})

    # 6. プロンプト完了時
    await hooks.emit(PROMPT_COMPLETE, {...})
```

### Q4: コンテキスト注入はどこで処理されるのか？

**A:** `coordinator.process_hook_result()` で処理されます：

```
Orchestrator
  └─ hooks.emit(TOOL_PRE, ...) → HookResult(action="inject_context", ...)
      ↓
  └─ coordinator.process_hook_result(result, ...)
      ↓
      coordinator.py:342-501
      └─ _handle_context_injection(result, ...)
          ↓
          coordinator.py:378-439
          ├─ サイズ検証
          ├─ 予算チェック
          └─ context.add_message({
                  "role": "system",
                  "content": injection,
                  "metadata": {...}
              })
```

---

## 次のステップ

1. [01-overview.md](./01-overview.md)でアーキテクチャ全体を理解
2. [02-startup-flow.md](./02-startup-flow.md)でモジュールロードの詳細を確認
3. [03-execution-flow.md](./03-execution-flow.md)で実行フローの詳細を学ぶ
4. [モジュール実装例](../module-examples/)で実際のコードを確認
