"""
Claude CLI Provider Module

ローカルで認証済みの Claude Code CLI を Provider として使用するモジュール。
APIキー不要で、Amplifier の Provider プロトコルに準拠。

使用方法:
    config = {
        "providers": [
            {
                "module": "provider-claude-cli",
                "config": {
                    "mode": "controlled",  # "passthrough" or "controlled"
                    "model": "sonnet",     # optional
                }
            }
        ]
    }

モード:
    - passthrough: CLIに全て任せる（ツールもCLI側で実行）
    - controlled: CLIのツールを無効化し、Amplifier側でツール実行を制御
"""

from .provider import ClaudeCliProvider
from .mount import mount

__all__ = ["ClaudeCliProvider", "mount"]
