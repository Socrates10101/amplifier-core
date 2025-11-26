"""
Example 05: セキュリティと承認（簡易デモ）

セキュリティフックと承認システムの統合を示します。
"""

import asyncio
from dataclasses import dataclass


@dataclass
class HookResult:
    action: str = "continue"
    reason: str = ""
    approval_prompt: str = ""


class ApprovalSystem:
    """承認システム（簡易版）"""

    async def request_approval(self, prompt: str) -> bool:
        """承認をリクエスト（自動応答版）"""
        print(f"\n[ApprovalSystem] Approval requested:")
        print(f"  Prompt: {prompt}")
        print(f"  [Auto-approved for demo]")
        return True


class EnhancedSecurityHook:
    """セキュリティと承認を統合したフック"""

    def __init__(self, approval_system: ApprovalSystem):
        self.approval = approval_system
        self.blocked = ["rm -rf", "format", "delete_all"]
        self.needs_approval = ["write_file", "execute_command"]

    async def handle_event(self, event: str, data: dict) -> HookResult:
        if event != "tool:pre":
            return HookResult(action="continue")

        tool_name = data.get("tool_name", "")
        input_data = data.get("input", {})

        # 完全にブロック
        if any(blocked in str(input_data).lower() for blocked in self.blocked):
            print(f"[SecurityHook] BLOCKED: Dangerous operation detected")
            return HookResult(
                action="deny",
                reason="Operation blocked for security"
            )

        # 承認が必要
        if tool_name in self.needs_approval:
            print(f"[SecurityHook] Approval required for: {tool_name}")

            approved = await self.approval.request_approval(
                f"Allow {tool_name} with input {input_data}?"
            )

            if not approved:
                return HookResult(action="deny", reason="User denied")

            print(f"[SecurityHook] Approved: {tool_name}")

        return HookResult(action="continue")


async def demo():
    print("=" * 60)
    print("Example 05: セキュリティと承認")
    print("=" * 60)
    print()

    approval = ApprovalSystem()
    security = EnhancedSecurityHook(approval)

    # Test 1: 安全な操作
    print("\n--- Test 1: 安全な操作 ---")
    result = await security.handle_event("tool:pre", {
        "tool_name": "calculator",
        "input": {"operation": "add", "a": 1, "b": 2}
    })
    print(f"Result: {result.action}")

    # Test 2: 承認が必要な操作
    print("\n--- Test 2: 承認が必要な操作 ---")
    result = await security.handle_event("tool:pre", {
        "tool_name": "write_file",
        "input": {"path": "/tmp/test.txt", "content": "hello"}
    })
    print(f"Result: {result.action}")

    # Test 3: ブロックされる操作
    print("\n--- Test 3: ブロックされる操作 ---")
    result = await security.handle_event("tool:pre", {
        "tool_name": "execute_command",
        "input": {"command": "rm -rf /important"}
    })
    print(f"Result: {result.action} - {result.reason}")

    print()
    print("=" * 60)
    print("完了")
    print("=" * 60)
    print()
    print("学んだこと:")
    print("  1. セキュリティフックで多層防御")
    print("  2. ApprovalSystemで動的な承認")
    print("  3. ブロック/承認/許可の3段階制御")


if __name__ == "__main__":
    asyncio.run(demo())
