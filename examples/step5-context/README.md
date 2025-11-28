# Step 5: ContextManager の詳細実装

このステップでは、高度なコンテキスト管理を学びます。

## 学習目標

- **トークン計算**の仕組みを理解する
- **要約コンパクション**を実装する
- **重要度ベースのメッセージ保持**を理解する
- コンテキスト管理の**ベストプラクティス**を習得する

## ファイル構成

```
examples/step5-context/
├── README.md              # このファイル
├── app.py                 # デモアプリケーション
├── context.py             # AdvancedContextManager 実装
└── tokenizer.py           # トークン計算ユーティリティ

modules/
├── amplifier_module_provider_claude_cli/   # Claude CLI Provider
└── amplifier_module_tool_examples/         # 学習用ツール
```

## 実行方法

```bash
cd examples/step5-context

# 基本デモ（トークン計算とコンパクションの動作確認）
python app.py

# Claude CLI との統合デモ（要約コンパクションを使用）
python app.py --with-llm
```

---

## Step 4 からの進化

Step 4 の `SimpleContextManager` は以下の制限がありました：

| 項目 | Step 4 (SimpleContextManager) | Step 5 (AdvancedContextManager) |
|------|-------------------------------|--------------------------------|
| トークン計算 | メッセージ数のみ | 実際のトークン数を計算 |
| コンパクション | 古いメッセージを削除 | 要約を生成して保持 |
| 重要度判定 | なし | ツール結果・エラーを優先保持 |
| システムプロンプト | 別管理 | 統合管理 + 保護 |

---

## AdvancedContextManager の特徴

### 1. トークン計算

```python
class TokenCounter:
    """トークン数を計算するユーティリティ"""

    def count(self, text: str) -> int:
        """テキストのトークン数を計算"""
        # 方法1: tiktoken ライブラリを使用（推奨）
        # 方法2: 4文字 ≈ 1トークンの概算
        ...

    def count_message(self, message: dict) -> int:
        """メッセージのトークン数を計算"""
        ...
```

### 2. 要約コンパクション

```python
async def compact(self) -> None:
    """
    コンテキストを圧縮。

    戦略:
    1. システムメッセージを保持
    2. 重要なメッセージ（ツール結果、エラー）を保持
    3. 古い会話を LLM で要約
    4. 最新のメッセージを保持
    """
    # LLM を使って要約を生成
    summary = await self._summarize_old_messages(old_messages)

    # 新しいメッセージリストを構築
    self._messages = (
        system_messages +
        [summary_message] +
        important_messages +
        recent_messages
    )
```

### 3. 重要度ベースの保持

```python
def _is_important(self, message: dict) -> bool:
    """メッセージの重要度を判定"""
    role = message.get("role")

    # ツール結果は重要
    if role == "tool":
        return True

    # エラーを含むメッセージは重要
    content = message.get("content", "")
    if "error" in content.lower():
        return True

    # メタデータで重要とマークされたメッセージ
    metadata = message.get("metadata", {})
    if metadata.get("important"):
        return True

    return False
```

---

## ContextManager プロトコル（復習）

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

## AdvancedContextManager の設定

| 設定 | 説明 | デフォルト |
|------|------|----------|
| `max_tokens` | 最大トークン数 | 8000 |
| `compact_threshold` | コンパクション開始閾値（トークン） | 6000 |
| `keep_recent` | 常に保持する最新メッセージ数 | 10 |
| `keep_system` | システムメッセージを保持 | True |
| `use_summary` | 要約コンパクションを使用 | True |
| `summary_provider` | 要約に使用するプロバイダー名 | None（最初のプロバイダー） |

---

## コンパクション戦略

### 戦略1: 単純削除（Step 4）

```
Before: [sys, u1, a1, u2, a2, u3, a3, u4, a4, u5, a5]
After:  [sys, u4, a4, u5, a5]  ← 古いメッセージを削除
```

**メリット**: シンプル、高速
**デメリット**: 会話の文脈が失われる

### 戦略2: 要約コンパクション（Step 5）

```
Before: [sys, u1, a1, u2, a2, u3, a3, u4, a4, u5, a5]
After:  [sys, summary, u4, a4, u5, a5]  ← 要約で文脈を保持
```

**メリット**: 会話の文脈を維持
**デメリット**: LLM 呼び出しが必要、コスト増

### 戦略3: 重要度ベース + 要約（推奨）

```
Before: [sys, u1, a1(tool), u2, a2(error), u3, a3, u4, a4, u5, a5]
After:  [sys, summary, a1(tool), a2(error), u4, a4, u5, a5]
        ↑ 重要なメッセージを保持
```

**メリット**: 重要な情報を失わない、文脈も維持
**デメリット**: 実装が複雑

---

## トークン計算の方法

### 方法1: tiktoken ライブラリ（推奨）

```python
import tiktoken

encoder = tiktoken.encoding_for_model("gpt-4")
token_count = len(encoder.encode(text))
```

**メリット**: 正確
**デメリット**: 外部依存

### 方法2: 概算（4文字 ≈ 1トークン）

```python
token_count = len(text) // 4
```

**メリット**: シンプル、依存なし
**デメリット**: 概算のため誤差あり

### 方法3: 正規表現ベース

```python
import re

# 単語とスペースで分割
tokens = re.findall(r'\w+|[^\w\s]|\s+', text)
token_count = len(tokens)
```

**メリット**: 依存なし、概算より正確
**デメリット**: 言語による差異

---

## 使用例

### 基本的な使用

```python
from context import AdvancedContextManager

# 設定
config = {
    "max_tokens": 8000,
    "compact_threshold": 6000,
    "keep_recent": 10,
    "use_summary": True,
}

context = AdvancedContextManager(config)

# メッセージを追加
await context.add_message({"role": "user", "content": "Hello!"})
await context.add_message({"role": "assistant", "content": "Hi there!"})

# トークン数を確認
print(f"Total tokens: {context.total_tokens}")

# コンパクションが必要か確認
if await context.should_compact():
    await context.compact()
```

### Orchestrator との統合

```python
from amplifier_core import AmplifierSession
from amplifier_core.loader import ModuleLoader
from context import AdvancedContextManager
from examples.step4_orchestrator.orchestrator import BasicLoopOrchestrator

config = {
    "session": {
        "orchestrator": "mock-orchestrator",
        "context": "mock-context",
    }
}

session = AmplifierSession(config)
loader = ModuleLoader(coordinator=session.coordinator)

# Provider と Tool をロード
await loader.load("provider-claude-cli", config={"mode": "controlled"})
await loader.load("tool-examples", config={"tools": ["calculator", "weather"]})

# AdvancedContextManager を使用
context = AdvancedContextManager({
    "max_tokens": 8000,
    "use_summary": True,
})

await session.coordinator.mount("context", context)

# Orchestrator 実行
orchestrator = BasicLoopOrchestrator({"max_turns": 10})
result = await orchestrator.execute(
    prompt="What is 123 * 456?",
    context=context,
    providers=session.coordinator.get("providers"),
    tools=session.coordinator.get("tools"),
    hooks=session.coordinator.hooks,
)
```

---

## 発行されるイベント

AdvancedContextManager は以下のイベントを発行します（Orchestrator 経由）:

| イベント | タイミング | データ |
|---------|----------|--------|
| `context:pre_compact` | コンパクション前 | `{message_count, token_count, reason}` |
| `context:post_compact` | コンパクション後 | `{old_count, new_count, old_tokens, new_tokens, summary_used}` |
| `context:token_warning` | トークン警告 | `{current_tokens, max_tokens, percentage}` |

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
            }
        },
        "context": {
            "module": "context-advanced",
            "config": {
                "max_tokens": 12000,
                "compact_threshold": 9000,
                "keep_recent": 15,
                "keep_system": True,
                "use_summary": True,
                "summary_provider": "claude-cli"
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

1. **トークン計算**: メッセージ数ではなくトークン数で制限を管理
2. **要約コンパクション**: 古い会話を要約して文脈を保持
3. **重要度ベース保持**: ツール結果やエラーは優先的に保持
4. **システムメッセージ保護**: 常にシステムプロンプトを維持

## 次のステップ

- **Step 6**: Hook システムの活用（観測性、拡張性）
- **Step 7**: 統合 - 完全なエージェント
