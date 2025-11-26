# Example 02: シンプルなProvider

Providerを実装して、LLM風の応答を生成するサンプルです。

## 学べること

1. **Providerの実装**
   - `Provider` プロトコルの実装方法
   - `ChatRequest` を受け取り `ChatResponse` を返す流れ
   - `ToolCall` のパース

2. **Orchestratorの拡張**
   - Providerを呼び出すロジック
   - ChatRequest の構築
   - ChatResponse の処理

3. **メッセージフロー**
   - ユーザープロンプト → Context → ChatRequest
   - Provider → ChatResponse
   - ChatResponse → ユーザーレスポンス

## ファイル構成

```
02-simple-echo/
├── README.md              # このファイル
├── app_standalone.py      # スタンドアロン実行スクリプト
├── echo_provider.py       # Echoプロバイダー実装
└── simple_orchestrator.py # Providerを使うOrchestrator
```

## 実行方法

```bash
cd examples/02-simple-echo
python3 app_standalone.py
```

## 期待される出力

```
============================================================
Example 02: シンプルなProvider
============================================================

[1/3] セッション作成完了
[2/3] Providerをマウント: echo-provider
[2/3] Orchestratorをマウント: simple-orchestrator
[2/3] ContextManagerをマウント
[2/3] 初期化完了

[3/3] プロンプト実行: "What is 2 + 2?"

[Orchestrator] Context messages: 1
[Orchestrator] Building ChatRequest...
[Orchestrator] Calling provider: echo-provider
[EchoProvider] Received request with 1 messages
[EchoProvider] Last message: What is 2 + 2?
[Orchestrator] Provider response received

------------------------------------------------------------
レスポンス:
  [Echo] You said: What is 2 + 2?
  I'm a simple echo provider, so I'll just repeat what you said.
------------------------------------------------------------
```

## コードの詳細解説

### EchoProvider の実装

`EchoProvider` は最もシンプルなProvider実装です：

```python
class EchoProvider:
    @property
    def name(self) -> str:
        return "echo-provider"

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        # 最後のメッセージを取得
        last_message = request.messages[-1] if request.messages else None
        last_content = last_message.content[0].text if last_message else "nothing"

        # エコーレスポンスを構築
        response_text = f"[Echo] You said: {last_content}\\n"
        response_text += "I'm a simple echo provider, so I'll just repeat what you said."

        return ChatResponse(
            content=[TextBlock(type="text", text=response_text)],
            usage=Usage(input_tokens=10, output_tokens=20),
            stop_reason="end_turn"
        )

    def parse_tool_calls(self, response: ChatResponse) -> list[ToolCall]:
        # このシンプルな実装ではツールコールをサポートしない
        return []
```

### SimpleOrchestrator の実装

`SimpleOrchestrator` はProviderを1回だけ呼び出す最もシンプルなループです：

```python
class SimpleOrchestrator:
    async def execute(
        self,
        prompt: str,
        context: ContextManager,
        providers: dict[str, Provider],
        tools: dict[str, Tool],
        hooks: Any,
    ) -> str:
        # 1. プロンプトをcontextに追加
        await context.add_message({
            "role": "user",
            "content": prompt
        })

        # 2. Contextからメッセージを取得
        messages = await context.get_messages()

        # 3. ChatRequestを構築
        chat_request = self._build_chat_request(messages)

        # 4. Providerを呼び出し
        provider = list(providers.values())[0]  # 最初のproviderを使用
        response = await provider.complete(chat_request)

        # 5. レスポンステキストを抽出
        response_text = self._extract_text(response)

        # 6. レスポンスをcontextに追加
        await context.add_message({
            "role": "assistant",
            "content": response_text
        })

        return response_text
```

## 次のステップ

→ [Example 03: ツールの追加](../03-with-tools/) で、Providerがツールを呼び出せるようにします。

## 学習ポイント

### Provider プロトコル

Providerは3つのメソッドを実装する必要があります：
- `name`: プロバイダー名
- `complete()`: ChatRequest → ChatResponse
- `parse_tool_calls()`: ChatResponse → list[ToolCall]

### ChatRequest / ChatResponse

- `ChatRequest`: 標準化されたリクエスト形式
  - `messages`: 会話履歴
  - `tools`: 利用可能なツール
  - `max_tokens`, `temperature`: 生成パラメータ

- `ChatResponse`: 標準化されたレスポンス形式
  - `content`: TextBlock, ToolCallBlock など
  - `usage`: トークン使用量
  - `stop_reason`: 停止理由

### Orchestrator の責務

- Contextからメッセージを読み取る
- ChatRequestを構築する
- Providerを呼び出す
- レスポンスを処理する
- Contextにレスポンスを保存する
