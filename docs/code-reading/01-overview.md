# 01. 概要 - アーキテクチャ全体像

## Amplifier Coreとは

Amplifier Coreは、モジュラーAIエージェントシステムの超軽量カーネルです。約2,725行のPythonコードで、**Linuxカーネルの設計思想**を基にした「メカニズムであってポリシーではない」という明確な哲学を持っています。

## 2層アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│ KERNEL LAYER (amplifier-core)                               │
│ ・モジュールローディング    ・イベントシステム                │
│ ・セッションライフサイクル  ・コーディネーター                │
│ ・最小限の依存関係          ・安定した契約                   │
└──────────────────┬──────────────────────────────────────────┘
                   │ プロトコル (Tool, Provider等)
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ MODULE LAYER (ユーザースペース - 交換可能)                   │
│ ・Providers: LLMバックエンド (Anthropic, OpenAI等)          │
│ ・Tools: 機能 (filesystem, bash, web, search)               │
│ ・Orchestrators: 実行ループ (basic, streaming, events)      │
│ ・Contexts: メモリ管理 (simple, persistent)                 │
│ ・Hooks: 観測性 (logging, redaction, approval)              │
└─────────────────────────────────────────────────────────────┘
```

## コア設計哲学

### 1. メカニズムであってポリシーではない

**カーネルが提供するメカニズム:**
- モジュールのロード/アンロード機構
- イベントディスパッチシステム
- セッションライフサイクル管理

**カーネルが決して行わないポリシー:**
- プロバイダーやモデルの選択
- オーケストレーション戦略の決定
- ツールの動作選択

### 2. イベントファースト観測性

すべての重要な操作はイベントとして発行されます：

```python
# セッションライフサイクル
await hooks.emit("session:start", {...})
await hooks.emit("session:fork", {...})

# プロンプト処理
await hooks.emit("prompt:submit", {...})
await hooks.emit("prompt:complete", {...})

# プロバイダー呼び出し
await hooks.emit("provider:request", {...})
await hooks.emit("provider:response", {...})

# ツール実行
await hooks.emit("tool:pre", {...})
await hooks.emit("tool:post", {...})
```

### 3. プロトコルベース設計

継承を必要としない構造的サブタイピング：

```python
from typing import Protocol

@runtime_checkable
class Provider(Protocol):
    name: str
    async def complete(request: ChatRequest) -> ChatResponse: ...
    def parse_tool_calls(response: ChatResponse) -> list[ToolCall]: ...
```

モジュールはプロトコルに従うだけで、カーネルから独立しています。

## 主要コンポーネント

### AmplifierSession (`session.py`)
- セッション全体を管理
- モジュールの初期化とライフサイクル制御
- `execute()` でプロンプトを実行

### ModuleCoordinator (`coordinator.py`)
- インフラストラクチャコンテキストの中心
- マウントポイント管理
- フック結果処理のルーティング
- 能力レジストリとコントリビューションチャネル

### HookRegistry (`hooks.py`)
- イベントシステムの実装
- 優先順位ベースのハンドラー実行
- デフォルトフィールド（session_id等）の自動注入

### ModuleLoader (`loader.py`)
- モジュールの発見とロード
- ソース解決（git, file, package）
- エントリーポイント/ファイルシステム経由のロード

## データフロー

```
User Input
    ↓
AmplifierSession.execute()
    ↓
Orchestrator.execute()
    ↓
├─→ hooks.emit(PROMPT_SUBMIT)
├─→ context.get_messages()
├─→ hooks.emit(PROVIDER_REQUEST)
├─→ provider.complete(request)
├─→ hooks.emit(PROVIDER_RESPONSE)
├─→ FOR EACH tool_call:
│   ├─→ hooks.emit(TOOL_PRE)
│   ├─→ coordinator.process_hook_result()
│   ├─→ tool.execute()
│   └─→ hooks.emit(TOOL_POST)
└─→ hooks.emit(PROMPT_COMPLETE)
    ↓
Response
```

## マウントプラン（設定）

セッション作成時に提供する設定：

```python
config = {
    "session": {
        "orchestrator": "loop-basic",
        "context": "context-simple",
        "injection_budget_per_turn": 10000,
        "injection_size_limit": 10240
    },
    "providers": [
        {
            "module": "provider-anthropic",
            "source": "git+https://github.com/...",
            "config": {"api_key": "..."}
        }
    ],
    "tools": [
        {"module": "tool-bash", "config": {}},
        {"module": "tool-filesystem", "config": {}}
    ],
    "hooks": [
        {"module": "hook-logger", "config": {"level": "INFO"}}
    ]
}

session = AmplifierSession(config)
await session.initialize()
```

## イベント分類

**セッションライフサイクル:**
- `session:start`, `session:end`, `session:fork`, `session:resume`

**プロンプトライフサイクル:**
- `prompt:submit`, `prompt:complete`

**プロバイダー呼び出し:**
- `provider:request`, `provider:response`, `provider:error`

**ツール呼び出し:**
- `tool:pre`, `tool:post`, `tool:error`

**コンテキスト管理:**
- `context:pre_compact`, `context:post_compact`, `context:include`

**承認とポリシー:**
- `approval:required`, `approval:granted`, `approval:denied`, `policy:violation`

詳細は `events.py:1-95` を参照。

## 次のステップ

- [起動フロー](./02-startup-flow.md)でモジュールのロード過程を理解
- [実行フロー](./03-execution-flow.md)で実際の動作を追跡
- [モジュール実装例](../module-examples/)で具体的な実装を確認
