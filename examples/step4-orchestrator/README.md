# Step 4: Orchestrator の実装

このステップでは、Provider と Tool を連携させるエージェントループ（Orchestrator）を学びます。

## 学習目標

- **Orchestrator プロトコル**を理解する（execute メソッド）
- **ContextManager プロトコル**を理解する（会話履歴管理）
- **エージェントループ**の仕組みを理解する
- Provider と Tool の**連携方法**を習得する

## ファイル構成

```
examples/step4-orchestrator/
├── README.md           # このファイル
├── app.py              # デモアプリケーション
├── orchestrator.py     # BasicLoopOrchestrator 実装
├── context.py          # SimpleContextManager 実装
└── mount.py            # mount() 関数

modules/
├── amplifier_module_provider_claude_cli/   # Claude CLI Provider
└── amplifier_module_tool_examples/         # 学習用ツール
```

## 実行方法

```bash
cd examples/step4-orchestrator

# 基本デモ（モック Provider）
python app.py

# Claude CLI との統合デモ（APIキー不要）
python app.py --with-llm
```

---

## Orchestrator プロトコル

**定義:** `amplifier_core/interfaces.py`

```python
@runtime_checkable
class Orchestrator(Protocol):
    async def execute(
        self,
        prompt: str,
        context: "ContextManager",
        providers: dict[str, "Provider"],
        tools: dict[str, "Tool"],
        hooks: "HookRegistry",
        coordinator: "ModuleCoordinator" = None,
    ) -> str:
        """
        エージェントループを実行。

        Args:
            prompt: ユーザー入力
            context: コンテキストマネージャー
            providers: 利用可能なプロバイダー
            tools: 利用可能なツール
            hooks: フックレジストリ
            coordinator: コーディネーター（フック結果処理用）

        Returns:
            最終レスポンス文字列
        """
        ...
```

## ContextManager プロトコル

**定義:** `amplifier_core/interfaces.py`

```python
@runtime_checkable
class ContextManager(Protocol):
    async def add_message(self, message: dict[str, Any]) -> None:
        """メッセージを履歴に追加"""
        ...

    async def get_messages(self) -> list[dict[str, Any]]:
        """全履歴を取得"""
        ...

    async def should_compact(self) -> bool:
        """コンパクションが必要か判定"""
        ...

    async def compact(self) -> None:
        """履歴を圧縮"""
        ...

    async def clear(self) -> None:
        """履歴をクリア"""
        ...
```

---

## エージェントループのフロー

```
┌─────────────────────────────────────────────────────────────────┐
│                      Orchestrator.execute()                       │
│                                                                   │
│  1. hooks.emit(PROMPT_SUBMIT)                                    │
│     │                                                             │
│     ▼                                                             │
│  2. context.add_message(user_message)                            │
│     │                                                             │
│     ▼                                                             │
│  ┌──────────────── Main Loop (max_turns) ─────────────────┐     │
│  │                                                          │     │
│  │  3. context.get_messages()                               │     │
│  │     │                                                    │     │
│  │     ▼                                                    │     │
│  │  4. provider.complete(ChatRequest)                       │     │
│  │     │                                                    │     │
│  │     ▼                                                    │     │
│  │  5. context.add_message(assistant_response)             │     │
│  │     │                                                    │     │
│  │     ▼                                                    │     │
│  │  6. tool_calls = provider.parse_tool_calls(response)    │     │
│  │     │                                                    │     │
│  │     ├─── No tool calls ──▶ Return final response        │     │
│  │     │                                                    │     │
│  │     ▼                                                    │     │
│  │  7. For each tool_call:                                 │     │
│  │     ├── hooks.emit(TOOL_PRE)                            │     │
│  │     ├── tool.execute(arguments)                         │     │
│  │     ├── hooks.emit(TOOL_POST)                           │     │
│  │     └── context.add_message(tool_result)                │     │
│  │     │                                                    │     │
│  │     └──────────── Continue loop ─────────────────────┘  │     │
│  │                                                          │     │
│  └──────────────────────────────────────────────────────────┘     │
│     │                                                             │
│     ▼                                                             │
│  8. hooks.emit(PROMPT_COMPLETE)                                  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## BasicLoopOrchestrator の設定

| 設定 | 説明 | デフォルト |
|------|------|----------|
| `max_turns` | 最大ターン数 | 10 |
| `provider` | 使用するプロバイダー名 | 最初のプロバイダー |
| `temperature` | LLM の温度パラメータ | 0.7 |
| `max_tokens` | 最大トークン数 | 4096 |

## SimpleContextManager の設定

| 設定 | 説明 | デフォルト |
|------|------|----------|
| `max_messages` | 最大メッセージ数 | 100 |
| `compact_threshold` | コンパクション閾値 | 80 |
| `keep_system` | システムメッセージを保持 | True |
| `keep_recent` | コンパクト時に保持する最近のメッセージ数 | 20 |

---

## 使用例

### 基本的な使用

```python
from orchestrator import BasicLoopOrchestrator
from context import SimpleContextManager

# セットアップ
orchestrator = BasicLoopOrchestrator({
    "max_turns": 10,
    "temperature": 0.7,
})
context = SimpleContextManager({
    "max_messages": 100,
})

# 実行
result = await orchestrator.execute(
    prompt="What is the weather in Tokyo?",
    context=context,
    providers=providers,
    tools=tools,
    hooks=hooks,
    coordinator=coordinator,
)
```

### modules を使った完全な統合

```python
from amplifier_core import AmplifierSession
from amplifier_core.loader import ModuleLoader

# セッション作成
config = {"session": {"orchestrator": "mock", "context": "mock"}}
session = AmplifierSession(config)
loader = ModuleLoader(coordinator=session.coordinator)

# Provider と Tool をロード
provider_mount = await loader.load("provider-claude-cli", config={"mode": "controlled"})
await provider_mount(session.coordinator)

tool_mount = await loader.load("tool-examples", config={"tools": ["calculator", "weather"]})
await tool_mount(session.coordinator)

# Orchestrator と Context をマウント
from orchestrator import BasicLoopOrchestrator
from context import SimpleContextManager

orchestrator = BasicLoopOrchestrator({"max_turns": 10})
context = SimpleContextManager({})

await session.coordinator.mount("orchestrator", orchestrator)
await session.coordinator.mount("context", context)

# 実行
providers = session.coordinator.get("providers")
tools = session.coordinator.get("tools")

result = await orchestrator.execute(
    prompt="What is 123 + 456?",
    context=context,
    providers=providers,
    tools=tools,
    hooks=session.coordinator.hooks,
    coordinator=session.coordinator,
)
```

---

## 発行されるイベント

Orchestrator は以下のイベントを発行します：

| イベント | タイミング | データ |
|---------|----------|--------|
| `prompt:submit` | ループ開始時 | `{prompt, max_turns}` |
| `provider:request` | Provider 呼び出し前 | `{provider, message_count, tool_count}` |
| `provider:response` | Provider レスポンス受信後 | `{provider, finish_reason, usage}` |
| `provider:error` | Provider エラー時 | `{provider, error, error_type}` |
| `tool:pre` | ツール実行前 | `{tool, arguments, id}` |
| `tool:post` | ツール実行後 | `{tool, arguments, result, success}` |
| `tool:error` | ツールエラー時 | `{tool, arguments, error, error_type}` |
| `context:pre_compact` | コンパクション前 | `{message_count, reason}` |
| `context:post_compact` | コンパクション後 | `{old_count, new_count}` |
| `prompt:complete` | ループ終了時 | `{response, turns}` |

---

## 完全な設定例

```python
config = {
    "session": {
        "orchestrator": {
            "module": "loop-basic",
            "config": {
                "max_turns": 15,
                "provider": "claude-cli",
                "temperature": 0.7,
                "max_tokens": 4096
            }
        },
        "context": {
            "module": "context-simple",
            "config": {
                "max_messages": 100,
                "compact_threshold": 80
            }
        }
    },
    "providers": [
        {
            "module": "provider-claude-cli",
            "config": {
                "mode": "controlled",
                "model": "sonnet"
            }
        }
    ],
    "tools": [
        {
            "module": "tool-examples",
            "config": {
                "tools": ["calculator", "weather"]
            }
        }
    ],
    "hooks": []
}

async with AmplifierSession(config) as session:
    result = await session.execute("What is the weather in Tokyo?")
    print(result)
```

---

## まとめ

1. **Orchestrator**: エージェントループを制御する中心的なコンポーネント
2. **ContextManager**: 会話履歴を管理し、必要に応じてコンパクションを実行
3. **イベントシステム**: ライフサイクルイベントを発行し、観測性を提供
4. **モジュール連携**: Provider と Tool を組み合わせて完全なエージェントを構築

## 次のステップ

- **Step 5**: ContextManager の詳細実装（トークン計算、要約コンパクション）
- **Step 6**: Hook システムの活用（観測性、拡張性）
- **Step 7**: 統合 - 完全なエージェント
