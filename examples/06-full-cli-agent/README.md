# Example 06: 完全なCLIエージェント

これまでの要素を統合した、実用的なCLIエージェントのサンプルです。

## 学べること

1. **完全な統合**
   - Provider (LLM風の応答)
   - Tools (Bash, Filesystem, Edit)
   - Hooks (Logging, Security, Approval)
   - Context Management

2. **実際のユースケース**
   - ファイル操作
   - コマンド実行
   - セキュリティ制御
   - ユーザー承認

3. **プロダクションパターン**
   - エラーハンドリング
   - ロギング
   - セキュリティベストプラクティス

## ファイル構成

```
06-full-cli-agent/
├── README.md          # このファイル
└── app_standalone.py  # 統合デモ
```

## 実行方法

```bash
cd examples/06-full-cli-agent
python3 app_standalone.py
```

## アーキテクチャ概要

```
User Prompt
    ↓
AmplifierSession
    ↓
Orchestrator (loop)
    ├→ Provider (LLM)
    │   └→ ToolCall or Text
    ├→ Tools
    │   ├→ BashTool
    │   ├→ FilesystemTool
    │   └→ EditTool
    └→ Hooks
        ├→ LoggingHook (観測)
        ├→ SecurityHook (ブロック)
        └→ ApprovalHook (承認)
```

## 次のステップ

これで基本的なAmplifier Coreの仕組みを学びました：

1. **実際のamplifier-coreを使う**
   - 依存関係をインストール
   - 実際のプロバイダーモジュールを使用
   - カスタムモジュールを実装

2. **ドキュメントを読む**
   - [コードリーディングガイド](../../docs/code-reading/)
   - [モジュール実装例](../../docs/module-examples/)

3. **カスタマイズ**
   - 独自のToolを実装
   - 独自のHookを追加
   - 独自のOrchestratorを作成
