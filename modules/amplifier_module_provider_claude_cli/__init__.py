"""
Amplifier Module: provider-claude-cli

ローカルで認証済みの Claude Code CLI を Provider として使用するモジュール。
APIキー不要で、Amplifier の Provider プロトコルに準拠。

Usage (config):
    {
        "providers": [
            {
                "module": "provider-claude-cli",
                "config": {
                    "mode": "controlled",
                    "model": "sonnet"
                }
            }
        ]
    }

Modes:
    - passthrough: CLIに全て任せる（ツールもCLI側で実行）
    - controlled: CLIのツールを無効化し、Amplifier側でツール実行を制御（推奨）
"""

from .provider import ClaudeCliProvider
from .mount import mount

__all__ = ["ClaudeCliProvider", "mount"]
