# モジュール実装例

このディレクトリには、Amplifier Coreのモジュールを実装するための具体的な例が含まれています。

## モジュールタイプ

各モジュールタイプの実装例：

1. **[Provider](./provider-example.md)** - LLMプロバイダーの実装
   - Anthropic Providerの完全な実装例
   - ChatRequest/ChatResponse処理
   - ストリーミング対応

2. **[Tool](./tool-example.md)** - ツールモジュールの実装
   - Bash Toolの完全な実装例
   - Filesystem Toolの実装例
   - ツール仕様の生成

3. **[Orchestrator](./orchestrator-example.md)** - 実行ループの実装
   - Basic Loopオーケストレーターの実装
   - イベント発行のタイミング
   - ツール実行とフック処理

4. **[Context Manager](./context-example.md)** - コンテキスト管理の実装
   - Simple Context Managerの実装
   - メッセージ履歴の管理
   - コンパクション戦略

5. **[Hook](./hook-example.md)** - フックモジュールの実装
   - ロギングフック
   - セキュリティフック
   - Linter統合フック
   - メトリクス収集フック

## 共通パターン

### mount関数の基本構造

すべてのモジュールは `mount` 関数を実装します：

```python
async def mount(coordinator: ModuleCoordinator, config: dict):
    """
    モジュールをCoordinatorにマウント。

    Args:
        coordinator: インフラストラクチャコンテキスト
        config: モジュール固有の設定

    Returns:
        cleanup関数（オプション）
    """
    # 1. インスタンス作成
    instance = MyModule(config)

    # 2. Coordinatorにマウント
    await coordinator.mount("mount-point", instance, name="module-name")

    # 3. 追加設定（オプション）
    # - フック登録
    # - 能力登録
    # - コントリビューション登録

    # 4. クリーンアップ関数（オプション）
    async def cleanup():
        await instance.close()

    return cleanup
```

### プロトコルの実装

モジュールはプロトコルに従うだけで、継承は不要です：

```python
from typing import Protocol

@runtime_checkable
class MyModuleProtocol(Protocol):
    async def my_method(self, arg: str) -> str: ...

# 実装（継承なし）
class MyModule:
    async def my_method(self, arg: str) -> str:
        return f"Result: {arg}"

# プロトコルチェック
assert isinstance(MyModule(), MyModuleProtocol)
```

## エントリーポイントの設定

モジュールをパッケージとして配布する場合、`pyproject.toml` にエントリーポイントを追加：

```toml
[project.entry-points."amplifier.modules"]
my-module = "amplifier_module_my_module:mount"
```

これにより、`amplifier-core` がモジュールを自動的に発見できます。

## 次のステップ

1. 実装したいモジュールタイプの例を確認
2. プロトコル定義を理解（`amplifier_core/interfaces.py`）
3. 実装例をベースに独自のモジュールを作成
4. [コードリーディングガイド](../code-reading/)で動作を理解
