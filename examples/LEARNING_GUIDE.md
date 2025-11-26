# Amplifier Core 学習ガイド

このガイドでは、Amplifier Coreの各コンポーネントを段階的に学んでいきます。

## アーキテクチャ概要

```
┌─────────────────────────────────────────────────────────────┐
│                     AmplifierSession                        │
│  (メインエントリーポイント - セッションライフサイクル管理)      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    ModuleCoordinator                        │
│  (インフラストラクチャハブ - モジュール間の調整)              │
│                                                             │
│  マウントポイント:                                          │
│  ├── orchestrator (single) : エージェントループ制御          │
│  ├── context (single)      : 会話履歴管理                   │
│  ├── providers (multi)     : LLMバックエンド                │
│  ├── tools (multi)         : エージェント機能               │
│  └── hooks (built-in)      : イベントシステム               │
└─────────────────────────────────────────────────────────────┘
```

## 学習ステップ

### Step 1: 基本構造の理解
**目標**: AmplifierSession, ModuleCoordinator, HookRegistryの基本的な動作を理解する

**学ぶこと**:
- セッションの作成とライフサイクル
- Coordinatorへのモジュールのマウント
- 基本的なイベントの発行と受信

**ディレクトリ**: `step1-basics/`

---

### Step 2: Providerの実装
**目標**: LLMプロバイダーの仕組みを理解し、モックプロバイダーを実装する

**学ぶこと**:
- Providerプロトコルの理解
- ChatRequest / ChatResponse の構造
- プロバイダーのマウント方法

**ディレクトリ**: `step2-provider/`

---

### Step 3: Toolの実装
**目標**: エージェントが使用できるツールを実装する

**学ぶこと**:
- Toolプロトコルの理解
- ToolCall / ToolResult の構造
- 複数ツールのマウント

**ディレクトリ**: `step3-tool/`

---

### Step 4: Orchestratorの実装
**目標**: エージェントループを制御するOrchestratorを実装する

**学ぶこと**:
- Orchestratorプロトコルの理解
- プロンプト実行フロー
- プロバイダーとツールの連携

**ディレクトリ**: `step4-orchestrator/`

---

### Step 5: ContextManagerの実装
**目標**: 会話履歴を管理するContextManagerを実装する

**学ぶこと**:
- ContextManagerプロトコルの理解
- メッセージの追加と取得
- コンパクション（要約）の仕組み

**ディレクトリ**: `step5-context/`

---

### Step 6: Hookシステムの活用
**目標**: イベントシステムを使った拡張性を理解する

**学ぶこと**:
- HookRegistryの使い方
- イベントハンドラーの登録
- HookResultによるフロー制御（deny, modify, inject_context）
- 標準イベント一覧

**ディレクトリ**: `step6-hooks/`

---

### Step 7: 統合 - 完全なエージェント
**目標**: 全コンポーネントを統合して動作するエージェントを構築する

**学ぶこと**:
- 設定ファイルによるモジュール構成
- ModuleLoaderによる動的ロード
- 実用的なエージェントパターン

**ディレクトリ**: `step7-integration/`

---

## 各ステップの実行方法

```bash
# 例: Step 1を実行
cd examples/step1-basics
python app.py
```

## コンポーネント関係図

```
実行フロー:
session.execute(prompt)
    │
    ▼
orchestrator.execute()
    │
    ├──▶ hooks.emit("prompt:submit")
    │
    ├──▶ context.get_messages()
    │
    ├──▶ provider.complete(request)
    │       │
    │       ├──▶ hooks.emit("provider:request")
    │       └──▶ hooks.emit("provider:response")
    │
    ├──▶ [ツールコールがあれば]
    │       │
    │       ├──▶ hooks.emit("tool:pre")
    │       ├──▶ tool.execute(input)
    │       └──▶ hooks.emit("tool:post")
    │
    └──▶ hooks.emit("prompt:complete")
```

## 必須 vs オプション

| コンポーネント | 必須? | 説明 |
|--------------|-------|------|
| Orchestrator | 必須 | 実行戦略を決定 |
| ContextManager | 必須 | 会話履歴を保持 |
| Provider | 必須 | LLM呼び出しに必要 |
| Tool | オプション | エージェント機能を拡張 |
| Hook | オプション | 観測性・拡張性を提供 |

## 参考ドキュメント

- `/docs/code-reading/00-getting-started.md` - コードリーディングガイド
- `/amplifier_core/interfaces.py` - 全プロトコル定義
- `/amplifier_core/models.py` - データ構造
- `/amplifier_core/events.py` - 標準イベント一覧
