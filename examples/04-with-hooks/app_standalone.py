"""
Example 04: フックシステム（スタンドアロン版）

フックシステムでイベントを観測し、動作を制御します。
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class HookResult:
    """フック実行結果"""
    action: str = "continue"  # continue, deny, inject_context, ask_user
    reason: str = ""
    context_injection: str = ""


class HookRegistry:
    """フックを登録・実行するレジストリ"""

    def __init__(self):
        self._hooks: dict[str, list] = {}

    def register(self, event: str, handler):
        """イベントにフックを登録"""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(handler)

    async def emit(self, event: str, data: dict) -> list[HookResult]:
        """イベントを発火してフックを実行"""
        results = []

        if event in self._hooks:
            for handler in self._hooks[event]:
                result = await handler(event, data)
                results.append(result)

                # denyアクションがあればすぐに停止
                if result.action == "deny":
                    break

        return results


class LoggingHook:
    """ロギングフック - すべてのイベントを記録"""

    async def handle_event(self, event: str, data: dict) -> HookResult:
        timestamp = time.strftime("%H:%M:%S")
        message = data.get("message", "")
        print(f"[{timestamp}] [LogHook] {event:<20} {message}")
        return HookResult(action="continue")


class TimingHook:
    """タイミング計測フック - セッション時間を計測"""

    def __init__(self):
        self.start_time = None
        self.turn_start_time = None

    async def handle_event(self, event: str, data: dict) -> HookResult:
        if event == "session:start":
            self.start_time = time.time()
            print("[TimingHook] Session started")

        elif event == "session:end":
            if self.start_time:
                duration = time.time() - self.start_time
                print(f"[TimingHook] Session duration: {duration:.2f}s")

        elif event == "turn:start":
            self.turn_start_time = time.time()

        elif event == "turn:end":
            if self.turn_start_time:
                duration = time.time() - self.turn_start_time
                print(f"[TimingHook] Turn duration: {duration:.2f}s")

        return HookResult(action="continue")


class SecurityHook:
    """セキュリティフック - 危険な操作をブロック"""

    def __init__(self):
        self.blocked_operations = ["delete_file", "execute_shell"]

    async def handle_event(self, event: str, data: dict) -> HookResult:
        if event == "tool:pre":
            tool_name = data.get("tool_name", "")

            if tool_name in self.blocked_operations:
                print(f"[SecurityHook] BLOCKED: {tool_name} is not allowed")
                return HookResult(
                    action="deny",
                    reason=f"Tool '{tool_name}' is blocked for security reasons"
                )

            print(f"[SecurityHook] Allowed: {tool_name}")

        return HookResult(action="continue")


class SimpleSession:
    """フックシステムを持つシンプルなセッション"""

    def __init__(self):
        self.hooks = HookRegistry()
        self._initialized = False

    async def initialize(self):
        """初期化してsession:startイベントを発火"""
        print("\n" + "=" * 60)
        print("セッション初期化")
        print("=" * 60 + "\n")

        await self.hooks.emit("session:start", {
            "message": "Session initializing..."
        })

        self._initialized = True

    async def execute_turn(self, turn_number: int):
        """1ターンを実行（フックイベント付き）"""
        print(f"\n--- Turn {turn_number} ---")

        # Turn開始
        await self.hooks.emit("turn:start", {
            "turn": turn_number,
            "message": f"Starting turn {turn_number}"
        })

        # Provider呼び出し前
        await self.hooks.emit("provider:pre", {
            "provider": "echo-provider",
            "message": "About to call provider"
        })

        # Provider呼び出しをシミュレート
        await asyncio.sleep(0.1)

        # Provider呼び出し後
        await self.hooks.emit("provider:post", {
            "provider": "echo-provider",
            "message": "Provider call completed"
        })

        # ツール実行前（セキュリティチェック）
        tool_name = "calculator" if turn_number % 2 == 1 else "delete_file"

        results = await self.hooks.emit("tool:pre", {
            "tool_name": tool_name,
            "message": f"About to execute tool: {tool_name}"
        })

        # denyチェック
        denied = any(r.action == "deny" for r in results)

        if not denied:
            # ツール実行をシミュレート
            await asyncio.sleep(0.1)

            await self.hooks.emit("tool:post", {
                "tool_name": tool_name,
                "success": True,
                "message": f"Tool {tool_name} executed successfully"
            })
        else:
            print(f"[Session] Tool {tool_name} was blocked by security hook")

        # Turn終了
        await self.hooks.emit("turn:end", {
            "turn": turn_number,
            "message": f"Turn {turn_number} completed"
        })

    async def cleanup(self):
        """クリーンアップしてsession:endイベントを発火"""
        print("\n" + "=" * 60)
        print("セッション終了")
        print("=" * 60 + "\n")

        await self.hooks.emit("session:end", {
            "message": "Session ending..."
        })


async def main():
    print("=" * 60)
    print("Example 04: フックシステム")
    print("=" * 60)
    print()

    print("このサンプルでは以下を学びます：")
    print("  1. Hookでイベントを観測")
    print("  2. 複数のフックを登録")
    print("  3. HookResultでdenyアクションによるブロック")
    print()

    # セッション作成
    session = SimpleSession()

    # フックを登録
    print("フックを登録中...")

    logging_hook = LoggingHook()
    session.hooks.register("session:start", logging_hook.handle_event)
    session.hooks.register("session:end", logging_hook.handle_event)
    session.hooks.register("turn:start", logging_hook.handle_event)
    session.hooks.register("turn:end", logging_hook.handle_event)
    session.hooks.register("provider:pre", logging_hook.handle_event)
    session.hooks.register("provider:post", logging_hook.handle_event)
    session.hooks.register("tool:pre", logging_hook.handle_event)
    session.hooks.register("tool:post", logging_hook.handle_event)

    timing_hook = TimingHook()
    session.hooks.register("session:start", timing_hook.handle_event)
    session.hooks.register("session:end", timing_hook.handle_event)
    session.hooks.register("turn:start", timing_hook.handle_event)
    session.hooks.register("turn:end", timing_hook.handle_event)

    security_hook = SecurityHook()
    session.hooks.register("tool:pre", security_hook.handle_event)

    print("  - LoggingHook: すべてのイベントをログ")
    print("  - TimingHook: 時間を計測")
    print("  - SecurityHook: 危険なツールをブロック")
    print()

    # セッション実行
    await session.initialize()

    # Turn 1: 安全なツール
    await session.execute_turn(1)

    # Turn 2: 危険なツール（ブロックされる）
    await session.execute_turn(2)

    # Turn 3: 安全なツール
    await session.execute_turn(3)

    # クリーンアップ
    await session.cleanup()

    print()
    print("=" * 60)
    print("完了")
    print("=" * 60)
    print()

    print("学んだこと:")
    print("  1. HookRegistryでイベントとハンドラーを管理")
    print("  2. emit()でイベントを発火し、すべてのフックを実行")
    print("  3. HookResult(action='deny')で処理をブロック")
    print("  4. 複数のフックが同じイベントを観測できる")
    print()
    print("次のステップ:")
    print("  - Example 05 で承認システムを追加")
    print("  - HookResult(action='ask_user')を実装")


if __name__ == "__main__":
    asyncio.run(main())
