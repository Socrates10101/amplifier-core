# Step 3: Tool の実装

このステップでは、エージェントが使用できるツールの仕組みを学びます。

## 学習目標

- **Tool プロトコル**を理解する（name, description, execute）
- **ToolCall / ToolResult** の構造を理解する
- **Amplifier Core のモジュールローディング**を理解する
- **Claude CLI Provider** を使った実際のツール実行を体験する

## ファイル構成

```
examples/
├── amplifier_module_provider_claude_cli/   # Claude CLI Provider モジュール
│   ├── __init__.py
│   ├── provider.py                         # Provider 実装
│   └── mount.py                            # mount() 関数
│
├── amplifier_module_tool_examples/         # 学習用ツールモジュール
│   ├── __init__.py
│   ├── tools.py                            # Tool 実装
│   └── mount.py                            # mount() 関数
│
└── step3-tool/
    ├── README.md                           # このファイル
    └── app.py                              # デモアプリケーション
```

## 実行方法

```bash
cd examples/step3-tool

# 基本デモ
python app.py

# Claude CLI との統合デモ（APIキー不要）
python app.py --with-llm
```

## Amplifier Core モジュール規約

### ディレクトリ命名

モジュールは `amplifier_module_{module_id}` の形式で命名：

```
amplifier_module_provider_claude_cli/   → module-id: "provider-claude-cli"
amplifier_module_tool_examples/         → module-id: "tool-examples"
```

### mount() 関数のシグネチャ

```python
async def mount(
    coordinator: ModuleCoordinator,
    config: dict[str, Any]
) -> Callable[[], Awaitable[None]] | None:
    """
    モジュールを Coordinator にマウント。

    Args:
        coordinator: ModuleCoordinator インスタンス
        config: モジュール設定

    Returns:
        クリーンアップ関数（または None）
    """
    # 1. インスタンス作成
    provider = MyProvider(config)

    # 2. Coordinator にマウント
    await coordinator.mount("providers", provider, name="my-provider")

    # 3. クリーンアップ関数を返す
    async def cleanup():
        ...
    return cleanup
```

### ModuleLoader による読み込み

```python
from amplifier_core.loader import ModuleLoader

loader = ModuleLoader(coordinator=session.coordinator)

# モジュールをロードしてマウント
mount_fn = await loader.load("provider-claude-cli", config={"mode": "controlled"})
await mount_fn(session.coordinator)
```

## provider-claude-cli モジュール

### 概要

ローカルで認証済みの Claude Code CLI を Amplifier の Provider として使用。
**APIキー不要**で実際の Claude とやり取りできます。

### モード

| モード | 説明 |
|--------|------|
| `passthrough` | CLIに全て任せる |
| `controlled` | CLIのツールを無効化し、Amplifier側でツール実行を制御（推奨） |

### 設定

```python
{
    "module": "provider-claude-cli",
    "config": {
        "mode": "controlled",    # "passthrough" or "controlled"
        "model": "sonnet",       # optional: model name
        "timeout": 300,          # optional: timeout in seconds
        "name": "claude-cli"     # optional: provider name
    }
}
```

### controlled モードのアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│ Amplifier Core                                              │
│                                                             │
│  1. ChatRequest + ToolSpec                                  │
│     │                                                       │
│     ▼                                                       │
│  ┌─────────────────────────────────────────────────┐       │
│  │ ClaudeCliProvider                               │       │
│  │ (claude -p "..." --tools "" --output-format json)│       │
│  └─────────────────────────────────────────────────┘       │
│     │                                                       │
│     ▼                                                       │
│  2. ChatResponse (finish_reason="tool_use")                │
│     │                                                       │
│     ▼                                                       │
│  3. parse_tool_calls() でツールコールを検出                  │
│     │                                                       │
│     ▼                                                       │
│  ┌─────────────────────────────────────────────────┐       │
│  │ Tool.execute()  ← Amplifier 側でツールを実行    │       │
│  └─────────────────────────────────────────────────┘       │
│     │                                                       │
│     ▼                                                       │
│  4. ToolResult を LLM にフィードバック                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## tool-examples モジュール

### 設定

```python
{
    "module": "tool-examples",
    "config": {
        "tools": ["calculator", "weather"]  # マウントするツール
    }
}
```

### 利用可能なツール

| ツール | 説明 |
|--------|------|
| `calculator` | 四則演算 |
| `weather` | 天気情報（モック） |
| `file_reader` | ファイル読み取り（仮想FS） |
| `multi_step` | 状態管理 |

## Tool プロトコル

```python
from typing import Protocol, Any

class Tool(Protocol):
    @property
    def name(self) -> str:
        """ツール識別子"""
        ...

    @property
    def description(self) -> str:
        """ツールの説明（LLMが参照）"""
        ...

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """ツールを実行"""
        ...
```

### ToolSpec（LLM 用ツール定義）

```python
def get_spec(self) -> ToolSpec:
    return ToolSpec(
        name=self.name,
        description=self.description,
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression"
                }
            },
            "required": ["expression"]
        }
    )
```

## 本番環境での使用

### Entry Point 登録（推奨）

`pyproject.toml`:

```toml
[project.entry-points."amplifier.modules"]
provider-claude-cli = "amplifier_module_provider_claude_cli:mount"
tool-examples = "amplifier_module_tool_examples:mount"
```

### 完全な設定例

```python
config = {
    "session": {
        "orchestrator": "loop-basic",
        "context": "context-simple"
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

## まとめ

1. **モジュール命名**: `amplifier_module_{module_id}`
2. **mount() シグネチャ**: `async def mount(coordinator, config) -> cleanup | None`
3. **Provider モード**: `controlled` で Amplifier 側でツール実行を制御
4. **Tool プロトコル**: `name`, `description`, `execute()`, `get_spec()`

## 次のステップ

Step 4 では、Provider と Tool を連携させる **Orchestrator** を実装します。
