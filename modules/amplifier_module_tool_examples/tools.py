"""
Example Tool Implementations

Amplifier Core の Tool プロトコルに準拠したツール実装例。

Tool プロトコル:
    - name: str (property) - ツール識別子
    - description: str (property) - ツールの説明
    - execute(input: dict) -> ToolResult - ツール実行
"""

from typing import Any

from amplifier_core import ToolResult, ToolSpec


class CalculatorTool:
    """
    四則演算を行う計算機ツール。

    Tool プロトコルの基本実装例。
    """

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Performs basic arithmetic calculations. Supports +, -, *, / operations."

    def get_spec(self) -> ToolSpec:
        """Get ToolSpec for LLM tool definition."""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression to evaluate (e.g., '2 + 3 * 4')"
                    }
                },
                "required": ["expression"]
            }
        )

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """Execute calculation."""
        try:
            if "expression" not in input:
                return ToolResult(
                    success=False,
                    error={"message": "Missing required parameter: expression"}
                )

            expr = input["expression"]

            # Security: only allow safe characters
            allowed_chars = set("0123456789+-*/.(). ")
            if not all(c in allowed_chars for c in expr):
                return ToolResult(
                    success=False,
                    error={"message": "Invalid characters in expression"}
                )

            # Note: eval is used for simplicity in examples only
            result = eval(expr)
            return ToolResult(success=True, output=result)

        except Exception as e:
            return ToolResult(
                success=False,
                error={"message": str(e), "type": type(e).__name__}
            )


class WeatherTool:
    """
    天気情報を取得するツール（モック実装）。

    外部 API を呼び出すツールのパターン例。
    """

    MOCK_DATA = {
        "tokyo": {"temp": 22, "condition": "Sunny", "humidity": 45},
        "new york": {"temp": 18, "condition": "Cloudy", "humidity": 60},
        "london": {"temp": 15, "condition": "Rainy", "humidity": 80},
        "paris": {"temp": 20, "condition": "Partly Cloudy", "humidity": 55},
        "sydney": {"temp": 25, "condition": "Clear", "humidity": 40},
    }

    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return "Gets current weather information for a specified city."

    def get_spec(self) -> ToolSpec:
        """Get ToolSpec for LLM tool definition."""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name (e.g., 'Tokyo', 'Paris')"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit (default: celsius)"
                    }
                },
                "required": ["city"]
            }
        )

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """Get weather information."""
        city = input.get("city")
        if not city:
            return ToolResult(
                success=False,
                error={"message": "Missing required parameter: city"}
            )

        unit = input.get("unit", "celsius")
        city_lower = city.lower()

        if city_lower not in self.MOCK_DATA:
            return ToolResult(
                success=False,
                error={
                    "message": f"Weather data not available for: {city}",
                    "available_cities": list(self.MOCK_DATA.keys())
                }
            )

        data = self.MOCK_DATA[city_lower]
        temp = data["temp"]

        if unit == "fahrenheit":
            temp = temp * 9 / 5 + 32

        return ToolResult(
            success=True,
            output={
                "city": city,
                "temperature": temp,
                "unit": unit,
                "condition": data["condition"],
                "humidity": data["humidity"],
            }
        )


class FileReaderTool:
    """
    ファイルを読み取るツール（仮想ファイルシステム）。

    ファイルシステム操作を行うツールのパターン例。
    """

    def __init__(self):
        self._virtual_fs = {
            "/readme.txt": "Welcome to Amplifier Core!\nThis is a sample file.",
            "/config.json": '{"version": "1.0", "debug": true}',
            "/data/users.csv": "id,name,email\n1,Alice,alice@example.com\n2,Bob,bob@example.com",
        }

    @property
    def name(self) -> str:
        return "file_reader"

    @property
    def description(self) -> str:
        return "Reads content from a file at the specified path."

    def get_spec(self) -> ToolSpec:
        """Get ToolSpec for LLM tool definition."""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read"
                    }
                },
                "required": ["path"]
            }
        )

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """Read file content."""
        path = input.get("path")
        if not path:
            return ToolResult(
                success=False,
                error={"message": "Missing required parameter: path"}
            )

        if path not in self._virtual_fs:
            return ToolResult(
                success=False,
                error={
                    "message": f"File not found: {path}",
                    "available_files": list(self._virtual_fs.keys())
                }
            )

        content = self._virtual_fs[path]
        return ToolResult(
            success=True,
            output={
                "path": path,
                "content": content,
                "size": len(content),
            }
        )


class MultiStepTool:
    """
    状態を持つツール。

    複数回の呼び出しで状態を維持するツールのパターン例。
    """

    def __init__(self):
        self._state: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "multi_step"

    @property
    def description(self) -> str:
        return "A tool that maintains state across invocations. Actions: set, get, list, clear."

    def get_spec(self) -> ToolSpec:
        """Get ToolSpec for LLM tool definition."""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["set", "get", "list", "clear"],
                        "description": "Action to perform"
                    },
                    "key": {
                        "type": "string",
                        "description": "Key name (required for set/get)"
                    },
                    "value": {
                        "description": "Value to set (required for set)"
                    }
                },
                "required": ["action"]
            }
        )

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """Manage state."""
        action = input.get("action")

        if action == "set":
            key = input.get("key")
            value = input.get("value")
            if not key:
                return ToolResult(
                    success=False,
                    error={"message": "Missing key for set action"}
                )
            self._state[key] = value
            return ToolResult(
                success=True,
                output={"message": f"Set {key} = {value}", "state": dict(self._state)}
            )

        elif action == "get":
            key = input.get("key")
            if not key:
                return ToolResult(
                    success=False,
                    error={"message": "Missing key for get action"}
                )
            if key not in self._state:
                return ToolResult(
                    success=False,
                    error={"message": f"Key not found: {key}"}
                )
            return ToolResult(
                success=True,
                output={"key": key, "value": self._state[key]}
            )

        elif action == "list":
            return ToolResult(
                success=True,
                output={"state": dict(self._state), "count": len(self._state)}
            )

        elif action == "clear":
            self._state.clear()
            return ToolResult(
                success=True,
                output={"message": "State cleared"}
            )

        else:
            return ToolResult(
                success=False,
                error={
                    "message": f"Unknown action: {action}",
                    "valid_actions": ["set", "get", "list", "clear"]
                }
            )
