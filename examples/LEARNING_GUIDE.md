# Amplifier Core 学習ガイド

このガイドでは、Amplifier Coreの各コンポーネントを段階的に学んでいきます。

## アーキテクチャ概要

```
┌─────────────────────────────────────────────────────────────┐
│                     AmplifierSession                        │
│  (メインエントリーポイント - セッションライフサイクル管理)      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    ModuleCoordinator                        │
│  (インフラストラクチャハブ - モジュール間の調整)              │
│                                                             │
│  マウントポイント:                                          │
│  ├── orchestrator (single) : エージェントループ制御          │
│  ├── context (single)      : 会話履歴管理                   │
│  ├── providers (multi)     : LLMバックエンド                │
│  ├── tools (multi)         : エージェント機能               │
│  └── hooks (built-in)      : イベントシステム               │
└─────────────────────────────────────────────────────────────┘
```

## ディレクトリ構成

```
examples/
├── LEARNING_GUIDE.md                       # このファイル
│
├── step1-basics/                           # Step 1: 基本構造
├── step2-provider/                         # Step 2: Provider
├── step3-tool/                             # Step 3: Tool
├── step4-orchestrator/                     # Step 4: Orchestrator
│   ├── app.py                              # デモアプリケーション
│   ├── orchestrator.py                     # BasicLoopOrchestrator 実装
│   ├── context.py                          # SimpleContextManager 実装
│   ├── mount.py                            # mount() 関数
│   └── README.md                           # ドキュメント
└── step5-context/                          # Step 5: ContextManager詳細
    ├── app.py                              # デモアプリケーション
    ├── context.py                          # AdvancedContextManager 実装
    ├── tokenizer.py                        # トークン計算ユーティリティ
    └── README.md                           # ドキュメント

modules/
├── amplifier_module_provider_claude_cli/   # Claude CLI Provider モジュール
│   ├── __init__.py
│   ├── provider.py
│   └── mount.py
│
└── amplifier_module_tool_examples/         # 学習用ツールモジュール
    ├── __init__.py
    ├── tools.py
    └── mount.py
```

---

## Amplifier Core モジュール規約

### モジュール命名規則

モジュールは `amplifier_module_{module_id}` の形式で命名します：

```
ディレクトリ名                              module-id
─────────────────────────────────────────────────────────
amplifier_module_provider_claude_cli   →   provider-claude-cli
amplifier_module_tool_examples         →   tool-examples
amplifier_module_loop_basic            →   loop-basic
```

### mount() 関数

すべてのモジュールは `mount()` 関数をエクスポートする必要があります：

```python
async def mount(
    coordinator: ModuleCoordinator,
    config: dict[str, Any]
) -> Callable[[], Awaitable[None]] | None:
    """
    モジュールを Coordinator にマウント。

    Args:
        coordinator: ModuleCoordinator インスタンス
        config: モジュール設定（mount plan から渡される）

    Returns:
        クリーンアップ関数（または None）
    """
    # 1. インスタンス作成
    instance = MyModule(config)

    # 2. Coordinator にマウント
    await coordinator.mount("providers", instance, name="my-module")

    # 3. クリーンアップ関数を返す
    async def cleanup():
        await instance.close()
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

### 本番での Entry Point 登録

`pyproject.toml`:

```toml
[project.entry-points."amplifier.modules"]
provider-claude-cli = "amplifier_module_provider_claude_cli:mount"
tool-examples = "amplifier_module_tool_examples:mount"
```

---

## 提供モジュール

### provider-claude-cli

**ローカルで認証済みの Claude Code CLI を Provider として使用**

APIキー不要で実際の Claude とやり取りできます。

| 設定 | 説明 | デフォルト |
|------|------|----------|
| `mode` | `"passthrough"` or `"controlled"` | `"controlled"` |
| `model` | モデル名（sonnet, opus など） | なし |
| `timeout` | タイムアウト秒数 | 300 |

**モード比較:**

| モード | ツール実行 | 用途 |
|--------|-----------|------|
| `passthrough` | CLI側 | CLIに全て任せる |
| `controlled` | Amplifier側 | ツール実行を完全制御（推奨） |

**controlled モードのアーキテクチャ:**

```
                      ┌─────────────────────┐
  ChatRequest    ──▶  │ claude -p "..."     │
  + ToolSpec          │ --tools ""          │  ← ツール無効化
                      │ --output-format json│
                      └─────────────────────┘
                               │
                               ▼
                      ┌─────────────────────┐
  ChatResponse   ◀──  │ finish_reason:      │
  (tool_use)          │   "tool_use"        │
                      │ content:            │
                      │   [ToolCallBlock]   │
                      └─────────────────────┘
                               │
                               ▼
                      ┌─────────────────────┐
  Tool.execute() ──▶  │ Amplifier側で実行   │  ← 完全制御
                      └─────────────────────┘
```

### tool-examples

**学習用ツール実装**

| ツール | 説明 |
|--------|------|
| `calculator` | 四則演算 |
| `weather` | 天気情報（モック） |
| `file_reader` | ファイル読み取り（仮想FS） |
| `multi_step` | 状態管理 |

---

## 学習ステップ

### Step 1: 基本構造の理解
**目標**: AmplifierSession, ModuleCoordinator, HookRegistryの基本的な動作を理解する

**学ぶこと**:
- セッションの作成とライフサイクル
- Coordinatorへのモジュールのマウント
- 基本的なイベントの発行と受信

**ディレクトリ**: `step1-basics/`

```bash
cd examples/step1-basics
python app.py
```

---

### Step 2: Providerの実装
**目標**: LLMプロバイダーの仕組みを理解し、モックプロバイダーを実装する

**学ぶこと**:
- Providerプロトコルの理解
- ChatRequest / ChatResponse の構造
- プロバイダーのマウント方法

**ディレクトリ**: `step2-provider/`

```bash
cd examples/step2-provider
python app.py
```

---

### Step 3: Toolの実装
**目標**: エージェントが使用できるツールを実装し、Claude CLI と統合する

**学ぶこと**:
- Toolプロトコルの理解
- ToolCall / ToolResult の構造
- Amplifier Core モジュール規約
- Claude CLI Provider との統合

**ディレクトリ**: `step3-tool/`

```bash
cd examples/step3-tool
python app.py              # 基本デモ
python app.py --with-llm   # Claude CLI 統合デモ（APIキー不要）
```

---

### Step 4: Orchestratorの実装
**目標**: エージェントループを制御するOrchestratorを実装する

**学ぶこと**:
- Orchestratorプロトコルの理解
- ContextManagerプロトコルの理解
- プロンプト実行フロー
- プロバイダーとツールの連携
- イベントの発行とフック処理

**ディレクトリ**: `step4-orchestrator/`

```bash
cd examples/step4-orchestrator
python app.py              # 基本デモ（モック Provider）
python app.py --with-llm   # Claude CLI 統合デモ（APIキー不要）
```

**実装内容**:
- `BasicLoopOrchestrator`: エージェントループを制御
- `SimpleContextManager`: 会話履歴を管理

**エージェントループのフロー**:
```
orchestrator.execute(prompt)
    │
    ├──▶ context.add_message(user_message)
    │
    └──▶ Main Loop (max_turns)
          │
          ├──▶ context.get_messages()
          ├──▶ provider.complete(ChatRequest)
          ├──▶ context.add_message(assistant_response)
          │
          └──▶ [ツールコールがあれば]
                ├──▶ tool.execute(arguments)
                └──▶ context.add_message(tool_result)
```

---

### Step 5: ContextManagerの詳細実装
**目標**: 高度なコンテキスト管理（トークン計算、要約コンパクション）を実装する

**学ぶこと**:
- トークン計算の仕組み（TokenCounter）
- トークン予算管理（TokenBudget）
- 要約コンパクションの実装
- 重要度ベースのメッセージ保持

**ディレクトリ**: `step5-context/`

```bash
cd examples/step5-context
python app.py              # 基本デモ
python app.py --with-llm   # Claude CLI 統合デモ（要約コンパクション使用）
```

**実装内容**:
- `TokenCounter`: トークン数の計算ユーティリティ
- `TokenBudget`: トークン予算の管理
- `AdvancedContextManager`: 高度なコンテキスト管理

**Step 4 からの進化**:

| 項目 | Step 4 (SimpleContextManager) | Step 5 (AdvancedContextManager) |
|------|-------------------------------|--------------------------------|
| トークン計算 | メッセージ数のみ | 実際のトークン数を計算 |
| コンパクション | 古いメッセージを削除 | 要約を生成して保持 |
| 重要度判定 | なし | ツール結果・エラーを優先保持 |
| システムプロンプト | 別管理 | 統合管理 + 保護 |

**コンパクション戦略の比較**:

```
単純削除（Step 4）:
  Before: [sys, u1, a1, u2, a2, u3, a3, u4, a4, u5, a5]
  After:  [sys, u4, a4, u5, a5]  ← 古いメッセージを削除

要約コンパクション（Step 5）:
  Before: [sys, u1, a1, u2, a2, u3, a3, u4, a4, u5, a5]
  After:  [sys, summary, u4, a4, u5, a5]  ← 要約で文脈を保持

重要度ベース + 要約（推奨）:
  Before: [sys, u1, a1(tool), u2, a2(error), u3, a3, u4, a4, u5, a5]
  After:  [sys, summary, a1(tool), a2(error), u4, a4, u5, a5]
          ↑ 重要なメッセージを保持
```

---

### Step 6: Hookシステムの活用（予定）
**目標**: イベントシステムを使った拡張性を理解する

---

### Step 7: 統合 - 完全なエージェント（予定）
**目標**: 全コンポーネントを統合して動作するエージェントを構築する

---

## 完全な設定例

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

---

## コンポーネント関係図

```
実行フロー:
session.execute(prompt)
    │
    ▼
orchestrator.execute()
    │
    ├──▶ hooks.emit("prompt:submit")
    │
    ├──▶ context.get_messages()
    │
    ├──▶ provider.complete(request)
    │       │
    │       ├──▶ hooks.emit("provider:request")
    │       └──▶ hooks.emit("provider:response")
    │
    ├──▶ [ツールコールがあれば]
    │       │
    │       ├──▶ hooks.emit("tool:pre")
    │       ├──▶ tool.execute(input)
    │       └──▶ hooks.emit("tool:post")
    │
    └──▶ hooks.emit("prompt:complete")
```

---

## 必須 vs オプション

| コンポーネント | 必須? | 説明 |
|--------------|-------|------|
| Orchestrator | 必須 | 実行戦略を決定 |
| ContextManager | 必須 | 会話履歴を保持 |
| Provider | 必須 | LLM呼び出しに必要 |
| Tool | オプション | エージェント機能を拡張 |
| Hook | オプション | 観測性・拡張性を提供 |

---

## クイックスタート

### 1. 基本を理解する

```bash
cd examples/step1-basics && python app.py
```

### 2. Provider を理解する

```bash
cd examples/step2-provider && python app.py
```

### 3. Tool と Claude CLI を体験する

```bash
cd examples/step3-tool && python app.py --with-llm
```

### 4. Orchestrator でエージェントループを実装する

```bash
cd examples/step4-orchestrator && python app.py --with-llm
```

### 5. ContextManager で高度なコンテキスト管理を実装する

```bash
cd examples/step5-context && python app.py --with-llm
```

---

## 参考ドキュメント

- `/docs/code-reading/00-getting-started.md` - コードリーディングガイド
- `/amplifier_core/interfaces.py` - 全プロトコル定義
- `/amplifier_core/models.py` - データ構造
- `/amplifier_core/events.py` - 標準イベント一覧
- `/amplifier_core/loader.py` - モジュールローダー
