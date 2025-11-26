"""
Example 06: 完全なCLIエージェント（コンセプトデモ）

これまでの要素を統合した概念実証です。
"""

import asyncio


def print_section(title: str):
    """セクションヘッダーを表示"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


async def demo():
    print_section("Example 06: 完全なCLIエージェント")

    print("\nこのサンプルは、これまでのすべての要素を統合したものです：\n")

    print("【アーキテクチャ】")
    print("""
    User: "Write a Python script to hello.py"
        ↓
    AmplifierSession
        ↓
    Orchestrator
        ├→ [Turn 1]
        │   ├→ Context: Add user message
        │   ├→ Provider: Analyze request
        │   │   └→ Returns: ToolCall(filesystem, write, ...)
        │   ├→ Hook (Security): Check path
        │   ├→ Hook (Approval): Ask user
        │   └→ Tool (Filesystem): Write file
        │
        ├→ [Turn 2]
        │   ├→ Context: Add tool result
        │   └→ Provider: Generate response
        │       └→ Returns: "I've written the file"
        │
        └→ Response: "I've written the file"
    """)

    print("\n【実行フロー】")
    print("\n1. セッション作成と初期化")
    print("   - Orchestrator をロード")
    print("   - Context Manager をロード")
    print("   - Provider をロード (LLM)")
    print("   - Tools をロード (Bash, Filesystem, Edit)")
    print("   - Hooks を登録 (Logging, Security, Approval)")

    await asyncio.sleep(0.5)

    print("\n2. プロンプト実行")
    print("   [Turn 1]")
    print("   - Provider: ツールコール生成 (write_file)")
    print("   - Hook (Security): パスをチェック ✓")
    print("   - Hook (Approval): ユーザーに確認 ✓")
    print("   - Tool: ファイルを書き込み ✓")

    await asyncio.sleep(0.5)

    print("\n   [Turn 2]")
    print("   - Provider: 最終レスポンス生成")
    print("   - レスポンス: 'Successfully wrote hello.py'")

    await asyncio.sleep(0.5)

    print("\n3. フックによる観測")
    print("   [LoggingHook]")
    print("     - session:start")
    print("     - provider:pre")
    print("     - provider:post (tool_call)")
    print("     - tool:pre (write_file)")
    print("     - tool:post (success)")
    print("     - provider:pre")
    print("     - provider:post (text)")
    print("     - session:end")

    await asyncio.sleep(0.5)

    print("\n4. セキュリティ多層防御")
    print("   [Layer 1: Tool Config]")
    print("     - allowed_paths: ['/tmp', './']")
    print("     - max_file_size: 10MB")
    print("\n   [Layer 2: Security Hook]")
    print("     - Block: rm -rf, format, dd")
    print("     - Validate: path, size, permissions")
    print("\n   [Layer 3: Approval Hook]")
    print("     - Require approval for:")
    print("       - Write outside /tmp")
    print("       - Execute commands")
    print("       - Delete operations")

    print_section("学んだこと")

    print("""
1. セッション管理
   - AmplifierSession がすべてを統合
   - initialize() でモジュールをロード
   - execute() でプロンプトを実行

2. モジュールシステム
   - Orchestrator: 実行ループ
   - Provider: LLM統合
   - Tools: アクション実行
   - Context: 会話履歴管理
   - Hooks: イベント観測と制御

3. イベント駆動
   - すべての重要なポイントでイベント発火
   - フックが観測・制御
   - 非侵入的な拡張

4. セキュリティパターン
   - 多層防御
   - Fail-safe デフォルト
   - 最小権限の原則
    """)

    print_section("次のステップ")

    print("""
実際のAmplifier Coreを使う：

1. 依存関係をインストール
   $ pip install pydantic pyyaml tomli

2. 実際のプロバイダーモジュールを使用
   - anthropic-provider
   - openai-provider

3. カスタムモジュールを実装
   - 独自のToolを作成
   - 独自のHookを追加
   - 独自のOrchestratorを実装

4. ドキュメントを読む
   - docs/code-reading/  コード解説
   - docs/module-examples/  実装例

5. コミュニティに参加
   - GitHub Issues
   - Discussions
    """)

    print("=" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(demo())
