# 基本設計: {{FEATURE_NAME}}

最終更新: {{DATE}}
関連: [requirements.md](./requirements.md)

## 1. アーキテクチャ概要
```mermaid
graph TB
  Client --> API
  API --> Service
  Service --> DB[(DB)]
```

## 2. コンポーネント
### <コンポーネント名>
- 責務:
- 入力:
- 出力:
- 依存:

## 3. データフロー
### シナリオ: <名前>
```mermaid
sequenceDiagram
  participant U as User
  participant A as API
  U->>A: request
  A-->>U: response
```

## 4. データモデル
```mermaid
erDiagram
  ENTITY {
    string id
  }
```

## 5. 外部インターフェース
- 

## 6. エラー処理方針
- 

## 7. 設計判断ログ
| # | 判断 | 採用案 | 却下案 | 理由 |
|---|------|-------|-------|------|
