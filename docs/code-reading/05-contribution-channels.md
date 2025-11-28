# 05. コントリビューションチャネル - プルベース集約

## コントリビューションチャネルとは

プルベースの集約メカニズムで、モジュールが機能や情報を宣言し、消費者が必要時に収集します。

**特徴:**
- **プルベース**: 消費者が必要な時に `collect_contributions()` を呼び出す
- **非干渉**: 失敗した貢献者はログに記録され、スキップされる
- **順序保持**: 貢献は登録順に返される
- **フォーマット非依存**: カーネルは解釈せず、消費者が解釈

## 基本的な使い方

### 貢献者の登録

**コード:** `coordinator.py:257-285`

```python
coordinator.register_contributor(
    channel="observability.events",
    name="tool-filesystem",
    callback=lambda: ["filesystem:read", "filesystem:write", "filesystem:delete"]
)
```

**引数:**
- `channel`: チャネル名（例: "observability.events", "capabilities"）
- `name`: モジュール名（デバッグ用）
- `callback`: 貢献を返すcallable（同期/非同期両方サポート）

### 貢献の収集

**コード:** `coordinator.py:287-322`

```python
contributions = await coordinator.collect_contributions("observability.events")
# → [
#      ["filesystem:read", "filesystem:write"],
#      ["bash:execute", "bash:complete"],
#      ["task:agent_spawned"]
#    ]
```

## 内部動作

### 登録処理

```python
def register_contributor(self, channel, name, callback):
    if channel not in self.channels:
        self.channels[channel] = []

    self.channels[channel].append({
        "name": name,
        "callback": callback
    })

    logger.debug(f"Registered contributor '{name}' to channel '{channel}'")
```

**データ構造:**

```python
self.channels = {
    "observability.events": [
        {"name": "tool-filesystem", "callback": lambda: [...]},
        {"name": "tool-bash", "callback": lambda: [...]},
    ],
    "capabilities": [
        {"name": "tool-task", "callback": lambda: {...}},
    ]
}
```

### 収集処理

```python
async def collect_contributions(self, channel):
    contributions = []

    for contributor in self.channels.get(channel, []):
        try:
            callback = contributor["callback"]

            # 同期/非同期の両方に対応
            if inspect.iscoroutinefunction(callback):
                result = await callback()
            else:
                result = callback()
                if inspect.iscoroutine(result):
                    result = await result

            if result is not None:
                contributions.append(result)

        except Exception as e:
            # 失敗した貢献者はログに記録してスキップ
            logger.warning(f"Contributor '{contributor['name']}' on channel '{channel}' failed: {e}")

    return contributions
```

**特徴:**
- エラーが発生しても他の貢献者に影響しない
- `None` は自動的にフィルタされる
- 同期・非同期callbackの両方をサポート

## ユースケース

### ユースケース1: カスタムイベントの宣言

各ツールモジュールが独自のイベントを宣言します。

**Filesystemツール:**

```python
async def mount(coordinator, config):
    tool = FilesystemTool(config)
    await coordinator.mount("tools", tool, name="filesystem")

    # カスタムイベントを宣言
    coordinator.register_contributor(
        "observability.events",
        "tool-filesystem",
        lambda: [
            "filesystem:read",
            "filesystem:write",
            "filesystem:delete",
            "filesystem:mkdir",
            "filesystem:chmod"
        ]
    )
```

**Bashツール:**

```python
async def mount(coordinator, config):
    tool = BashTool(config)
    await coordinator.mount("tools", tool, name="bash")

    # カスタムイベントを宣言
    coordinator.register_contributor(
        "observability.events",
        "tool-bash",
        lambda: [
            "bash:execute",
            "bash:complete",
            "bash:timeout",
            "bash:killed"
        ]
    )
```

**フックモジュールが収集:**

```python
async def mount(coordinator, config):
    # すべてのカスタムイベントを収集
    all_custom_events = await coordinator.collect_contributions("observability.events")
    # → [
    #      ["filesystem:read", "filesystem:write", ...],
    #      ["bash:execute", "bash:complete", ...],
    #    ]

    # フラット化
    custom_events = [event for events in all_custom_events for event in events]

    # イベント名の検証
    for event in custom_events:
        if event.count(":") != 1:
            logger.warning(f"Invalid event name: {event}")
```

### ユースケース2: 能力の発見

各モジュールが自身の能力を宣言します。

**Webサーチツール:**

```python
async def mount(coordinator, config):
    tool = WebSearchTool(config)
    await coordinator.mount("tools", tool, name="web-search")

    # 検索能力を宣言
    coordinator.register_contributor(
        "capabilities.search",
        "tool-web-search",
        lambda: {
            "engines": ["google", "bing", "duckduckgo"],
            "max_results": 100,
            "supports_images": True,
            "supports_news": True
        }
    )
```

**Databaseツール:**

```python
async def mount(coordinator, config):
    tool = DatabaseTool(config)
    await coordinator.mount("tools", tool, name="database")

    # 検索能力を宣言
    coordinator.register_contributor(
        "capabilities.search",
        "tool-database",
        lambda: {
            "engines": ["postgresql", "mysql"],
            "max_results": 1000,
            "supports_fulltext": True,
            "supports_fuzzy": False
        }
    )
```

**オーケストレーターが活用:**

```python
# すべての検索能力を発見
search_capabilities = await coordinator.collect_contributions("capabilities.search")
# → [
#      {"engines": ["google", ...], "max_results": 100, ...},
#      {"engines": ["postgresql", ...], "max_results": 1000, ...}
#    ]

# 最も適切な検索ツールを選択
if user_query_is_web_related:
    # Web検索能力を持つツールを使用
    web_tools = [cap for cap in search_capabilities if "google" in cap["engines"]]
else:
    # データベース検索能力を持つツールを使用
    db_tools = [cap for cap in search_capabilities if "postgresql" in cap["engines"]]
```

### ユースケース3: 動的なツール説明

ツールが自身の説明を動的に生成します。

**Filesystemツール:**

```python
async def mount(coordinator, config):
    tool = FilesystemTool(config)
    await coordinator.mount("tools", tool, name="filesystem")

    # 動的な説明を提供
    coordinator.register_contributor(
        "tool-descriptions",
        "tool-filesystem",
        lambda: {
            "name": "filesystem",
            "description": tool.get_description(),  # 現在の設定に基づく
            "available_operations": tool.get_available_operations(),
            "restrictions": tool.get_restrictions()
        }
    )
```

**オーケストレーターがLLMに渡す:**

```python
# すべてのツール説明を収集
tool_descriptions = await coordinator.collect_contributions("tool-descriptions")

# LLMに渡すツール仕様を生成
tool_specs = [
    {
        "name": desc["name"],
        "description": desc["description"],
        # ...
    }
    for desc in tool_descriptions
]
```

### ユースケース4: メトリクスの集約

各モジュールが自身のメトリクスを提供します。

**Providerモジュール:**

```python
async def mount(coordinator, config):
    provider = AnthropicProvider(config)
    await coordinator.mount("providers", provider, name="anthropic")

    # メトリクス提供
    coordinator.register_contributor(
        "metrics",
        "provider-anthropic",
        lambda: {
            "total_requests": provider.request_count,
            "total_tokens": provider.total_tokens,
            "total_cost": provider.total_cost,
            "errors": provider.error_count
        }
    )
```

**ツールモジュール:**

```python
async def mount(coordinator, config):
    tool = BashTool(config)
    await coordinator.mount("tools", tool, name="bash")

    # メトリクス提供
    coordinator.register_contributor(
        "metrics",
        "tool-bash",
        lambda: {
            "total_executions": tool.execution_count,
            "total_failures": tool.failure_count,
            "avg_duration": tool.avg_execution_time
        }
    )
```

**フックモジュールが収集:**

```python
async def on_session_end(event, data):
    # すべてのメトリクスを収集
    all_metrics = await coordinator.collect_contributions("metrics")
    # → [
    #      {"total_requests": 10, "total_tokens": 5000, ...},
    #      {"total_executions": 25, "total_failures": 2, ...}
    #    ]

    # 集約して表示
    summary = {
        "providers": all_metrics[0],
        "tools": all_metrics[1:]
    }
    print(json.dumps(summary, indent=2))
```

## 非同期callbackのサポート

```python
# 同期callback
coordinator.register_contributor(
    "simple-data",
    "module-a",
    lambda: {"value": 42}
)

# 非同期callback
async def get_data():
    data = await fetch_from_database()
    return {"value": data}

coordinator.register_contributor(
    "async-data",
    "module-b",
    get_data
)

# 収集時は同じインターフェース
data = await coordinator.collect_contributions("async-data")
```

## エラーハンドリング

貢献者がエラーを発生させても、他の貢献者には影響しません：

```python
coordinator.register_contributor(
    "data",
    "module-a",
    lambda: {"value": 1}
)

coordinator.register_contributor(
    "data",
    "module-b",
    lambda: 1 / 0  # エラー！
)

coordinator.register_contributor(
    "data",
    "module-c",
    lambda: {"value": 3}
)

# 収集
data = await coordinator.collect_contributions("data")
# → [{"value": 1}, {"value": 3}]
# module-bはログに記録され、スキップされる
```

## 実装例

詳細な実装例は以下を参照：

- [Hook実装例 - メトリクス収集](../module-examples/hook-example.md#メトリクスフック)
- [Tool実装例 - 能力宣言](../module-examples/tool-example.md#能力宣言)

## 次のステップ

- [デバッグとトレーシング](./06-debugging.md)でデバッグ方法を学ぶ
- [モジュール実装例](../module-examples/)で実際のコードを確認
