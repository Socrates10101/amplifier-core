"""
Example 03: ツールの追加（スタンドアロン版）

ツールを実装して、エージェントが実際にアクションを実行できるようにします。
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any


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
    content: list[Any]  # TextBlock, ToolCallBlock, ToolResultBlock


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
    content: list[Any]  # TextBlock or ToolCallBlock
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
        return "Performs basic arithmetic operations (add, subtract, multiply, divide)"

    async def execute(self, input: dict) -> ToolResult:
        """計算を実行"""
        print(f"[CalculatorTool] Executing: {input}")

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

            print(f"[CalculatorTool] Result: {result}")

            return ToolResult(
                success=True,
                output={"result": result}
            )

        except Exception as e:
            print(f"[CalculatorTool] Error: {e}")
            return ToolResult(
                success=False,
                error={"message": str(e)}
            )


class ReadFileTool:
    """ファイルを読み込むツール"""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Reads the contents of a file"

    async def execute(self, input: dict) -> ToolResult:
        """ファイルを読み込む"""
        path = input.get("path")
        print(f"[ReadFileTool] Reading file: {path}")

        try:
            with open(path, "r") as f:
                content = f.read()

            print(f"[ReadFileTool] Read {len(content)} characters")

            return ToolResult(
                success=True,
                output={"content": content}
            )

        except Exception as e:
            print(f"[ReadFileTool] Error: {e}")
            return ToolResult(
                success=False,
                error={"message": str(e)}
            )


# === Smart Echo Provider ===

class SmartEchoProvider:
    """ツールコールを生成できる賢いEchoプロバイダー"""

    @property
    def name(self) -> str:
        return "smart-echo"

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        """リクエストを分析してツールコールまたはテキストレスポンスを返す"""
        print("[SmartEchoProvider] Analyzing request...")

        # 最後のユーザーメッセージを取得
        last_message = self._get_last_user_message(request)

        # ツール結果がある場合は最終レスポンスを生成
        if self._has_tool_results(request):
            print("[SmartEchoProvider] Received tool result")
            return self._generate_final_response(request)

        # 計算リクエストを検出
        if self._is_calculation_request(last_message):
            print("[SmartEchoProvider] Detected calculation request")
            return self._generate_calculation_tool_call(last_message)

        # ファイル読み込みリクエストを検出
        if "read file" in last_message.lower() or "read the file" in last_message.lower():
            print("[SmartEchoProvider] Detected file read request")
            return self._generate_read_file_tool_call(last_message)

        # 通常のテキストレスポンス
        print("[SmartEchoProvider] Generating text response")
        return ChatResponse(
            content=[TextBlock(text=f"[Echo] You said: {last_message}")],
            usage=Usage(input_tokens=10, output_tokens=20),
            stop_reason="end_turn"
        )

    def _get_last_user_message(self, request: ChatRequest) -> str:
        """最後のユーザーメッセージのテキストを取得"""
        for msg in reversed(request.messages):
            if msg.role == "user":
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        return block.text
        return ""

    def _has_tool_results(self, request: ChatRequest) -> bool:
        """ツール結果が含まれているかチェック"""
        for msg in request.messages:
            for block in msg.content:
                if isinstance(block, ToolResultBlock):
                    return True
        return False

    def _is_calculation_request(self, text: str) -> bool:
        """計算リクエストかチェック"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in ["calculate", "compute", "+"]) or \
               any(op in text for op in ["+", "-", "*", "/"])

    def _generate_calculation_tool_call(self, text: str) -> ChatResponse:
        """計算ツールコールを生成"""
        # 簡単なパース（実際にはもっと賢いパースが必要）
        if "+" in text:
            parts = text.split("+")
            if len(parts) == 2:
                try:
                    a = int("".join(filter(str.isdigit, parts[0])))
                    b = int("".join(filter(str.isdigit, parts[1])))

                    print(f"[SmartEchoProvider] Generating tool call: calculator(add, {a}, {b})")

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

        # パースできない場合はテキストレスポンス
        return ChatResponse(
            content=[TextBlock(text="I couldn't parse that calculation. Please try again.")],
            usage=Usage(input_tokens=10, output_tokens=20),
            stop_reason="end_turn"
        )

    def _generate_read_file_tool_call(self, text: str) -> ChatResponse:
        """ファイル読み込みツールコールを生成"""
        # 簡単なパース
        path = "/tmp/test.txt"  # デフォルトパス
        print(f"[SmartEchoProvider] Generating tool call: read_file({path})")

        return ChatResponse(
            content=[ToolCallBlock(
                type="tool_call",
                id=str(uuid.uuid4()),
                tool_name="read_file",
                input={"path": path}
            )],
            usage=Usage(input_tokens=10, output_tokens=20),
            stop_reason="tool_use"
        )

    def _generate_final_response(self, request: ChatRequest) -> ChatResponse:
        """ツール結果を含む最終レスポンスを生成"""
        # 最後のツール結果を取得
        tool_result = None
        for msg in reversed(request.messages):
            for block in msg.content:
                if isinstance(block, ToolResultBlock):
                    tool_result = block.content
                    break
            if tool_result:
                break

        print("[SmartEchoProvider] Generating final response")

        if tool_result and "result" in tool_result:
            result_value = tool_result["result"]
            response_text = f"The result is {result_value}."
        elif tool_result and "content" in tool_result:
            content = tool_result["content"]
            response_text = f"File contents:\n{content}"
        else:
            response_text = f"Tool execution completed. Result: {tool_result}"

        return ChatResponse(
            content=[TextBlock(text=response_text)],
            usage=Usage(input_tokens=10, output_tokens=20),
            stop_reason="end_turn"
        )

    def parse_tool_calls(self, response: ChatResponse) -> list[dict]:
        """ChatResponseからツールコールを抽出"""
        tool_calls = []
        for block in response.content:
            if isinstance(block, ToolCallBlock):
                tool_calls.append({
                    "id": block.id,
                    "tool_name": block.tool_name,
                    "input": block.input
                })
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
        """プロンプトを実行してレスポンスを返す（ツールループ付き）"""
        # 1. プロンプトをcontextに追加
        await context.add_message({
            "role": "user",
            "content": [TextBlock(text=prompt)]
        })

        # 2. ツール実行ループ
        provider = list(providers.values())[0]
        max_turns = 5

        for turn in range(1, max_turns + 1):
            print(f"\n[Turn {turn}]")

            # 3. ChatRequestを構築
            messages = await context.get_messages()
            chat_request = self._build_chat_request(messages)

            # 4. Providerを呼び出し
            print("[Orchestrator] Calling provider...")
            response = await provider.complete(chat_request)

            # 5. ツールコールがあるかチェック
            tool_calls = provider.parse_tool_calls(response)

            if not tool_calls:
                # 最終レスポンス
                print("[Orchestrator] Provider returned final response")
                response_text = self._extract_text(response)

                await context.add_message({
                    "role": "assistant",
                    "content": [TextBlock(text=response_text)]
                })

                return response_text

            # 6. ツールを実行
            print(f"[Orchestrator] Provider returned {len(tool_calls)} tool call(s)")

            for tc in tool_calls:
                tool_name = tc["tool_name"]
                tool = tools.get(tool_name)

                if not tool:
                    print(f"[Orchestrator] Tool not found: {tool_name}")
                    continue

                print(f"[Orchestrator] Executing tool: {tool_name}")
                result = await tool.execute(tc["input"])

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

        return "Error: Max turns exceeded"

    def _build_chat_request(self, messages: list[dict]) -> ChatRequest:
        """dict形式のメッセージからChatRequestを構築"""
        typed_messages = []

        for msg in messages:
            content = msg.get("content", [])

            # すでにブロック形式の場合
            if isinstance(content, list):
                typed_messages.append(Message(
                    role=msg["role"],
                    content=content
                ))
            # 文字列の場合
            else:
                typed_messages.append(Message(
                    role=msg["role"],
                    content=[TextBlock(text=content)]
                ))

        return ChatRequest(messages=typed_messages)

    def _extract_text(self, response: ChatResponse) -> str:
        """ChatResponseからテキストを抽出"""
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
        self._messages.append(message)

    async def get_messages(self) -> list[dict]:
        return self._messages.copy()

    async def should_compact(self) -> bool:
        return False

    async def compact(self) -> None:
        pass

    async def clear(self) -> None:
        self._messages.clear()


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

        print(f"[Session] Created session (ID: {self.session_id[:8]}...)")

    async def mount_tool(self, tool):
        self.tools[tool.name] = tool

    async def mount_provider(self, provider):
        self.providers[provider.name] = provider

    async def mount_orchestrator(self, orchestrator):
        self.orchestrator = orchestrator

    async def mount_context(self, context):
        self.context = context

    async def initialize(self):
        if not self.orchestrator or not self.context:
            raise ValueError("Orchestrator and Context required")

        tool_names = list(self.tools.keys())
        print(f"[Session] Mounted {len(tool_names)} tools: {', '.join(tool_names)}")
        print(f"[Session] Mounted provider: {list(self.providers.keys())[0]}")
        print("[Session] Mounted orchestrator")

        self._initialized = True
        print("[Session] Initialized")

    async def execute(self, prompt: str) -> str:
        if not self._initialized:
            raise ValueError("Not initialized")

        print(f"\n[Execute] Prompt: \"{prompt}\"")

        response = await self.orchestrator.execute(
            prompt=prompt,
            context=self.context,
            providers=self.providers,
            tools=self.tools,
            hooks=None,
        )

        return response


# === Main ===

async def main():
    print("=" * 60)
    print("Example 03: ツールの追加")
    print("=" * 60)
    print()

    # セッション作成
    config = {
        "session": {
            "orchestrator": "loop-orchestrator",
            "context": "simple-context"
        }
    }

    session = SimpleSession(config)

    # ツールをマウント
    calculator = CalculatorTool()
    await session.mount_tool(calculator)

    read_file = ReadFileTool()
    await session.mount_tool(read_file)

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
    result = await session.execute("Calculate 15 + 27")

    print()
    print("-" * 60)
    print("レスポンス:")
    print(f"  {result}")
    print("-" * 60)
    print()

    print("=" * 60)
    print("完了")
    print("=" * 60)
    print()

    print("学んだこと:")
    print("  1. Toolは name, description, execute() を実装")
    print("  2. Providerがツールコールを返す（ToolCallBlock）")
    print("  3. Orchestratorがツールを実行してループを管理")
    print("  4. ツール結果をcontextに追加して次のターンへ")
    print()
    print("次のステップ:")
    print("  - Example 04 でフックシステムを追加")
    print("  - イベントを観測してロギング")


if __name__ == "__main__":
    asyncio.run(main())
