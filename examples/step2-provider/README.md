# Step 2: Providerの実装

このステップでは、LLMプロバイダーの仕組みを深く理解し、モックプロバイダーを実装します。

## 学習目標

- **Providerプロトコル**の3つのメソッドを理解する
- **ChatRequest** / **ChatResponse** の構造を理解する
- 複数のプロバイダーをマウントして切り替える方法を学ぶ

## ファイル構成

```
step2-provider/
├── README.md           # このファイル
├── mock_provider.py    # 様々なモックプロバイダーの実装
└── app.py              # プロバイダーのデモアプリケーション
```

## 実行方法

```bash
cd examples/step2-provider
python app.py
```

## Providerプロトコルの概要

```python
from typing import Protocol

class Provider(Protocol):
    @property
    def name(self) -> str:
        """プロバイダー名"""
        ...

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        """チャット補完を実行"""
        ...

    def parse_tool_calls(self, response: ChatResponse) -> list[ToolCall]:
        """レスポンスからツールコールを解析"""
        ...
```

## ChatRequest の構造

```python
class ChatRequest(BaseModel):
    messages: list[Message]                    # 会話履歴
    tools: list[ToolSpec] | None = None        # 利用可能なツール
    response_format: ResponseFormat | None     # 応答フォーマット
    temperature: float | None = None           # 温度パラメータ
    max_output_tokens: int | None = None       # 最大出力トークン
    stream: bool | None = False                # ストリーミング
    metadata: dict[str, Any] | None = None     # 追加メタデータ
```

### Message の構造

```python
class Message(BaseModel):
    role: Literal["system", "developer", "user", "assistant", "function", "tool"]
    content: str | list[ContentBlock]
    name: str | None = None
    tool_call_id: str | None = None
```

### ContentBlock の種類

| タイプ | 説明 |
|--------|------|
| `TextBlock` | 通常のテキスト |
| `ThinkingBlock` | モデルの思考過程 |
| `ToolCallBlock` | ツール呼び出し |
| `ToolResultBlock` | ツール実行結果 |
| `ImageBlock` | 画像コンテンツ |

## ChatResponse の構造

```python
class ChatResponse(BaseModel):
    content: list[ContentBlock]               # 応答コンテンツ
    tool_calls: list[ToolCall] | None = None  # ツールコール（もしあれば）
    usage: Usage | None = None                # トークン使用量
    finish_reason: str | None = None          # 終了理由
    metadata: dict[str, Any] | None = None    # 追加メタデータ
```

### Usage の構造

```python
class Usage(BaseModel):
    input_tokens: int    # 入力トークン数
    output_tokens: int   # 出力トークン数
    total_tokens: int    # 合計トークン数
```

## コード解説

### 1. 基本的なプロバイダーの実装

```python
class EchoProvider:
    """ユーザーの入力をエコーバックする最もシンプルなプロバイダー"""

    @property
    def name(self) -> str:
        return "echo"

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        # 最後のユーザーメッセージを取得
        user_message = self._extract_last_user_message(request)

        return ChatResponse(
            content=[TextBlock(type="text", text=f"Echo: {user_message}")],
            finish_reason="stop",
        )

    def parse_tool_calls(self, response: ChatResponse) -> list[ToolCall]:
        return response.tool_calls or []
```

### 2. ツールコールをシミュレートするプロバイダー

```python
class ToolCallingProvider:
    """特定のキーワードでツールコールを生成するプロバイダー"""

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        if "calculate" in user_message.lower():
            return ChatResponse(
                content=[ToolCallBlock(
                    type="tool_call",
                    id="call_001",
                    name="calculator",
                    input={"expression": "1 + 1"}
                )],
                tool_calls=[ToolCall(
                    id="call_001",
                    name="calculator",
                    arguments={"expression": "1 + 1"}
                )],
                finish_reason="tool_use",
            )
```

### 3. 複数プロバイダーの切り替え

```python
# 複数のプロバイダーをマウント
await coordinator.mount("providers", echo_provider, name="echo")
await coordinator.mount("providers", tool_provider, name="tool-caller")

# 名前でプロバイダーを取得
providers = coordinator.get("providers")
provider = providers["echo"]  # または providers["tool-caller"]
```

## 重要な概念

### プロバイダーの責務

1. **ChatRequest の受信** - 標準化されたリクエストを受け取る
2. **LLM への変換** - 各LLMのAPIフォーマットに変換（実際のプロバイダーの場合）
3. **ChatResponse の返却** - 標準化されたレスポンスを返す
4. **ツールコールの解析** - レスポンスからツールコールを抽出

### finish_reason の値

| 値 | 説明 |
|----|------|
| `stop` | 正常終了 |
| `tool_use` | ツールコールが必要 |
| `length` | 最大トークン数に達した |
| `content_filter` | コンテンツフィルターで停止 |

## 次のステップ

Step 3では、プロバイダーが呼び出すツールを実装します。
