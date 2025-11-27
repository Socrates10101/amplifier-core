"""
Amplifier Module: tool-examples

学習用のツール実装を提供するモジュール。
Tool プロトコルに準拠した実装例です。

Usage (config):
    {
        "tools": [
            {
                "module": "tool-examples",
                "config": {
                    "tools": ["calculator", "weather", "file_reader"]
                }
            }
        ]
    }

Available tools:
    - calculator: 四則演算
    - weather: 天気情報（モック）
    - file_reader: ファイル読み取り（仮想FS）
    - multi_step: 状態管理
"""

from .tools import CalculatorTool, WeatherTool, FileReaderTool, MultiStepTool
from .mount import mount

__all__ = [
    "CalculatorTool",
    "WeatherTool",
    "FileReaderTool",
    "MultiStepTool",
    "mount",
]
