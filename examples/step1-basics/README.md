# Step 1: 基本構造の理解

このステップでは、Amplifier Coreの3つの基本コンポーネントを学びます：

1. **AmplifierSession** - メインエントリーポイント
2. **ModuleCoordinator** - モジュール間の調整ハブ
3. **HookRegistry** - イベントシステム

## 学習目標

- セッションの作成方法を理解する
- Coordinatorにモジュールをマウントする方法を理解する
- イベントの発行と受信の仕組みを理解する

## ファイル構成

```
step1-basics/
├── README.md          # このファイル
├── app.py             # メインアプリケーション
└── mock_modules.py    # モックモジュール定義
```

## 実行方法

```bash
cd examples/step1-basics
python app.py
```

## コード解説

### 1. セッションの作成

```python
from amplifier_core import AmplifierSession

config = {
    "session": {
        "orchestrator": "mock-orchestrator",
        "context": "mock-context"
    }
}
session = AmplifierSession(config)
```

セッションには最低限 `orchestrator` と `context` の指定が必要です。

### 2. Coordinatorへのマウント

```python
# Coordinatorを通じてモジュールをマウント
# 単一モジュール（orchestrator, context）
await session.coordinator.mount("orchestrator", orchestrator_instance)
await session.coordinator.mount("context", context_instance)

# 複数モジュール（providers, tools）- name引数が必要
await session.coordinator.mount("providers", provider_instance, name="my-provider")
await session.coordinator.mount("tools", tool_instance, name="my-tool")
```

マウントポイント:
- `orchestrator` - 単一のOrchestratorインスタンス
- `context` - 単一のContextManagerインスタンス
- `providers` - 複数のプロバイダー（name で識別）
- `tools` - 複数のツール（name で識別）

### 3. イベントの発行と受信

```python
# ハンドラーを登録
def my_handler(event: str, data: dict) -> HookResult:
    print(f"Event: {event}, Data: {data}")
    return HookResult(action="continue")

session.coordinator.hooks.register("my:event", my_handler, priority=0)

# イベントを発行
result = await session.coordinator.hooks.emit("my:event", {"key": "value"})
```

## 重要な概念

### HookResult

イベントハンドラーは `HookResult` を返します：

| action | 説明 |
|--------|------|
| `continue` | 処理を続行 |
| `deny` | 処理を中断（short-circuit） |
| `modify` | データを修正して続行 |
| `inject_context` | コンテキストに情報を追加 |
| `ask_user` | ユーザーに承認を求める |

### 優先度（Priority）

- 数値が小さいほど先に実行される
- 同じ優先度の場合は登録順
