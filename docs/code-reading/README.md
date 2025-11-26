# Amplifier Core - コードリーディングガイド

実際の使用フローに沿って、各コンポーネントがどのように動作し、連携するかを解説します。

## 目次

0. **[開発者向けスタートガイド](./00-getting-started.md)** - 最初の一歩から実行まで
   - プロジェクトのセットアップ
   - 最小限のPythonスクリプト
   - 3つの発火ポイントの詳細
   - よくある質問

1. **[概要](./01-overview.md)** - アーキテクチャ全体像
   - 2層アーキテクチャ
   - 核心的な設計哲学
   - 主要コンポーネント
   - データフロー

2. **[起動フロー](./02-startup-flow.md)** - セッション作成とモジュールロード
   - セッション作成の詳細
   - モジュールローディングの仕組み
   - マウントプロセス

3. **[実行フロー](./03-execution-flow.md)** - プロンプト実行の流れ
   - execute()の呼び出し
   - Orchestrator内部の動作
   - イベントタイムライン

4. **[フックシステム](./04-hook-system.md)** - イベントとフック処理の詳細
   - HookResultのアクション
   - フック実行フロー
   - コンテキスト注入・承認リクエストの処理

5. **[コントリビューションチャネル](./05-contribution-channels.md)** - プルベース集約
   - 基本的な使い方
   - ユースケース（イベント宣言、能力発見、メトリクス）

6. **[デバッグとトレーシング](./06-debugging.md)** - デバッグ方法とツール
   - ログレベルの設定
   - セッション状態の確認
   - イベントトレーシング
   - トラブルシューティング

7. **[コンポーネントライフサイクル](./07-component-lifecycle.md)** - 各コンポーネントの生成から破棄まで
   - AmplifierSessionのライフサイクル
   - 各コンポーネントの詳細ライフサイクル
   - 完全なライフサイクル図

8. **[CLIエージェント統合](./08-cli-agent-integration.md)** - ファイル編集とコマンド実行の管理
   - ツールモジュールによる実行管理
   - セキュリティフックによる制御
   - ApprovalSystemの実装
   - 完全なCLIエージェント設定例

## モジュール実装例

具体的なモジュールの実装例は [`../module-examples/`](../module-examples/) にあります：

- [Provider実装例](../module-examples/provider-example.md) - LLMプロバイダーの実装
- [Tool実装例](../module-examples/tool-example.md) - ツールモジュールの実装
- [Orchestrator実装例](../module-examples/orchestrator-example.md) - 実行ループの実装
- [Context Manager実装例](../module-examples/context-example.md) - コンテキスト管理の実装
- [Hook実装例](../module-examples/hook-example.md) - フックモジュールの実装

## クイックスタート

### 初めて読む場合

1. **[開発者向けスタートガイド](./00-getting-started.md)** から開始
   - 実際のコードを書きながら理解
   - 3つの発火ポイントを追跡
   
2. **[概要](./01-overview.md)** でアーキテクチャ全体を理解

3. **[コンポーネントライフサイクル](./07-component-lifecycle.md)** で各コンポーネントの生成から破棄までを追跡

4. **[実行フロー](./03-execution-flow.md)** で実際の動作を確認

### CLIエージェントを構築する場合

1. **[CLIエージェント統合](./08-cli-agent-integration.md)** で全体像を理解
2. [Tool実装例](../module-examples/tool-example.md)でBash/Filesystem/Edit Toolを確認
3. [Hook実装例](../module-examples/hook-example.md)でSecurity/Approval Hookを実装

### モジュールを実装する場合

1. [モジュール実装例](../module-examples/)で具体的な実装を確認
2. [起動フロー](./02-startup-flow.md)でモジュールのロード過程を理解
3. プロトコル定義（`amplifier_core/interfaces.py`）を参照

### デバッグする場合

[デバッグとトレーシング](./06-debugging.md)でログ設定やトレーシング方法を確認

## コード参照

各ドキュメントでは、該当するコードの場所を以下の形式で記載しています：

- `ファイル名:行番号` - 例：`session.py:28-82`
- これにより、実際のコードとドキュメントを照らし合わせて読むことができます

## 推奨される読み方

### パターン1: 開発者視点（実際に動かしながら理解）

```
00-getting-started.md（Pythonスクリプトを作成・実行）
    ↓
07-component-lifecycle.md（各コンポーネントの生成を追跡）
    ↓
08-cli-agent-integration.md（実際のCLIエージェントを構築）
    ↓
module-examples/（カスタムモジュールを実装）
```

### パターン2: アーキテクト視点（設計を理解）

```
01-overview.md（全体設計）
    ↓
02-startup-flow.md（モジュール構成）
    ↓
04-hook-system.md（拡張メカニズム）
    ↓
05-contribution-channels.md（モジュール間通信）
```

### パターン3: CLIエージェント開発者視点

```
00-getting-started.md（基本動作の確認）
    ↓
08-cli-agent-integration.md（CLIエージェントの全体像）
    ↓
module-examples/tool-example.md（ツール実装）
    ↓
module-examples/hook-example.md（セキュリティ実装）
```

### パターン4: デバッガー視点（問題解決）

```
00-getting-started.md（基本動作の確認）
    ↓
07-component-lifecycle.md（どこで何が起こるか）
    ↓
06-debugging.md（デバッグ手法）
```
