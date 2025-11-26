"""
Example 04: フックシステム（トレース版）

フックの実行タイミングとイベントフローを詳細に可視化します。
"""

import asyncio
import time
from dataclasses import dataclass


# === トレースユーティリティ ===

class ExecutionTracer:
    """実行トレースを表示するユーティリティ"""

    def __init__(self):
        self.depth = 0
        self.step = 0

    def enter(self, component: str, method: str = "", details: str = ""):
        """コンポーネントに入る"""
        self.step += 1
        indent = "  " * self.depth
        arrow = "┌─" if self.depth == 0 else "├─"
        label = f"{component}.{method}()" if method else component
        print(f"{arrow} [{self.step:02d}] {indent}{label} {details}")
        self.depth += 1

    def exit(self, component: str = "", result: str = ""):
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
        prefix = {
            "INFO": "ℹ️ ",
            "WARN": "⚠️ ",
            "ERROR": "❌",
            "SUCCESS": "✅"
        }.get(level, "  ")
        print(f"{symbol} {indent}{prefix} {message}")

    def event(self, event_name: str, data: str = ""):
        """イベント発火"""
        indent = "  " * self.depth
        symbol = "│ " if self.depth > 0 else "  "
        print(f"{symbol} {indent}🔔 EVENT: {event_name} {data}")

    def hook(self, hook_name: str, action: str = "continue"):
        """フック実行"""
        indent = "  " * self.depth
        symbol = "│ " if self.depth > 0 else "  "
        action_icon = {
            "continue": "→",
            "deny": "🚫",
            "inject_context": "💉",
            "ask_user": "❓"
        }.get(action, "?")
        print(f"{symbol} {indent}  🪝 HOOK: {hook_name} → {action_icon} {action}")


tracer = ExecutionTracer()


@dataclass
class HookResult:
    """フック実行結果"""
    action: str = "continue"
    reason: str = ""


class HookRegistry:
    """フックを登録・実行するレジストリ"""

    def __init__(self):
        self._hooks: dict[str, list] = {}
        self._hook_names: dict = {}  # handler -> name のマッピング

    def register(self, event: str, handler, name: str = ""):
        """イベントにフックを登録"""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(handler)
        if name:
            self._hook_names[id(handler)] = name

    async def emit(self, event: str, data: dict) -> list[HookResult]:
        """イベントを発火してフックを実行"""
        tracer.event(event, self._format_data(data))

        results = []

        if event in self._hooks:
            tracer.enter("HookRegistry", "emit", f"({len(self._hooks[event])} hooks)")

            for handler in self._hooks[event]:
                hook_name = self._hook_names.get(id(handler), handler.__name__)

                result = await handler(event, data)
                results.append(result)

                tracer.hook(hook_name, result.action)

                # denyアクションがあればすぐに停止
                if result.action == "deny":
                    tracer.log(f"Denied: {result.reason}", "WARN")
                    break

            tracer.exit("", f"processed {len(results)} hooks")

        return results

    def _format_data(self, data: dict) -> str:
        """データを短く表示"""
        if "message" in data:
            return f"({data['message'][:40]}...)"
        return ""


class LoggingHook:
    """ロギングフック - すべてのイベントを記録"""

    def __init__(self):
        self.event_count = 0

    async def handle_event(self, event: str, data: dict) -> HookResult:
        self.event_count += 1
        # tracer.log(f"Event #{self.event_count}: {event}")
        return HookResult(action="continue")


class TimingHook:
    """タイミング計測フック"""

    def __init__(self):
        self.start_time = None
        self.turn_start_time = None

    async def handle_event(self, event: str, data: dict) -> HookResult:
        if event == "session:start":
            self.start_time = time.time()
            tracer.log("⏱️  Session timer started")

        elif event == "session:end":
            if self.start_time:
                duration = time.time() - self.start_time
                tracer.log(f"⏱️  Total session time: {duration:.3f}s", "SUCCESS")

        elif event == "turn:start":
            self.turn_start_time = time.time()

        elif event == "turn:end":
            if self.turn_start_time:
                duration = time.time() - self.turn_start_time
                tracer.log(f"⏱️  Turn completed in {duration:.3f}s")

        return HookResult(action="continue")


class SecurityHook:
    """セキュリティフック - 危険な操作をブロック"""

    def __init__(self):
        self.blocked_operations = ["delete_file", "execute_shell", "rm_rf"]
        self.safe_operations = ["calculator", "read_file"]

    async def handle_event(self, event: str, data: dict) -> HookResult:
        if event == "tool:pre":
            tool_name = data.get("tool_name", "")

            if tool_name in self.blocked_operations:
                tracer.log(f"🚫 BLOCKED: {tool_name}", "ERROR")
                return HookResult(
                    action="deny",
                    reason=f"Tool '{tool_name}' is blocked for security"
                )

            if tool_name in self.safe_operations:
                tracer.log(f"✅ Allowed: {tool_name}", "SUCCESS")

        return HookResult(action="continue")


class MetricsHook:
    """メトリクス収集フック"""

    def __init__(self):
        self.provider_calls = 0
        self.tool_calls = 0
        self.tool_successes = 0

    async def handle_event(self, event: str, data: dict) -> HookResult:
        if event == "provider:post":
            self.provider_calls += 1

        elif event == "tool:post":
            self.tool_calls += 1
            if data.get("success"):
                self.tool_successes += 1

        elif event == "session:end":
            tracer.log("📊 Session Metrics:", "INFO")
            tracer.log(f"   Provider calls: {self.provider_calls}")
            tracer.log(f"   Tool calls: {self.tool_calls}")
            tracer.log(f"   Tool successes: {self.tool_successes}")

        return HookResult(action="continue")


class SimpleSession:
    """フックシステムを持つシンプルなセッション"""

    def __init__(self):
        self.hooks = HookRegistry()
        self._initialized = False

    async def initialize(self):
        """初期化"""
        tracer.enter("Session", "initialize")
        await self.hooks.emit("session:start", {"message": "Initializing session"})
        self._initialized = True
        tracer.exit("Session", "initialized")

    async def execute_turn(self, turn_number: int, tool_name: str):
        """1ターンを実行"""
        print(f"\n{'═' * 60}")
        print(f"  TURN {turn_number} - Tool: {tool_name}")
        print(f"{'═' * 60}\n")

        tracer.enter(f"Turn {turn_number}")

        # Turn開始
        await self.hooks.emit("turn:start", {
            "turn": turn_number,
            "message": f"Starting turn {turn_number}"
        })

        # Provider呼び出し
        tracer.log("Calling provider...")
        await self.hooks.emit("provider:pre", {
            "provider": "echo-provider",
            "message": "About to call provider"
        })

        await asyncio.sleep(0.05)  # Provider処理をシミュレート

        await self.hooks.emit("provider:post", {
            "provider": "echo-provider",
            "message": "Provider returned tool call"
        })

        # ツール実行前（セキュリティチェック）
        tracer.log(f"Attempting to execute tool: {tool_name}")

        results = await self.hooks.emit("tool:pre", {
            "tool_name": tool_name,
            "message": f"About to execute: {tool_name}"
        })

        # denyチェック
        denied = any(r.action == "deny" for r in results)

        if not denied:
            # ツール実行
            tracer.log(f"Executing {tool_name}...", "INFO")
            await asyncio.sleep(0.05)

            await self.hooks.emit("tool:post", {
                "tool_name": tool_name,
                "success": True,
                "message": f"Tool {tool_name} completed"
            })
        else:
            tracer.log(f"Tool {tool_name} execution BLOCKED", "ERROR")

        # Turn終了
        await self.hooks.emit("turn:end", {
            "turn": turn_number,
            "message": f"Turn {turn_number} completed"
        })

        tracer.exit(f"Turn {turn_number}")

    async def cleanup(self):
        """クリーンアップ"""
        tracer.enter("Session", "cleanup")
        await self.hooks.emit("session:end", {"message": "Session ending"})
        tracer.exit("Session", "cleaned up")


async def main():
    print("=" * 60)
    print("Example 04: フックシステム（トレース版）")
    print("=" * 60)
    print()
    print("フックの実行タイミングとイベントフローを表示します：")
    print("  🔔 EVENT: イベント発火")
    print("  🪝 HOOK: フック実行")
    print("  → continue: 処理を継続")
    print("  🚫 deny: 処理をブロック")
    print()
    print("=" * 60)
    print()

    # セッション作成
    tracer.enter("Setup", "", "Registering hooks...")

    session = SimpleSession()

    # フックを登録
    logging_hook = LoggingHook()
    session.hooks.register("session:start", logging_hook.handle_event, "LoggingHook")
    session.hooks.register("session:end", logging_hook.handle_event, "LoggingHook")
    session.hooks.register("turn:start", logging_hook.handle_event, "LoggingHook")
    session.hooks.register("turn:end", logging_hook.handle_event, "LoggingHook")
    session.hooks.register("provider:pre", logging_hook.handle_event, "LoggingHook")
    session.hooks.register("provider:post", logging_hook.handle_event, "LoggingHook")
    session.hooks.register("tool:pre", logging_hook.handle_event, "LoggingHook")
    session.hooks.register("tool:post", logging_hook.handle_event, "LoggingHook")

    timing_hook = TimingHook()
    session.hooks.register("session:start", timing_hook.handle_event, "TimingHook")
    session.hooks.register("session:end", timing_hook.handle_event, "TimingHook")
    session.hooks.register("turn:start", timing_hook.handle_event, "TimingHook")
    session.hooks.register("turn:end", timing_hook.handle_event, "TimingHook")

    security_hook = SecurityHook()
    session.hooks.register("tool:pre", security_hook.handle_event, "SecurityHook")

    metrics_hook = MetricsHook()
    session.hooks.register("provider:post", metrics_hook.handle_event, "MetricsHook")
    session.hooks.register("tool:post", metrics_hook.handle_event, "MetricsHook")
    session.hooks.register("session:end", metrics_hook.handle_event, "MetricsHook")

    tracer.log("Registered 4 hooks:")
    tracer.log("  1. LoggingHook - すべてのイベントを記録")
    tracer.log("  2. TimingHook - 時間を計測")
    tracer.log("  3. SecurityHook - 危険なツールをブロック")
    tracer.log("  4. MetricsHook - メトリクスを収集")

    tracer.exit("Setup")

    # セッション実行
    print("\n" + "=" * 60)
    print("  EXECUTION START")
    print("=" * 60 + "\n")

    await session.initialize()

    # Turn 1: 安全なツール
    await session.execute_turn(1, "calculator")

    # Turn 2: 危険なツール（ブロックされる）
    await session.execute_turn(2, "delete_file")

    # Turn 3: 安全なツール
    await session.execute_turn(3, "calculator")

    # クリーンアップ
    print("\n" + "=" * 60)
    print("  SESSION CLEANUP")
    print("=" * 60 + "\n")

    await session.cleanup()

    print("\n" + "=" * 60)
    print("  COMPLETE")
    print("=" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(main())
