# Example 01: 最小構成

最もシンプルなAmplifier Coreの動作例です。

## 学べること

1. **3つの発火ポイント**
   - `AmplifierSession(config)` - セッション作成
   - `await session.initialize()` - モジュールのロードとマウント
   - `await session.execute(prompt)` - プロンプトの実行

2. **モックコンポーネント**
   - Orchestrator: 固定メッセージを返すだけ
   - ContextManager: メモリ内でメッセージを保持するだけ
   - Provider/Tools: なし（最小限）

3. **イベントの流れ**
   - セッション作成時に何が起こるか
   - initialize() で何がロードされるか
   - execute() でどのようにOrchestratorが呼ばれるか

## ファイル構成

```
01-minimal/
├── README.md          # このファイル
├── app.py             # 実行スクリプト
└── mock_modules.py    # モックコンポーネント実装
```

## 実行方法

```bash
# プロジェクトルートで依存関係をインストール
pip install pydantic pyyaml tomli typing-extensions

# サンプルを実行
cd examples/01-minimal
PYTHONPATH=/path/to/amplifier-core:$PYTHONPATH python3 app.py
```

**注意:** このサンプルは`amplifier-core`がインストールされている環境で実行してください。

または、スタンドアロン版を使用：
```bash
python3 app_standalone.py
```

### 🔍 3つの発火ポイントを可視化（トレース版）

各発火ポイントで何が起こるかを詳細に表示：

```bash
python3 app_with_trace.py
```

トレース版では以下が明確にわかります：
- **発火ポイント 1/3**: `AmplifierSession(config)` でのインスタンス生成
- **発火ポイント 2/3**: `await session.initialize()` でのモジュールマウント
- **発火ポイント 3/3**: `await session.execute(prompt)` での実行フロー

## 期待される出力

```
=== Example 01: 最小構成 ===

[INFO] Creating AmplifierSession...
[INFO] Session ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

[INFO] Initializing session...
[INFO] Loading orchestrator: mock-orchestrator
[INFO] Loading context manager: mock-context

[INFO] Executing prompt: "Hello, Amplifier!"
[INFO] Orchestrator received prompt: Hello, Amplifier!
[INFO] Response: This is a mock response. Your prompt was: Hello, Amplifier!

=== Done ===
```

## コードの詳細解説

### app.py の流れ

```python
# 1. 設定を作成
config = {
    "session": {
        "orchestrator": "mock-orchestrator",
        "context": "mock-context"
    }
}

# 2. セッション作成（発火ポイント1）
session = AmplifierSession(config)
# → session.py:28-82 が実行される
# → ModuleCoordinator が作成される
# → ModuleLoader が作成される

# 3. 初期化（発火ポイント2）
await session.initialize()
# → session.py:95-152 が実行される
# → loader.load_module() でモジュールがロードされる
# → mount() 関数が呼ばれてコンポーネントが登録される
# → session:start イベントが発火

# 4. 実行（発火ポイント3）
result = await session.execute("Hello, Amplifier!")
# → session.py:154-226 が実行される
# → orchestrator.execute() が呼ばれる
# → モックOrchestratorが固定メッセージを返す
```

### mock_modules.py の実装

**MockOrchestrator:**
- 最もシンプルな実装
- プロンプトを受け取り、固定メッセージを返すだけ
- Provider や Tools は使わない

**MockContextManager:**
- メモリ内でメッセージリストを保持
- add_message() と get_messages() のみ実装
- コンパクションは行わない

## 次のステップ

→ [Example 02: シンプルなProvider](../02-simple-echo/) で、実際のLLM風の応答を実装します。

## デバッグのヒント

詳細なログを見たい場合：

```bash
AMPLIFIER_LOG_LEVEL=DEBUG python app.py
```

これにより、以下が確認できます：
- モジュールローディングの詳細
- イベント発火のタイミング
- 各コンポーネントの呼び出し
