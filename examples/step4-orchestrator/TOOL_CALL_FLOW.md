# Tool Call Flow - ツールコールの発火順序と情報の受け渡し

このドキュメントでは、Amplifier Core のオーケストレーターにおけるツールコールの仕組みを詳しく解説します。

## 概要図

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Agent Loop (Orchestrator)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐              │
│   │  User   │───▶│ Context  │───▶│ Provider │───▶│   LLM   │              │
│   │ Prompt  │    │ Manager  │    │(Claude)  │    │         │              │
│   └─────────┘    └──────────┘    └──────────┘    └────┬────┘              │
│                                                       │                    │
│                                                       ▼                    │
│                                              ┌────────────────┐            │
│                                              │  ChatResponse  │            │
│                                              │ ┌────────────┐ │            │
│                                              │ │ TextBlock  │ │            │
│                                              │ ├────────────┤ │            │
│                                              │ │ToolCallBlk │ │◀── ツールコール要求 │
│                                              │ └────────────┘ │            │
│                                              └───────┬────────┘            │
│                                                      │                     │
│                           parse_tool_calls()         │                     │
│                                  ▼                   │                     │
│                         ┌────────────────┐           │                     │
│                         │ List[ToolCall] │           │                     │
│                         │ ┌────────────┐ │           │                     │
│                         │ │tool: "weather"│          │                     │
│                         │ │arguments: {...}│         │                     │
│                         │ │id: "tc_1"   │ │          │                     │
│                         │ └────────────┘ │           │                     │
│                         └───────┬────────┘           │                     │
│                                 │                    │                     │
│                                 ▼                    │                     │
│                         ┌────────────────┐           │                     │
│                         │  Tool Module   │           │                     │
│                         │  .execute()    │           │                     │
│                         └───────┬────────┘           │                     │
│                                 │                    │                     │
│                                 ▼                    │                     │
│                         ┌────────────────┐           │                     │
│                         │  ToolResult    │           │                     │
│                         │ success: true  │           │                     │
│                         │ output: {...}  │           │                     │
│                         └───────┬────────┘           │                     │
│                                 │                    │                     │
│                                 ▼                    │                     │
│                         ┌────────────────┐           │                     │
│                         │    Context     │───────────┘                     │
│                         │  (tool result  │     次のターンでLLMに送信       │
│                         │   を追加)      │                                 │
│                         └────────────────┘                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 詳細な処理フロー

### Turn 1: ユーザープロンプトからツールコールまで

```
時間軸 ─────────────────────────────────────────────────────────────────▶

[Step 1]          [Step 2]           [Step 3]           [Step 4]
ユーザー入力       コンテキスト準備     LLM呼び出し          レスポンス解析
    │                 │                  │                   │
    ▼                 ▼                  ▼                   ▼
"What is the    Context に追加      Claude CLI 実行     ToolCallBlock
weather in      messages = [        response = {        を検出
Tokyo?"           {role: "user",      content: [
                   content: "..."}     TextBlock,        tool_calls = [
                 ]                     ToolCallBlock     {tool: "weather",
                                     ]                    args: {city:"Tokyo"}}
                                   }                    ]
```

### Step 1: ユーザー入力の受信

**場所**: `orchestrator.py:110-114`

```python
# ユーザーメッセージをコンテキストに追加
await context.add_message({
    "role": "user",
    "content": prompt,  # "What is the weather in Tokyo?"
})
```

**データ**:
```python
{
    "role": "user",
    "content": "What is the weather in Tokyo?"
}
```

---

### Step 2: ツール仕様の生成

**場所**: `orchestrator.py:127-128`

```python
# ツール仕様の生成
tool_specs = self._generate_tool_specs(tools)
```

登録されているツールから、LLMに渡すツール定義を生成します。

**データ** (`ToolSpec`):
```python
[
    ToolSpec(
        name="weather",
        description="Get weather information for a city",
        parameters={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name"
                }
            },
            "required": ["city"]
        }
    )
]
```

---

### Step 3: Provider (LLM) 呼び出し

**場所**: `orchestrator.py:130-136` → `provider.py:136-143`

```python
# orchestrator.py
response = await self._call_provider(provider, messages, tool_specs, hooks)

# provider.py (_complete_controlled)
prompt = self._build_prompt_with_tools(request)  # ツール定義をプロンプトに含める
system_prompt = self._build_system_prompt_for_tools(request)  # ツール呼び出し形式を指示
cmd = self._build_command(prompt, system_prompt, tools_disabled=True)
return await self._execute_cli(cmd, has_tools=True)
```

**LLMに送信されるプロンプト**:
```
Available tools:
- weather: Get weather information for a city
    - city* (string): City name

What is the weather in Tokyo?
```

**LLMに送信されるシステムプロンプト**:
```
When you need to use a tool, respond with a JSON block in this exact format:
```tool_call
{
  "tool": "tool_name",
  "arguments": {
    "arg1": "value1"
  }
}
```
```

---

### Step 4: LLMレスポンスの解析

**場所**: `provider.py:325-393`

LLMは以下のような形式で応答します：

```
I'll check the weather in Tokyo for you.

```tool_call
{
  "tool": "weather",
  "arguments": {
    "city": "Tokyo"
  }
}
```
```

この応答を `_parse_response()` が解析し、`ChatResponse` を生成：

```python
ChatResponse(
    content=[
        TextBlock(type="text", text="I'll check the weather in Tokyo for you."),
        ToolCallBlock(
            type="tool_call",
            id="tc_1",
            name="weather",
            input={"city": "Tokyo"}
        )
    ],
    finish_reason="tool_use"
)
```

---

### Step 5: ツールコールの抽出

**場所**: `orchestrator.py:144-145`

```python
tool_calls = provider.parse_tool_calls(response)
```

**parse_tool_calls の実装** (`provider.py:204-226`):
```python
def parse_tool_calls(self, response: ChatResponse) -> list[ModelToolCall]:
    tool_calls = []
    for block in response.content:
        if isinstance(block, ToolCallBlock):
            tool_calls.append(
                ModelToolCall(
                    tool=block.name,      # "weather"
                    arguments=block.input, # {"city": "Tokyo"}
                    id=block.id,          # "tc_1"
                )
            )
    return tool_calls
```

**抽出されたデータ**:
```python
[
    ToolCall(
        tool="weather",
        arguments={"city": "Tokyo"},
        id="tc_1"
    )
]
```

---

### Step 6: ツールの実行

**場所**: `orchestrator.py:346-401`

```python
async def _execute_single_tool(self, tool_call, tools, context, hooks, coordinator):
    # 1. ツールを取得
    tool = tools.get(tool_call.tool)  # tools["weather"]

    # 2. ツールを実行
    result = await tool.execute(tool_call.arguments)
    # tool.execute({"city": "Tokyo"})
```

**ツール実行結果** (`ToolResult`):
```python
ToolResult(
    success=True,
    output={
        "city": "Tokyo",
        "temperature": 22,
        "condition": "Sunny",
        "humidity": 45
    }
)
```

---

### Step 7: 結果をコンテキストに追加

**場所**: `orchestrator.py:412-423`

```python
# 結果をコンテキストに追加
await context.add_message({
    "role": "tool",
    "tool_call_id": tool_call.id,  # "tc_1"
    "content": str(result.output),  # '{"city": "Tokyo", "temperature": 22, ...}'
})
```

---

### Turn 2: ツール結果から最終回答へ

```
時間軸 ─────────────────────────────────────────────────────────────────▶

[Step 8]          [Step 9]           [Step 10]
コンテキスト取得    LLM再呼び出し        最終回答
    │                 │                  │
    ▼                 ▼                  ▼
messages = [      response = {       "The weather in
  {user: "..."},    content: [       Tokyo is sunny
  {assistant: ...}, TextBlock(       with 22°C..."
  {tool: ...}         "The weather
]                     in Tokyo..."     ループ終了
                    ]
                  }
```

### Step 8: 次のターンのコンテキスト

**場所**: `orchestrator.py:124-125`

```python
messages = await self._prepare_context(context, hooks)
```

**コンテキストの内容**:
```python
[
    Message(role="user", content="What is the weather in Tokyo?"),
    Message(role="assistant", content="I'll check the weather... [Tool Call: weather({...})]"),
    Message(role="tool", content='{"city": "Tokyo", "temperature": 22, ...}')
]
```

---

### Step 9: LLM再呼び出し

LLMはツール結果を受け取り、最終回答を生成：

```python
ChatResponse(
    content=[
        TextBlock(
            type="text",
            text="The weather in Tokyo is currently sunny with a temperature of 22°C and 45% humidity."
        )
    ],
    finish_reason="stop"  # ツールコールなし
)
```

---

### Step 10: ループ終了

**場所**: `orchestrator.py:152-162`

```python
tool_calls = provider.parse_tool_calls(response)

if not tool_calls:
    # ツール呼び出しなし → 終了
    logger.info("No tool calls in response - LLM has finished reasoning")
    final_response = self._extract_text(response)
    return final_response
```

---

## データ型の流れ

```
┌────────────────┐
│   ToolSpec     │  ← ツールの定義（LLMに渡す）
│  - name        │
│  - description │
│  - parameters  │
└───────┬────────┘
        │
        ▼  LLMがツールを使うと決定
┌────────────────┐
│ ToolCallBlock  │  ← LLMレスポンス内のツールコール情報
│  - id          │
│  - name        │
│  - input       │
└───────┬────────┘
        │
        ▼  parse_tool_calls() で変換
┌────────────────┐
│   ToolCall     │  ← オーケストレーターが扱う形式
│  - tool        │
│  - arguments   │
│  - id          │
└───────┬────────┘
        │
        ▼  tool.execute() を呼び出し
┌────────────────┐
│  ToolResult    │  ← ツール実行結果
│  - success     │
│  - output      │
│  - error       │
└────────────────┘
```

---

## ログ出力例

実際の実行時のログ出力：

```
2025-11-28 01:34:33,300 - orchestrator - INFO - Starting agent loop with prompt: What is the weather in Tokyo?...
2025-11-28 01:34:33,300 - orchestrator - INFO - Using provider: claude-cli
2025-11-28 01:34:33,300 - orchestrator - INFO - Turn 1/5

# === Turn 1: LLMがツールコールを要求 ===
2025-11-28 01:34:37,076 - orchestrator - INFO - LLM response text: I'll check the weather in Tokyo for you.
2025-11-28 01:34:37,076 - orchestrator - INFO - LLM requested 1 tool call(s)
2025-11-28 01:34:37,076 - orchestrator - INFO - LLM requested tool call: weather
2025-11-28 01:34:37,076 - orchestrator - INFO -   Arguments: {'city': 'Tokyo'}
2025-11-28 01:34:37,076 - orchestrator - INFO -   Executing tool 'weather'...
2025-11-28 01:34:37,077 - orchestrator - INFO -   Tool result: success=True, output={'temperature': 22, 'condition': 'sunny'}

# === Turn 2: LLMが最終回答を生成 ===
2025-11-28 01:34:37,077 - orchestrator - INFO - Turn 2/5
2025-11-28 01:34:41,269 - orchestrator - INFO - LLM response text: The weather in Tokyo is currently sunny with a temperature of 22°C.
2025-11-28 01:34:41,269 - orchestrator - INFO - No tool calls in response - LLM has finished reasoning
```

---

## 関連ファイル

| ファイル | 役割 |
|---------|------|
| `orchestrator.py` | エージェントループ制御、ツール実行の調整 |
| `provider.py` | LLM (Claude CLI) との通信、レスポンス解析 |
| `context.py` | 会話履歴の管理 |
| ツールモジュール | 実際のツール実装（weather, calculator等） |

---

## まとめ

1. **Orchestrator** がループを制御し、Provider と Tool を連携
2. **Provider** が LLM にツール定義を渡し、レスポンスから `ToolCallBlock` を抽出
3. **parse_tool_calls()** が `ToolCallBlock` → `ToolCall` に変換
4. **Orchestrator** が `ToolCall` を受けてツールを実行
5. **ToolResult** がコンテキストに追加され、次のターンで LLM に送信
6. LLM がツールコールを返さなくなったらループ終了
