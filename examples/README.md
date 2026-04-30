# examples

`nike-skills` ワークフローの完成形を示す参考用サンプル。実装は存在しません。

## 含まれるサンプル

| サンプル | 概要 | 含まれる artifact |
|---------|------|------------------|
| [`url-shortener/`](url-shortener/) | URL 短縮サービス (3 FR / 8 AC) | requirements.md / basic-design.md / detailed-design.md / implementation-log.md / verification-report.md |

## 使い方

設計書の書き方に迷ったら、これらを参照してフォーマットを真似してください。各ファイルは:

- `nike init <slug>` で生成されるテンプレートを実際に埋めた状態
- `nike validate <slug>` で `status: ok` を返す（リポジトリのルートで `cp -r examples/url-shortener docs/design/` してから実行）
- `nike parse-requirements` / `nike impl-init` / `nike verify-init` の入力として動作する

## 注意

- 参照されるファイルパス（`src/routes/links.ts` 等）は架空です
- コミット SHA・テスト件数・タイムスタンプは説明用のダミー値です
- 実際にこの機能を実装したい場合は、要件定義から自分のプロジェクトに合わせて書き直してください
