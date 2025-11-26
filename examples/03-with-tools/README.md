# Example 03: ツールの追加

ツールを実装して、エージェントが実際にアクションを実行できるようにするサンプルです。

## 学べること

1. **Toolの実装**
   - `Tool` プロトコルの実装方法
   - `execute()` メソッドで実際の処理を実行
   - `ToolResult` の返し方

2. **Orchestratorのツール実行ループ**
   - Provider がツールコールを返す
   - Orchestrator がツールを実行
   - 実行結果を Provider に渡す
   - 最終レスポンスまでループ

3. **ツールコールのフロー**
   - Provider → ToolCallBlock
   - Orchestrator → Tool.execute()
   - Tool → ToolResult
   - Orchestrator → ToolResultBlock → Provider

## ファイル構成

```
03-with-tools/
├── README.md          # このファイル
└── app_standalone.py  # スタンドアロン実行スクリプト
```

## 実行方法

```bash
cd examples/03-with-tools
python3 app_standalone.py
```

### 🔍 実行フローを可視化（トレース版）

イベントやコンポーネントの発火を詳細に表示：

```bash
python3 app_with_trace.py
```

トレース版では以下が可視化されます：
- コンポーネントの呼び出し階層
- イベント発火タイミング（`provider:pre`、`tool:pre` など）
- ツール実行フロー
- ターン単位の処理

詳細は [../TRACE_EXAMPLES.md](../TRACE_EXAMPLES.md) を参照。

## 期待される出力

```
============================================================
Example 03: ツールの追加
============================================================

[Session] Created session
[Session] Mounted 2 tools: calculator, read_file
[Session] Mounted provider: smart-echo
[Session] Mounted orchestrator
[Session] Initialized

[Execute] Prompt: "Calculate 15 + 27"

[Turn 1]
[Orchestrator] Calling provider...
[SmartEchoProvider] Analyzing request...
[SmartEchoProvider] Detected calculation request
[SmartEchoProvider] Generating tool call: calculator
[Orchestrator] Provider returned 1 tool call(s)
[Orchestrator] Executing tool: calculator
[CalculatorTool] Executing: 15 + 27
[CalculatorTool] Result: 42

[Turn 2]
[Orchestrator] Calling provider with tool results...
[SmartEchoProvider] Received tool result: 42
[SmartEchoProvider] Generating final response
[Orchestrator] Provider returned final response

------------------------------------------------------------
レスポンス:
  The result of 15 + 27 is 42.
------------------------------------------------------------
```

## コードの詳細解説

### Tool の実装

**CalculatorTool:**
```python
class CalculatorTool:
    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Performs basic arithmetic operations"

    async def execute(self, input: dict) -> ToolResult:
        operation = input.get("operation")  # "add", "subtract", etc.
        a = input.get("a")
        b = input.get("b")

        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        # ... その他の操作

        return ToolResult(
            success=True,
            output={"result": result}
        )
```

**ReadFileTool:**
```python
class ReadFileTool:
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Reads contents of a file"

    async def execute(self, input: dict) -> ToolResult:
        path = input.get("path")

        try:
            with open(path, "r") as f:
                content = f.read()

            return ToolResult(
                success=True,
                output={"content": content}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error={"message": str(e)}
            )
```

### SmartEchoProvider の実装

このProviderは、ユーザーの入力を分析してツールコールを生成します：

```python
class SmartEchoProvider:
    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        last_message = self._get_last_user_message(request)

        # ツール結果がある場合は最終レスポンスを生成
        if self._has_tool_results(request):
            return self._generate_final_response(request)

        # ツールコールが必要かチェック
        if "calculate" in last_message.lower() or "+" in last_message:
            return self._generate_tool_call(last_message)

        # 通常のレスポンス
        return self._generate_text_response(last_message)
```

### Orchestrator のツール実行ループ

```python
class LoopOrchestrator:
    async def execute(self, prompt, context, providers, tools, hooks) -> str:
        # 1. プロンプトを追加
        await context.add_message({"role": "user", "content": prompt})

        max_turns = 5
        for turn in range(1, max_turns + 1):
            print(f"\n[Turn {turn}]")

            # 2. Provider を呼び出し
            response = await provider.complete(chat_request)

            # 3. ツールコールがあるか確認
            tool_calls = provider.parse_tool_calls(response)

            if not tool_calls:
                # 最終レスポンス
                return self._extract_text(response)

            # 4. ツールを実行
            for tc in tool_calls:
                tool = tools[tc.tool_name]
                result = await tool.execute(tc.input)

                # 結果をcontextに追加
                await context.add_message({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result.output
                })

            # 5. 次のループへ（tool resultsを含むChatRequestを構築）

        return "Max turns exceeded"
```

## 次のステップ

→ [Example 04: フックシステム](../04-with-hooks/) で、イベント観測とロギングを追加します。

## 学習ポイント

### Tool プロトコル

Toolは3つのプロパティ/メソッドを実装：
- `name`: ツール名（識別子）
- `description`: ツールの説明
- `execute(input)`: 実際の処理を実行して ToolResult を返す

### ToolCall / ToolResult

- `ToolCall`: Providerが返すツール呼び出しリクエスト
  - `tool_name`: 呼び出すツール名
  - `input`: ツールへの入力パラメータ
  - `id`: ツールコールID（結果を紐付けるため）

- `ToolResult`: ツール実行結果
  - `success`: 成功/失敗
  - `output`: 成功時の出力
  - `error`: 失敗時のエラー情報

### ツール実行ループ

1. Provider を呼び出し
2. ToolCallBlock があるかチェック
3. あれば Tool.execute() を実行
4. 結果を Context に追加
5. もう一度 Provider を呼び出し（tool resultsを含む）
6. TextBlock が返るまで繰り返し
