"""
Basic Loop Orchestrator 実装

Amplifier Core の Orchestrator プロトコルに準拠したオーケストレーター実装。
Provider と Tool を連携させ、エージェントループを制御します。

Orchestrator プロトコル:
    - execute(prompt, context, providers, tools, hooks, coordinator) -> str
"""

import logging
from typing import Any

from amplifier_core import (
    ChatRequest,
    ChatResponse,
    TextBlock,
    ToolCallBlock,
    ToolSpec,
)
from amplifier_core.coordinator import ModuleCoordinator
from amplifier_core.events import (
    PROMPT_SUBMIT,
    PROMPT_COMPLETE,
    PROVIDER_REQUEST,
    PROVIDER_RESPONSE,
    PROVIDER_ERROR,
    TOOL_PRE,
    TOOL_POST,
    TOOL_ERROR,
    CONTEXT_PRE_COMPACT,
    CONTEXT_POST_COMPACT,
)
from amplifier_core.message_models import Message
from amplifier_core.models import ToolCall

logger = logging.getLogger(__name__)


class BasicLoopOrchestrator:
    """
    基本的なエージェントループオーケストレーター。

    Provider と Tool を連携させ、以下のループを実行:
    1. ユーザーメッセージをコンテキストに追加
    2. コンテキストから履歴を取得
    3. Provider にリクエストを送信
    4. レスポンスを解析
    5. ツール呼び出しがあれば実行
    6. 結果をコンテキストに追加
    7. 2-6 を繰り返し（最大ターン数まで）
    """

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: 設定
                - max_turns: 最大ターン数（デフォルト: 10）
                - provider: 使用するプロバイダー名（デフォルト: 最初のプロバイダー）
                - temperature: 温度パラメータ（デフォルト: 0.7）
                - max_tokens: 最大トークン数（デフォルト: 4096）
        """
        self._max_turns = config.get("max_turns", 10)
        self._provider_name = config.get("provider")
        self._temperature = config.get("temperature", 0.7)
        self._max_tokens = config.get("max_tokens", 4096)
        logger.info(
            f"BasicLoopOrchestrator initialized: "
            f"max_turns={self._max_turns}, provider={self._provider_name}"
        )

    async def execute(
        self,
        prompt: str,
        context,
        providers: dict,
        tools: dict,
        hooks,
        coordinator: ModuleCoordinator | None = None,
    ) -> str:
        """
        エージェントループを実行。

        Args:
            prompt: ユーザー入力
            context: コンテキストマネージャー
            providers: 利用可能なプロバイダー
            tools: 利用可能なツール
            hooks: フックレジストリ
            coordinator: コーディネーター（フック結果処理用）

        Returns:
            最終レスポンス文字列
        """
        logger.info(f"Starting agent loop with prompt: {prompt[:50]}...")

        # 1. プロンプト受信イベント
        await hooks.emit(PROMPT_SUBMIT, {
            "prompt": prompt,
            "max_turns": self._max_turns,
        })

        # 2. プロバイダー選択
        provider = self._select_provider(providers)
        if not provider:
            raise RuntimeError("No provider available")

        logger.info(f"Using provider: {provider.name}")

        # 3. ユーザーメッセージをコンテキストに追加
        await context.add_message({
            "role": "user",
            "content": prompt,
        })

        # 4. メインループ
        for turn in range(self._max_turns):
            logger.info(f"Turn {turn + 1}/{self._max_turns}")

            # ターン境界でコーディネーターの予算をリセット
            if coordinator:
                coordinator.reset_turn()

            # 4-1. コンテキスト準備
            messages = await self._prepare_context(context, hooks)

            # 4-2. ツール仕様の生成
            tool_specs = self._generate_tool_specs(tools)

            # 4-3. プロバイダー呼び出し
            response = await self._call_provider(
                provider,
                messages,
                tool_specs,
                hooks,
            )

            # 4-4. レスポンスをコンテキストに追加
            await context.add_message({
                "role": "assistant",
                "content": self._serialize_content(response),
            })

            # 4-5. ツール呼び出しの検出
            tool_calls = provider.parse_tool_calls(response)

            # LLMの応答内容をログ出力
            text_content = self._extract_text(response)
            if text_content:
                logger.info(f"LLM response text: {text_content[:100]}{'...' if len(text_content) > 100 else ''}")

            if not tool_calls:
                # ツール呼び出しなし → 終了
                logger.info("No tool calls in response - LLM has finished reasoning")
                final_response = text_content

                await hooks.emit(PROMPT_COMPLETE, {
                    "response": final_response,
                    "turns": turn + 1,
                })

                return final_response

            # 4-6. すべてのツール呼び出しを実行
            logger.info(f"LLM requested {len(tool_calls)} tool call(s)")
            await self._execute_tool_calls(
                tool_calls,
                tools,
                context,
                hooks,
                coordinator,
            )

        # 最大ターン数に到達
        logger.warning(f"Reached max turns ({self._max_turns})")

        final_response = "Maximum number of turns reached without completion."

        await hooks.emit(PROMPT_COMPLETE, {
            "response": final_response,
            "turns": self._max_turns,
            "max_turns_reached": True,
        })

        return final_response

    def _select_provider(self, providers: dict):
        """プロバイダーを選択"""
        if self._provider_name:
            return providers.get(self._provider_name)

        # デフォルト: 最初のプロバイダー
        return next(iter(providers.values())) if providers else None

    async def _prepare_context(self, context, hooks) -> list[Message]:
        """コンテキストを準備（必要に応じてコンパクション）"""
        messages = await context.get_messages()

        # コンパクション判定
        if await context.should_compact():
            logger.info("Compacting context")

            await hooks.emit(CONTEXT_PRE_COMPACT, {
                "message_count": len(messages),
                "reason": "token_limit_exceeded",
            })

            await context.compact()

            new_messages = await context.get_messages()

            await hooks.emit(CONTEXT_POST_COMPACT, {
                "old_count": len(messages),
                "new_count": len(new_messages),
            })

            messages = new_messages

        # dict -> Message 変換
        return self._convert_to_messages(messages)

    def _convert_to_messages(self, messages: list[dict]) -> list[Message]:
        """dict形式のメッセージをMessage型に変換"""
        result = []
        for msg in messages:
            content = msg.get("content", "")
            # content が文字列の場合はそのまま、それ以外はTextBlockに変換
            if isinstance(content, str):
                content = [TextBlock(type="text", text=content)]
            elif isinstance(content, list):
                # すでにブロックリストの場合
                pass
            else:
                content = [TextBlock(type="text", text=str(content))]

            result.append(Message(
                role=msg.get("role", "user"),
                content=content,
            ))
        return result

    def _generate_tool_specs(self, tools: dict) -> list[ToolSpec]:
        """ツール仕様を生成"""
        tool_specs = []

        for tool_name, tool in tools.items():
            # ツールが get_spec メソッドを持っている場合
            if hasattr(tool, "get_spec"):
                tool_specs.append(tool.get_spec())
            else:
                # デフォルトの仕様生成
                tool_specs.append(ToolSpec(
                    name=tool.name,
                    description=tool.description if hasattr(tool, "description") else "",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ))

        return tool_specs

    async def _call_provider(
        self,
        provider,
        messages: list[Message],
        tool_specs: list[ToolSpec],
        hooks,
    ) -> ChatResponse:
        """プロバイダーを呼び出し"""
        # リクエストイベント
        await hooks.emit(PROVIDER_REQUEST, {
            "provider": provider.name,
            "message_count": len(messages),
            "tool_count": len(tool_specs),
        })

        try:
            # ChatRequest の構築
            request = ChatRequest(
                messages=messages,
                tools=tool_specs if tool_specs else None,
                temperature=self._temperature,
                max_output_tokens=self._max_tokens,
            )

            # プロバイダー呼び出し
            response = await provider.complete(request)

            # レスポンスイベント
            await hooks.emit(PROVIDER_RESPONSE, {
                "provider": provider.name,
                "finish_reason": response.finish_reason,
                "usage": response.usage.model_dump() if response.usage else None,
            })

            return response

        except Exception as e:
            logger.error(f"Provider call failed: {e}")

            await hooks.emit(PROVIDER_ERROR, {
                "provider": provider.name,
                "error": str(e),
                "error_type": type(e).__name__,
            })

            raise

    def _extract_text(self, response: ChatResponse) -> str:
        """レスポンスからテキストを抽出"""
        texts = []
        for block in response.content:
            if isinstance(block, TextBlock):
                texts.append(block.text)
        return "\n".join(texts)

    def _serialize_content(self, response: ChatResponse) -> str:
        """レスポンスコンテンツをシリアライズ（コンテキスト保存用）"""
        parts = []
        for block in response.content:
            if isinstance(block, TextBlock):
                parts.append(block.text)
            elif isinstance(block, ToolCallBlock):
                parts.append(f"[Tool Call: {block.name}({block.input})]")
        return "\n".join(parts)

    async def _execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
        tools: dict,
        context,
        hooks,
        coordinator,
    ):
        """すべてのツール呼び出しを実行"""
        for tool_call in tool_calls:
            await self._execute_single_tool(
                tool_call,
                tools,
                context,
                hooks,
                coordinator,
            )

    async def _execute_single_tool(
        self,
        tool_call: ToolCall,
        tools: dict,
        context,
        hooks,
        coordinator,
    ):
        """単一のツール呼び出しを実行"""
        logger.info(f"LLM requested tool call: {tool_call.tool}")
        logger.info(f"  Arguments: {tool_call.arguments}")

        # ツール実行前イベント
        hook_result = await hooks.emit(TOOL_PRE, {
            "tool": tool_call.tool,
            "arguments": tool_call.arguments,
            "id": tool_call.id,
        })

        # フック結果の処理
        if coordinator and hook_result:
            processed_result = await coordinator.process_hook_result(
                hook_result,
                event="tool:pre",
                hook_name="pre-execution-hooks",
            )

            # deny の場合はスキップ
            if processed_result.action == "deny":
                logger.info(f"Tool '{tool_call.tool}' blocked: {processed_result.reason}")

                # ブロックメッセージをコンテキストに追加
                await context.add_message({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"[Tool execution blocked: {processed_result.reason}]",
                })
                return

        # ツール取得
        tool = tools.get(tool_call.tool)
        if not tool:
            logger.error(f"Tool '{tool_call.tool}' not found")

            await context.add_message({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": f"[Error: Tool '{tool_call.tool}' not found]",
            })
            return

        try:
            # ツール実行
            logger.info(f"  Executing tool '{tool_call.tool}'...")
            result = await tool.execute(tool_call.arguments)
            logger.info(f"  Tool result: success={result.success}, output={str(result.output)[:100]}")

            # ツール実行後イベント
            await hooks.emit(TOOL_POST, {
                "tool": tool_call.tool,
                "arguments": tool_call.arguments,
                "result": result.model_dump(),
                "success": result.success,
            })

            # 結果をコンテキストに追加
            if result.success:
                content = str(result.output)
            else:
                error_msg = result.error.get("message", "Unknown error") if result.error else "Unknown error"
                content = f"[Error: {error_msg}]"

            await context.add_message({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": content,
            })

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")

            await hooks.emit(TOOL_ERROR, {
                "tool": tool_call.tool,
                "arguments": tool_call.arguments,
                "error": str(e),
                "error_type": type(e).__name__,
            })

            # エラーをコンテキストに追加
            await context.add_message({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": f"[Error: {str(e)}]",
            })
