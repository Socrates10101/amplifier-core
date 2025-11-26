"""
Example 03: ツールの追加（トレース版）

実行フローを詳細に可視化したバージョンです。
各コンポーネントの呼び出しとイベント発火を確認できます。
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any


# === トレースユーティリティ ===

class ExecutionTracer:
    """実行トレースを表示するユーティリティ"""

    def __init__(self):
        self.depth = 0
        self.step = 0

    def enter(self, component: str, method: str, details: str = ""):
        """コンポーネントに入る"""
        self.step += 1
        indent = "  " * self.depth
        arrow = "┌─" if self.depth == 0 else "├─"
        print(f"{arrow} [{self.step:02d}] {indent}{component}.{method}() {details}")
        self.depth += 1

    def exit(self, component: str, result: str = ""):
        """コンポーネントから出る"""
        self.depth -= 1
        indent = "  " * self.depth
        arrow = "└─" if self.depth == 0 else "├─"
        if result:
            print(f"{arrow} ✓ {indent}→ {result}")

    def log(self, message: str, level: str = "INFO"):
        """ログメッセージ"""
        indent = "  " * self.depth
        symbol = "│ " if self.depth > 0 else "  "
        print(f"{symbol} {indent}[{level}] {message}")

    def event(self, event_name: str, data: str = ""):
        """イベント発火"""
        indent = "  " * self.depth
        symbol = "│ " if self.depth > 0 else "  "
        print(f"{symbol} {indent}🔔 EVENT: {event_name} {data}")


tracer = ExecutionTracer()


# === Message Models ===

@dataclass
class TextBlock:
    type: str = "text"
    text: str = ""


@dataclass
class ToolCallBlock:
    type: str = "tool_call"
    id: str = ""
    tool_name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class ToolResultBlock:
    type: str = "tool_result"
    tool_call_id: str = ""
    content: Any = None


@dataclass
class Message:
    role: str
    content: list[Any]


@dataclass
class ChatRequest:
    messages: list[Message]
    tools: list[dict] = field(default_factory=list)


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class ChatResponse:
    content: list[Any]
    usage: Usage
    stop_reason: str


@dataclass
class ToolResult:
    success: bool
    output: dict = field(default_factory=dict)
    error: dict = field(default_factory=dict)


# === Tools ===

class CalculatorTool:
    """基本的な計算を実行するツール"""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Performs basic arithmetic operations"

    async def execute(self, input: dict) -> ToolResult:
        """計算を実行"""
        tracer.enter("CalculatorTool", "execute", f"input={input}")

        operation = input.get("operation")
        a = input.get("a", 0)
        b = input.get("b", 0)

        try:
            if operation == "add":
                result = a + b
            elif operation == "subtract":
                result = a - b
            elif operation == "multiply":
                result = a * b
            elif operation == "divide":
                if b == 0:
                    raise ValueError("Division by zero")
                result = a / b
            else:
                raise ValueError(f"Unknown operation: {operation}")

            tracer.log(f"Computed: {a} {operation} {b} = {result}")
            tracer.exit("CalculatorTool", f"result={result}")

            return ToolResult(success=True, output={"result": result})

        except Exception as e:
            tracer.log(f"Error: {e}", "ERROR")
            tracer.exit("CalculatorTool", f"error={e}")
            return ToolResult(success=False, error={"message": str(e)})


# === Smart Echo Provider ===

class SmartEchoProvider:
    """ツールコールを生成できる賢いEchoプロバイダー"""

    @property
    def name(self) -> str:
        return "smart-echo"

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        """リクエストを分析してツールコールまたはテキストレスポンスを返す"""
        tracer.enter("SmartEchoProvider", "complete", f"messages={len(request.messages)}")

        # 最後のユーザーメッセージを取得
        last_message = self._get_last_user_message(request)
        tracer.log(f"Last user message: {last_message[:50]}...")

        # ツール結果がある場合は最終レスポンスを生成
        if self._has_tool_results(request):
            tracer.log("Tool results found → generating final response")
            response = self._generate_final_response(request)
            tracer.exit("SmartEchoProvider", "TextBlock (final response)")
            return response

        # 計算リクエストを検出
        if self._is_calculation_request(last_message):
            tracer.log("Calculation detected → generating tool call")
            response = self._generate_calculation_tool_call(last_message)
            tracer.exit("SmartEchoProvider", "ToolCallBlock (calculator)")
            return response

        # 通常のテキストレスポンス
        tracer.log("No special pattern → text response")
        response = ChatResponse(
            content=[TextBlock(text=f"[Echo] You said: {last_message}")],
            usage=Usage(input_tokens=10, output_tokens=20),
            stop_reason="end_turn"
        )
        tracer.exit("SmartEchoProvider", "TextBlock (echo)")
        return response

    def _get_last_user_message(self, request: ChatRequest) -> str:
        for msg in reversed(request.messages):
            if msg.role == "user":
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        return block.text
        return ""

    def _has_tool_results(self, request: ChatRequest) -> bool:
        for msg in request.messages:
            for block in msg.content:
                if isinstance(block, ToolResultBlock):
                    return True
        return False

    def _is_calculation_request(self, text: str) -> bool:
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in ["calculate", "compute", "+"]) or \
               any(op in text for op in ["+", "-", "*", "/"])

    def _generate_calculation_tool_call(self, text: str) -> ChatResponse:
        if "+" in text:
            parts = text.split("+")
            if len(parts) == 2:
                try:
                    a = int("".join(filter(str.isdigit, parts[0])))
                    b = int("".join(filter(str.isdigit, parts[1])))

                    return ChatResponse(
                        content=[ToolCallBlock(
                            type="tool_call",
                            id=str(uuid.uuid4()),
                            tool_name="calculator",
                            input={"operation": "add", "a": a, "b": b}
                        )],
                        usage=Usage(input_tokens=10, output_tokens=20),
                        stop_reason="tool_use"
                    )
                except:
                    pass

        return ChatResponse(
            content=[TextBlock(text="I couldn't parse that calculation.")],
            usage=Usage(input_tokens=10, output_tokens=20),
            stop_reason="end_turn"
        )

    def _generate_final_response(self, request: ChatRequest) -> ChatResponse:
        tool_result = None
        for msg in reversed(request.messages):
            for block in msg.content:
                if isinstance(block, ToolResultBlock):
                    tool_result = block.content
                    break
            if tool_result:
                break

        if tool_result and "result" in tool_result:
            result_value = tool_result["result"]
            response_text = f"The result is {result_value}."
        else:
            response_text = f"Tool execution completed."

        return ChatResponse(
            content=[TextBlock(text=response_text)],
            usage=Usage(input_tokens=10, output_tokens=20),
            stop_reason="end_turn"
        )

    def parse_tool_calls(self, response: ChatResponse) -> list[dict]:
        """ChatResponseからツールコールを抽出"""
        tracer.enter("SmartEchoProvider", "parse_tool_calls", "")

        tool_calls = []
        for block in response.content:
            if isinstance(block, ToolCallBlock):
                tool_calls.append({
                    "id": block.id,
                    "tool_name": block.tool_name,
                    "input": block.input
                })

        tracer.exit("SmartEchoProvider", f"found {len(tool_calls)} tool call(s)")
        return tool_calls


# === Loop Orchestrator ===

class LoopOrchestrator:
    """ツール実行ループを持つOrchestrator"""

    async def execute(
        self,
        prompt: str,
        context,
        providers: dict,
        tools: dict,
        hooks: Any,
    ) -> str:
        """プロンプトを実行してレスポンスを返す"""
        tracer.enter("LoopOrchestrator", "execute", f'prompt="{prompt}"')

        # 1. プロンプトをcontextに追加
        tracer.log("Adding user prompt to context...")
        await context.add_message({
            "role": "user",
            "content": [TextBlock(text=prompt)]
        })

        # 2. ツール実行ループ
        provider = list(providers.values())[0]
        max_turns = 5
        tracer.log(f"Starting execution loop (max_turns={max_turns})...")

        for turn in range(1, max_turns + 1):
            print(f"\n{'═' * 60}")
            print(f"  TURN {turn}")
            print(f"{'═' * 60}\n")

            # 3. ChatRequestを構築
            messages = await context.get_messages()
            tracer.log(f"Building ChatRequest from {len(messages)} context messages...")
            chat_request = self._build_chat_request(messages)

            # 4. Providerを呼び出し
            tracer.log(f"Calling provider: {provider.name}")
            tracer.event("provider:pre", f"provider={provider.name}")
            response = await provider.complete(chat_request)
            tracer.event("provider:post", f"stop_reason={response.stop_reason}")

            # 5. ツールコールがあるかチェック
            tool_calls = provider.parse_tool_calls(response)

            if not tool_calls:
                # 最終レスポンス
                tracer.log("No tool calls → final response")
                response_text = self._extract_text(response)

                await context.add_message({
                    "role": "assistant",
                    "content": [TextBlock(text=response_text)]
                })

                tracer.exit("LoopOrchestrator", f"response='{response_text[:50]}...'")
                return response_text

            # 6. ツールを実行
            tracer.log(f"Found {len(tool_calls)} tool call(s) → executing...")

            for tc in tool_calls:
                tool_name = tc["tool_name"]
                tool = tools.get(tool_name)

                if not tool:
                    tracer.log(f"Tool not found: {tool_name}", "ERROR")
                    continue

                tracer.event("tool:pre", f"tool={tool_name}")
                result = await tool.execute(tc["input"])
                tracer.event("tool:post", f"success={result.success}")

                # ツール結果をcontextに追加
                await context.add_message({
                    "role": "assistant",
                    "content": [ToolCallBlock(
                        id=tc["id"],
                        tool_name=tool_name,
                        input=tc["input"]
                    )]
                })

                await context.add_message({
                    "role": "tool",
                    "content": [ToolResultBlock(
                        tool_call_id=tc["id"],
                        content=result.output if result.success else result.error
                    )]
                })

            tracer.log("Continuing to next turn...")

        tracer.exit("LoopOrchestrator", "max turns exceeded")
        return "Error: Max turns exceeded"

    def _build_chat_request(self, messages: list[dict]) -> ChatRequest:
        typed_messages = []
        for msg in messages:
            content = msg.get("content", [])
            if isinstance(content, list):
                typed_messages.append(Message(role=msg["role"], content=content))
            else:
                typed_messages.append(Message(role=msg["role"], content=[TextBlock(text=content)]))
        return ChatRequest(messages=typed_messages)

    def _extract_text(self, response: ChatResponse) -> str:
        texts = []
        for block in response.content:
            if isinstance(block, TextBlock):
                texts.append(block.text)
        return "\n".join(texts)


# === Context Manager ===

class SimpleContextManager:
    def __init__(self):
        self._messages: list[dict] = []

    async def add_message(self, message: dict) -> None:
        tracer.enter("ContextManager", "add_message", f"role={message.get('role')}")
        self._messages.append(message)
        tracer.exit("ContextManager", f"total messages: {len(self._messages)}")

    async def get_messages(self) -> list[dict]:
        return self._messages.copy()


# === Session ===

class SimpleSession:
    def __init__(self, config: dict):
        self.session_id = str(uuid.uuid4())
        self.config = config
        self._initialized = False
        self.orchestrator = None
        self.context = None
        self.providers: dict = {}
        self.tools: dict = {}

    async def mount_tool(self, tool):
        self.tools[tool.name] = tool

    async def mount_provider(self, provider):
        self.providers[provider.name] = provider

    async def mount_orchestrator(self, orchestrator):
        self.orchestrator = orchestrator

    async def mount_context(self, context):
        self.context = context

    async def initialize(self):
        tracer.enter("Session", "initialize", "")
        self._initialized = True
        tracer.event("session:start", f"session_id={self.session_id[:8]}")
        tracer.exit("Session", "initialized")

    async def execute(self, prompt: str) -> str:
        tracer.enter("Session", "execute", f'prompt="{prompt}"')

        response = await self.orchestrator.execute(
            prompt=prompt,
            context=self.context,
            providers=self.providers,
            tools=self.tools,
            hooks=None,
        )

        tracer.event("session:end", "")
        tracer.exit("Session", "completed")
        return response


# === Main ===

async def main():
    print("=" * 60)
    print("Example 03: ツールの追加（トレース版）")
    print("=" * 60)
    print()
    print("実行フローを詳細に表示します：")
    print("  ┌─ コンポーネント開始")
    print("  ├─ サブコンポーネント")
    print("  │  [INFO] ログメッセージ")
    print("  │  🔔 EVENT: イベント発火")
    print("  └─ ✓ 戻り値")
    print()
    print("=" * 60)
    print()

    # セッション作成
    config = {"session": {"orchestrator": "loop", "context": "simple"}}
    session = SimpleSession(config)

    # ツールをマウント
    calculator = CalculatorTool()
    await session.mount_tool(calculator)

    # Providerをマウント
    provider = SmartEchoProvider()
    await session.mount_provider(provider)

    # Orchestratorをマウント
    orchestrator = LoopOrchestrator()
    await session.mount_orchestrator(orchestrator)

    # Contextをマウント
    context = SimpleContextManager()
    await session.mount_context(context)

    await session.initialize()

    # プロンプトを実行
    print("\n" + "=" * 60)
    print("  EXECUTION START")
    print("=" * 60 + "\n")

    result = await session.execute("Calculate 15 + 27")

    print("\n" + "=" * 60)
    print("  FINAL RESULT")
    print("=" * 60)
    print(f"\n  {result}\n")

    print("=" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(main())
