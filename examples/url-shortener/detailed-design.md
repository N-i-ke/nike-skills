# 詳細設計: URL 短縮サービス

最終更新: 2026-04-30
関連: [basic-design.md](./basic-design.md)

## 1. ファイル構成
```
src/
├── routes/links.ts                          新規 — POST/GET API + リダイレクト
├── services/shortener.ts                    新規 — ID 生成・重複検出
├── repos/links.ts                           新規 — links テーブル CRUD
├── types/link.ts                            新規 — Link ドメイン型
└── db/migrations/
    └── 20260430_create_links.ts             新規 — links テーブル定義
src/server.ts                                変更 — ルート登録
```

## 2. クラス・関数仕様

### `src/services/shortener.ts`
#### `shorten(userId: number, url: string): Promise<Link>`
- 説明: URL を短縮し、Link オブジェクトを返す
- パラメータ:
  - `userId`: DB の users.id
  - `url`: HTTP/HTTPS URL (それ以外は `InvalidUrlError`)
- 戻り値: `Link { id, url, createdAt }`
- 例外: `InvalidUrlError` (URL 形式不正), `ConflictError` (3 回リトライ後も衝突)

#### `generateId(): string`
- 説明: 7 文字の base62 文字列を返す (a-zA-Z0-9)
- 戻り値: 7 文字の string

### `src/repos/links.ts`
#### `findByUserAndUrl(userId, url): Promise<Link | null>`
#### `insert(id, userId, url): Promise<Link>`
#### `findById(id): Promise<Link | null>`
#### `listByUser(userId): Promise<Link[]>` 新しい順

## 3. API 仕様

### POST /api/links
- 認証: 必須
- リクエスト: `{ "url": "https://example.com/long" }`
- レスポンス (201):
  ```json
  {
    "id": "abc1234",
    "shortUrl": "https://s.example.com/abc1234",
    "url": "https://example.com/long",
    "createdAt": "2026-04-30T18:00:00Z"
  }
  ```
- エラー: 400 (URL 不正), 401 (未認証)

### GET /api/links
- 認証: 必須
- レスポンス (200): `Array<{ id, url, shortUrl, createdAt }>` 新しい順
- エラー: 401

### GET /:id
- 認証: 不要
- レスポンス (301): `Location: <元URL>`
- エラー: 404

## 4. DB スキーマ
```sql
CREATE TABLE links (
  id VARCHAR(7) PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_links_user_id_created ON links(user_id, created_at DESC);
CREATE UNIQUE INDEX idx_links_user_url ON links(user_id, url);
```

## 5. テスト観点
- ユニット: `generateId` が 7 文字 base62 を返す / `shorten` が既存を返す
- 統合: API → Service → Repo → DB のフルフロー (テスト用 PostgreSQL)
- E2E: 認証 → 作成 → リダイレクト → 履歴取得の通しシナリオ

## 6. 実装ステップ
1. マイグレーション作成 + 適用 (`db/migrations/20260430_create_links.ts`)
2. `types/link.ts` と `repos/links.ts` (リポジトリ層)
3. `services/shortener.ts` (ID 生成・重複検出)
4. `routes/links.ts` (API 3 エンドポイント、open redirect 対策)
5. `server.ts` でルート登録
6. ユニット・統合テスト追加
