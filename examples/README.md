# Amplifier Core - 実行可能なサンプル集

実際に動かしながらAmplifier Coreの仕組みを学ぶための段階的なサンプルです。

## クイックスタート

```bash
# サンプル01から順に実行
cd examples/01-minimal
python3 app_standalone.py

cd ../02-simple-echo
python3 app_standalone.py

cd ../03-with-tools
python3 app_standalone.py

# ... 以降も同様
```

すべてのサンプルは**依存関係なし**で実行できます（Python 3.11+のみ）。

## サンプルの進め方

各サンプルは独立して実行できます。番号順に進めることで、徐々に機能を理解できます：

### 01-minimal - 最小構成
**学べること:** セッションの基本構造、3つの発火ポイント
- モックコンポーネントで最小限の動作を確認
- `AmplifierSession()`、`initialize()`、`execute()` の流れ
- イベントがどのように発火するかを観察

→ [01-minimal/README.md](./01-minimal/README.md)

### 02-simple-echo - シンプルなProvider
**学べること:** Provider の実装、ChatRequest/ChatResponse
- エコーバックするだけのシンプルなProvider
- ChatRequest を受け取り ChatResponse を返す流れ
- Orchestrator がどのように Provider を呼び出すか

→ [02-simple-echo/README.md](./02-simple-echo/README.md)

### 03-with-tools - ツールの追加
**学べること:** Tool の実装、ToolCall/ToolResult
- ファイル読み込みツール
- 計算ツール
- Orchestrator がツールを実行する流れ

→ [03-with-tools/README.md](./03-with-tools/README.md)

### 04-with-hooks - フックシステム
**学べること:** Hook の実装、HookResult、イベント観測
- ロギングフック
- タイミング計測フック
- イベントドリブンアーキテクチャの実践

→ [04-with-hooks/README.md](./04-with-hooks/README.md)

### 05-with-security - セキュリティと承認
**学べること:** セキュリティフック、ApprovalSystem
- 危険なコマンドのブロック
- 承認ゲートの実装
- 多層防御の仕組み

→ [05-with-security/README.md](./05-with-security/README.md)

### 06-full-cli-agent - 完全なCLIエージェント
**学べること:** 実用的なCLIエージェントの構築
- Bash/Filesystem/Edit ツール
- セキュリティ + 承認の統合
- 実際のファイル操作とコマンド実行

→ [06-full-cli-agent/README.md](./06-full-cli-agent/README.md)

## 実行方法

各サンプルには**スタンドアロン版** (`app_standalone.py`) があります。
これは`amplifier-core`をインストールせずに実行できる教育的なバージョンです：

```bash
# サンプル01を実行（スタンドアロン版）
cd examples/01-minimal
python3 app_standalone.py

# サンプル02を実行
cd examples/02-simple-echo
python3 app_standalone.py

# サンプル03を実行
cd examples/03-with-tools
python3 app_standalone.py

# ... 以下同様
```

**スタンドアロン版の特徴：**
- 依存関係不要（Python 3.11+ のみ）
- 実際の動作フローを理解するための教育的実装
- 簡略化されているが、本質的な概念は同じ

### 実際のamplifier-coreを使う場合

`app.py` （一部のサンプルに含まれる）は実際の`amplifier-core`を使用します：

```bash
# プロジェクトルートで依存関係をインストール
pip install pydantic pyyaml tomli typing-extensions

# サンプルを実行（PYTHONPATHを設定）
cd examples/01-minimal
PYTHONPATH=/path/to/amplifier-core:$PYTHONPATH python3 app.py
```

## デバッグモード

各サンプルは環境変数でログレベルを変更できます：

```bash
# 詳細ログを表示
AMPLIFIER_LOG_LEVEL=DEBUG python app.py

# イベントトレースを表示
AMPLIFIER_LOG_LEVEL=DEBUG python app.py
```

## 各サンプルの比較

| サンプル | Orchestrator | Provider | Tools | Hooks | セキュリティ |
|---------|-------------|----------|-------|-------|------------|
| 01 | Mock | Mock | - | - | - |
| 02 | Simple | Echo | - | - | - |
| 03 | Loop | Echo | Read, Calc | - | - |
| 04 | Loop | Echo | Read, Calc | Logging, Timing | - |
| 05 | Loop | Echo | Bash, File | Logging, Security | Approval |
| 06 | Full | Anthropic | Bash, File, Edit | All | Full |

## 次のステップ

- [コードリーディングガイド](../docs/code-reading/) で内部構造を詳しく学ぶ
- [モジュール実装例](../docs/module-examples/) で実装パターンを学ぶ
- 自分のカスタムモジュールを実装してみる

## トラブルシューティング

**ModuleNotFoundError: amplifier_core**
```bash
# プロジェクトルートで開発モードインストール
pip install -e .
```

**ImportError: No module named 'pydantic'**
```bash
pip install pydantic
```

**動作が理解できない**
```bash
# デバッグログを有効化
AMPLIFIER_LOG_LEVEL=DEBUG python app.py
```
