"""
Example 02: シンプルなProvider（スタンドアロン版）

Providerを実装して、LLM風の応答を生成するサンプルです。
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any


# === Message Models (簡易版) ===

@dataclass
class TextBlock:
    type: str = "text"
    text: str = ""


@dataclass
class Message:
    role: str
    content: list[TextBlock]


@dataclass
class ChatRequest:
    messages: list[Message]
    tools: list[dict] = field(default_factory=list)
    max_tokens: int = 1024
    temperature: float = 0.7


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class ChatResponse:
    content: list[TextBlock]
    usage: Usage
    stop_reason: str


# === Echo Provider ===

class EchoProvider:
    """最もシンプルなProvider実装 - エコーバックするだけ"""

    @property
    def name(self) -> str:
        return "echo-provider"

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        """ChatRequestを受け取り、エコーレスポンスを返す"""
        print(f"[EchoProvider] Received request with {len(request.messages)} messages")

        # 最後のメッセージを取得
        if request.messages:
            last_message = request.messages[-1]
            if last_message.content:
                last_content = last_message.content[0].text
            else:
                last_content = "nothing"
        else:
            last_content = "nothing"

        print(f"[EchoProvider] Last message: {last_content}")

        # エコーレスポンスを構築
        response_text = f"[Echo] You said: {last_content}\n"
        response_text += "I'm a simple echo provider, so I'll just repeat what you said."

        return ChatResponse(
            content=[TextBlock(type="text", text=response_text)],
            usage=Usage(input_tokens=10, output_tokens=20),
            stop_reason="end_turn"
        )

    def parse_tool_calls(self, response: ChatResponse) -> list[Any]:
        """このシンプルな実装ではツールコールをサポートしない"""
        return []


# === Simple Orchestrator ===

class SimpleOrchestrator:
    """Providerを1回だけ呼び出す最もシンプルなOrchestrator"""

    async def execute(
        self,
        prompt: str,
        context,  # ContextManager
        providers: dict,
        tools: dict,
        hooks: Any,
    ) -> str:
        """プロンプトを実行してレスポンスを返す"""
        print(f"[Orchestrator] execute() called with prompt: {prompt}")

        # 1. プロンプトをcontextに追加
        await context.add_message({
            "role": "user",
            "content": prompt
        })

        # 2. Contextからメッセージを取得
        messages = await context.get_messages()
        print(f"[Orchestrator] Context messages: {len(messages)}")

        # 3. ChatRequestを構築
        print("[Orchestrator] Building ChatRequest...")
        chat_request = self._build_chat_request(messages)

        # 4. Providerを呼び出し
        if not providers:
            return "Error: No provider available"

        provider = list(providers.values())[0]  # 最初のproviderを使用
        print(f"[Orchestrator] Calling provider: {provider.name}")

        response = await provider.complete(chat_request)
        print("[Orchestrator] Provider response received")

        # 5. レスポンステキストを抽出
        response_text = self._extract_text(response)

        # 6. レスポンスをcontextに追加
        await context.add_message({
            "role": "assistant",
            "content": response_text
        })

        return response_text

    def _build_chat_request(self, messages: list[dict]) -> ChatRequest:
        """dict形式のメッセージからChatRequestを構築"""
        typed_messages = []
        for msg in messages:
            content = msg.get("content", "")
            typed_messages.append(Message(
                role=msg["role"],
                content=[TextBlock(text=content)]
            ))

        return ChatRequest(messages=typed_messages)

    def _extract_text(self, response: ChatResponse) -> str:
        """ChatResponseからテキストを抽出"""
        texts = []
        for block in response.content:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts)


# === Simple Context Manager ===

class SimpleContextManager:
    """メモリ内でメッセージを保持するシンプルなContextManager"""

    def __init__(self):
        self._messages: list[dict[str, Any]] = []

    async def add_message(self, message: dict[str, Any]) -> None:
        self._messages.append(message)

    async def get_messages(self) -> list[dict[str, Any]]:
        return self._messages.copy()

    async def should_compact(self) -> bool:
        return False

    async def compact(self) -> None:
        pass

    async def clear(self) -> None:
        self._messages.clear()


# === Simple Session ===

class SimpleSession:
    """AmplifierSessionの簡易版"""

    def __init__(self, config: dict):
        self.session_id = str(uuid.uuid4())
        self.config = config
        self._initialized = False

        # マウントポイント
        self.orchestrator = None
        self.context = None
        self.providers: dict[str, Any] = {}
        self.tools: dict[str, Any] = {}

        print(f"[1/3] セッション作成完了 (ID: {self.session_id[:8]}...)")

    async def mount_provider(self, provider):
        """Providerをマウント"""
        self.providers[provider.name] = provider
        print(f"[2/3] Providerをマウント: {provider.name}")

    async def mount_orchestrator(self, orchestrator):
        """Orchestratorをマウント"""
        self.orchestrator = orchestrator
        print("[2/3] Orchestratorをマウント: simple-orchestrator")

    async def mount_context(self, context):
        """ContextManagerをマウント"""
        self.context = context
        print("[2/3] ContextManagerをマウント")

    async def initialize(self):
        """初期化"""
        if not self.orchestrator or not self.context:
            raise ValueError("Orchestrator and Context must be mounted")

        self._initialized = True
        print("[2/3] 初期化完了")

    async def execute(self, prompt: str) -> str:
        """プロンプトを実行"""
        if not self._initialized:
            raise ValueError("Session must be initialized")

        print(f"\n[3/3] プロンプト実行: \"{prompt}\"\n")

        # Orchestratorに実行を委譲
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
    print("Example 02: シンプルなProvider")
    print("=" * 60)
    print()

    # 1. セッション作成
    config = {
        "session": {
            "orchestrator": "simple-orchestrator",
            "context": "simple-context"
        },
        "providers": [
            {"module": "echo-provider"}
        ]
    }

    session = SimpleSession(config)

    # 2. モジュールをマウント
    provider = EchoProvider()
    await session.mount_provider(provider)

    orchestrator = SimpleOrchestrator()
    await session.mount_orchestrator(orchestrator)

    context = SimpleContextManager()
    await session.mount_context(context)

    await session.initialize()
    print()

    # 3. プロンプトを実行
    result = await session.execute("What is 2 + 2?")

    print()
    print("-" * 60)
    print("レスポンス:")
    print(f"  {result.replace(chr(10), chr(10) + '  ')}")
    print("-" * 60)
    print()

    print("=" * 60)
    print("完了")
    print("=" * 60)
    print()

    print("学んだこと:")
    print("  1. Providerは ChatRequest を受け取り ChatResponse を返す")
    print("  2. Orchestratorが Context → ChatRequest → Provider の流れを管理")
    print("  3. Provider は name, complete(), parse_tool_calls() を実装")
    print()
    print("次のステップ:")
    print("  - Example 03 でツールを追加する")
    print("  - Providerがツールを呼び出せるようにする")


if __name__ == "__main__":
    asyncio.run(main())
