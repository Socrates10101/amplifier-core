# 02. 起動フロー - セッション作成とモジュールロード

## フロー全体図

```
AmplifierSession作成
    ↓
設定検証
    ↓
Coordinator作成
    ↓
HookRegistry初期化
    ↓
ModuleLoader作成
    ↓
initialize() 呼び出し
    ↓
├─→ Orchestratorロード
├─→ Context Managerロード
├─→ Providersロード
├─→ Toolsロード
└─→ Hooksロード
    ↓
session:fork イベント発行（子セッションの場合）
    ↓
初期化完了
```

## ステップ1: セッション作成

**コード:** `session.py:28-82`

```python
session = AmplifierSession(config)
```

### 1-1. 設定検証 (`session.py:56-61`)

```python
if not config:
    raise ValueError("Configuration is required")
if not config.get("session", {}).get("orchestrator"):
    raise ValueError("Configuration must specify session.orchestrator")
if not config.get("session", {}).get("context"):
    raise ValueError("Configuration must specify session.context")
```

**必須項目:**
- `session.orchestrator` - 実行ループ戦略（例: "loop-basic"）
- `session.context` - コンテキスト管理（例: "context-simple"）

### 1-2. ID生成 (`session.py:64-65`)

```python
self.session_id = session_id if session_id else str(uuid.uuid4())
self.parent_id = parent_id  # 子セッションの場合のみ
```

### 1-3. Coordinator作成 (`session.py:71-75`)

```python
self.coordinator = ModuleCoordinator(
    session=self,
    approval_system=approval_system,  # アプリ層から注入
    display_system=display_system,    # アプリ層から注入
)
```

**Coordinatorが初期化するもの** (`coordinator.py:67-84`):

```python
self.mount_points = {
    "orchestrator": None,
    "providers": {},
    "tools": {},
    "context": None,
    "hooks": HookRegistry(),
    "module-source-resolver": None,
}
self._cleanup_functions = []
self._capabilities = {}
self.channels = {}
```

### 1-4. デフォルトフィールドの設定 (`session.py:78`)

```python
self.coordinator.hooks.set_default_fields(
    session_id=self.session_id,
    parent_id=self.parent_id
)
```

**効果:** 以降すべてのイベントに自動的に `session_id` と `parent_id` が含まれます。

## ステップ2: モジュール初期化

**コード:** `session.py:95-222`

```python
await session.initialize()
```

### ロード順序

1. **Orchestrator** (必須) - `session.py:107-131`
2. **Context Manager** (必須) - `session.py:133-154`
3. **Providers** (必須、複数可) - `session.py:156-171`
4. **Tools** (オプション、複数可) - `session.py:173-188`
5. **Hooks** (オプション、複数可) - `session.py:193-208`

### 2-1. Orchestratorのロード

**設定の解析** (`session.py:109-117`):

```python
orchestrator_spec = self.config.get("session", {}).get("orchestrator")

# dict形式の場合
if isinstance(orchestrator_spec, dict):
    orchestrator_id = orchestrator_spec.get("module")        # "loop-basic"
    orchestrator_source = orchestrator_spec.get("source")    # git/file/package URI
    orchestrator_config = orchestrator_spec.get("config")    # モジュール固有設定
else:
    # 文字列形式の場合
    orchestrator_id = orchestrator_spec
```

**モジュールのロード** (`session.py:122-131`):

```python
orchestrator_mount = await self.loader.load(
    orchestrator_id,
    orchestrator_config,
    profile_source=orchestrator_source
)

# mount関数を呼び出してCoordinatorに登録
cleanup = await orchestrator_mount(self.coordinator)
if cleanup:
    self.coordinator.register_cleanup(cleanup)
```

## ステップ3: Loaderの内部動作

**コード:** `loader.py:144-220`

### 3-1. ソース解決 (`loader.py:167-195`)

```python
# ModuleSourceResolverの取得を試行
source_resolver = None
if self._coordinator:
    with contextlib.suppress(ValueError):
        source_resolver = self._coordinator.get("module-source-resolver")

if source_resolver is None:
    # リゾルバーなし → エントリーポイント/ファイルシステムから直接
    mount_fn = await self._load_direct(module_id, config)
    if mount_fn:
        return mount_fn
else:
    # リゾルバー使用 → ソースURIを解決
    source = source_resolver.resolve(module_id, profile_source)
    module_path = source.resolve()  # 実際のパスを取得
```

**ソースURI例:**
- `git+https://github.com/org/repo@main`
- `file:///absolute/path`
- `./relative/path`
- `package-name`（またはsource省略でインストール済みパッケージ）

### 3-2. sys.pathへの追加 (`loader.py:197-202`)

```python
path_str = str(module_path)
if path_str not in sys.path:
    sys.path.insert(0, path_str)
```

**重要:** モジュールの依存関係がインポート可能になるよう、パスは永続的に残ります。

### 3-3. エントリーポイント経由のロード (`loader.py:249-269`)

```python
def _load_entry_point(self, module_id: str, config: dict | None = None):
    eps = importlib.metadata.entry_points(group="amplifier.modules")

    for ep in eps:
        if ep.name == module_id:
            mount_fn = ep.load()

            async def mount_with_config(coordinator, fn=mount_fn):
                return await fn(coordinator, config or {})

            return mount_with_config
```

**pyproject.tomlの例:**

```toml
[project.entry-points."amplifier.modules"]
loop-basic = "amplifier_module_loop_basic:mount"
provider-anthropic = "amplifier_module_provider_anthropic:mount"
tool-bash = "amplifier_module_tool_bash:mount"
```

### 3-4. ファイルシステム経由のロード (`loader.py:271-292`)

```python
def _load_filesystem(self, module_id: str, config: dict | None = None):
    # "loop-basic" → "amplifier_module_loop_basic"
    module_name = f"amplifier_module_{module_id.replace('-', '_')}"
    module = importlib.import_module(module_name)

    if hasattr(module, "mount"):
        mount_fn = module.mount

        async def mount_with_config(coordinator):
            return await mount_fn(coordinator, config or {})

        return mount_with_config
```

## ステップ4: モジュールのマウント

ロードされたモジュールの `mount` 関数が呼ばれます。

**典型的なmount関数の構造:**

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
    await coordinator.mount("providers", instance, name="my-provider")

    # 3. フック登録（オプション）
    coordinator.hooks.register(
        "provider:request",
        instance.on_request,
        priority=0,
        name="my-provider-logger"
    )

    # 4. 能力登録（オプション）
    coordinator.register_capability(
        "my-provider.feature",
        lambda: instance.do_something()
    )

    # 5. コントリビューション登録（オプション）
    coordinator.register_contributor(
        "observability.events",
        "my-provider",
        lambda: ["my-provider:event1", "my-provider:event2"]
    )

    # 6. クリーンアップ関数（オプション）
    async def cleanup():
        await instance.close()

    return cleanup
```

**実際の例は [モジュール実装例](../module-examples/) を参照してください。**

## ステップ5: 複数モジュールのロード

### Providersのロード (`session.py:156-171`)

```python
for provider_config in self.config.get("providers", []):
    module_id = provider_config.get("module")
    if not module_id:
        continue

    provider_mount = await self.loader.load(
        module_id,
        provider_config.get("config", {}),
        profile_source=provider_config.get("source")
    )
    cleanup = await provider_mount(self.coordinator)
    if cleanup:
        self.coordinator.register_cleanup(cleanup)
```

**設定例:**

```python
"providers": [
    {
        "module": "provider-anthropic",
        "source": "git+https://github.com/...",
        "config": {
            "api_key": "sk-...",
            "default_model": "claude-sonnet-4-5-20250929"
        }
    },
    {
        "module": "provider-openai",
        "config": {"api_key": "sk-..."}
    }
]
```

### Toolsのロード (`session.py:173-188`)

```python
for tool_config in self.config.get("tools", []):
    # Providerと同じパターン
```

### Hooksのロード (`session.py:193-208`)

```python
for hook_config in self.config.get("hooks", []):
    # Providerと同じパターン
```

## ステップ6: セッションフォークイベント

**コード:** `session.py:212-216`

```python
if self.parent_id:
    from .events import SESSION_FORK
    await self.coordinator.hooks.emit(SESSION_FORK, {"parent": self.parent_id})
```

子セッション（`parent_id` が設定されている）の場合、`session:fork` イベントが発行され、親子関係が観測可能になります。

## マウント状態の確認

初期化後のマウントポイント:

```python
session.coordinator.mount_points
# {
#   "orchestrator": <OrchestratorInstance>,
#   "providers": {
#     "anthropic": <AnthropicProvider>,
#     "openai": <OpenAIProvider>
#   },
#   "tools": {
#     "bash": <BashTool>,
#     "filesystem": <FilesystemTool>
#   },
#   "context": <ContextManager>,
#   "hooks": <HookRegistry>,
#   "module-source-resolver": None
# }
```

## 次のステップ

- [実行フロー](./03-execution-flow.md)で実際のプロンプト処理を理解
- [モジュール実装例](../module-examples/)で具体的な実装を確認
