# 実装ログ: URL 短縮サービス

最終更新: 2026-04-30
ステータス: 完了

## 実装サマリ
URL 短縮 + リダイレクト + 履歴の 3 エンドポイントと、`links` テーブル + マイグレーションを追加。base62 7 文字 ID 生成と衝突時 3 回リトライを実装。

## 変更ファイル
| ファイル | 種別 | 概要 |
|---------|------|------|
| src/routes/links.ts | 新規 | POST/GET API + リダイレクトルート |
| src/services/shortener.ts | 新規 | ID 生成・重複検出・リトライ |
| src/repos/links.ts | 新規 | links テーブル CRUD |
| src/types/link.ts | 新規 | Link ドメイン型 |
| src/db/migrations/20260430_create_links.ts | 新規 | links テーブル定義 |
| src/server.ts | 変更 | ルート登録 |

## 実装タスク状況
- [x] FR-01: URL 短縮
- [x] FR-02: 短縮 URL リダイレクト
- [x] FR-03: 履歴一覧

## 設計との差分
- detailed-design.md ではリダイレクト時の URL スキーム検証は API ルートでのみ行う想定だったが、open redirect 対策として **`shorten` の入口でも** `http://` または `https://` のみ許可するチェックを追加した。理由: 古い DB データに不正 URL が混入している場合のフォールバック保護。requirements.md の非機能要件「open redirect 対策」を反映する妥当な拡張。

## 既知の制限・TODO
- レート制限はスコープ外として未実装。本番投入前に Express rate-limit ミドルウェアで保護する想定 (別 feature `rate-limit` で対応予定)
- 短縮 URL のドメイン (`s.example.com`) は環境変数 `SHORT_DOMAIN` から取得、未設定時は `http://localhost:3000`

## 検証用メモ (verify Skill 向け)
- 起動コマンド: `pnpm dev`
- マイグレーション: `pnpm migrate:latest`
- テストコマンド: `pnpm test src/services/shortener.test.ts src/routes/links.test.ts`
- 統合テスト: `pnpm test:integration`
- 手動確認手順:
  1. `pnpm migrate:latest` でテーブル作成
  2. `pnpm dev` でサーバー起動
  3. `curl -X POST http://localhost:3000/api/links -H "Cookie: session=..." -d '{"url":"https://example.com/long"}'` で短縮
  4. レスポンスの `shortUrl` をブラウザで開いて元 URL に飛ぶことを確認
  5. `curl http://localhost:3000/api/links -H "Cookie: ..."` で履歴を確認
