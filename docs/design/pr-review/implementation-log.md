# 実装ログ: PR Review

最終更新: 2026-05-08
ステータス: 完了

## 実装サマリ
- nike CLI に `review-context` / `review-init` サブコマンドを追加 (差分・PR メタ取得 / レポート雛形生成)
- レビュー観点 7 種 (ドキュメント整合 / セキュリティ / 可読性 / 運用 / 拡張性 / テスト網羅 / CLAUDE.md 暗黙契約) を扱う `pr-review` Skill (`skills/pr-review/SKILL.md`) を新設
- `scripts/templates/review-report.md` を新規追加し、観点別セクション付きレポートをテンプレ化
- バージョン 0.3.0 → 0.4.0 (機能追加 minor bump)
- 53 unit/integration tests がローカルで全 pass

## 変更ファイル
| ファイル | 種別 | 概要 |
|---------|------|------|
| `scripts/nike.py` | 変更 | `cmd_review_context`, `cmd_review_init` と関連ヘルパ (`normalize_pr`, `run_git`, `run_gh`, `detect_default_branch`, `parse_numstat`, `parse_name_status`, `parse_log`, `match_features_from_paths`) を追加 |
| `scripts/templates/review-report.md` | 新規 | レポート雛形テンプレート |
| `scripts/tests/test_nike.py` | 変更 | `TestNormalizePR` / `TestParseNumstat` / `TestParseNameStatus` / `TestMatchFeaturesFromPaths` / `TestNikeReviewInit` / `TestNikeReviewContextLocal` を追加 (15 ケース) |
| `skills/pr-review/SKILL.md` | 新規 | Skill 本体 (起動方法・観点・ステップ 1〜8・進め方の原則) |
| `README.md` | 変更 | Skill 一覧に pr-review を追加、CLI コマンド表に review-context/review-init を追加、ロードマップから pr-review を削除、ディレクトリ構成に pr-review/SKILL.md と review-report.md を追加 |
| `.claude-plugin/plugin.json` | 変更 | version 0.3.0 → 0.4.0、説明文に PR レビューを追加、keywords に pr-review |
| `.claude-plugin/marketplace.json` | 変更 | 同上 |
| `CLAUDE.md` | 変更 | 「4 つの Skill」→「5 つの Skill」に更新 |

## 実装タスク状況
- [x] FR-01: レビュー対象の特定 — `cmd_review_context` の local / pr モード分岐
- [x] FR-02: 設計ドキュメントとの整合チェック — `match_features_from_paths` で feature slug を推定し、Skill 側で `nike parse-requirements` を呼ぶ運用に
- [x] FR-03: セキュリティ観点のチェック — Skill の §レビュー観点 表 + ステップ 4 で実装
- [x] FR-04: 可読性・保守性の観点 — 同上
- [x] FR-05: 運用面・拡張性の観点 — 同上
- [x] FR-06: CLAUDE.md 暗黙契約のチェック — `review-context` の `claude_md` フィールドで提示し、Skill が CLAUDE.md を Read
- [x] FR-07: レビューレポートの生成と出力 — `review-init` テンプレ + Skill のステップ 6
- [x] FR-08: GitHub への投稿（許可制） — Skill のステップ 7 (CLI 自体には投稿機能を持たせない設計判断)
- [x] FR-09: nike CLI への決定的処理の委譲 — review-context / review-init で実現

## 設計との差分

### 1. PR モードの diff 取得を `gh pr diff` から `git diff <baseRefOid>...<headRefOid>` に変更
detailed-design では `gh pr diff` を使う想定だったが、`gh pr view --json baseRefOid,headRefOid` で SHA を取得した後はローカル git で diff が取れる（fork の場合のみ追加 fetch が必要）。実装では現在のリポジトリで両 SHA が解決できる前提で git に統一し、CLI を 1 系統 (`run_git`) にまとめてシンプルにした。fork の対応はオープンイシュー扱い。

### 2. `match_features_from_paths` の閾値ロジック
detailed-design に「Jaccard 係数」と書いていたが、実装では「slug トークンの過半数がパストークンに含まれるか」というシンプルな包含率に変更。Jaccard はパストークンが多いと希釈されるため不適と判断した。テスト 3 ケースで意図通りの挙動を確認。

### 3. `gh pr review` 投稿は CLI に実装せず、Skill で gh を直接叩く設計
detailed-design ではどちらでも実装可能としていたが、投稿は不可逆操作のため Skill 側でユーザー確認を挟むフローに統一した。CLI から薄いラッパを提供するメリットが薄いため。

## 既知の制限・TODO
- **fork からの PR**: `git diff <baseSha>...<headSha>` がローカルに head SHA が無いため失敗する可能性。現状 `gh pr checkout` を促すワークアラウンドのみ。fork 対応は v0.5 以降のオープンイシュー。
- **巨大 PR の分割レビュー**: requirements.md オープンイシューの「>100 ファイル」ケースは未着手。Skill 側でユーザーに分割を提案するのみ。
- **観点の YAML 外部化**: 同じくオープンイシュー扱い。MVP では Skill に固定で観点 7 種を埋め込み。
- **`origin/HEAD` 未設定リポジトリ**: `detect_default_branch` が `main` にフォールバックする。実際の default branch が `master` 等の場合はユーザーが `--base` で明示する必要あり。

## 検証用メモ (verify Skill 向け)

### 起動コマンド
```bash
# CLI のヘルプ確認 (smoke)
python3 scripts/nike.py --help
python3 scripts/nike.py review-context --help
python3 scripts/nike.py review-init --help

# ローカルモード (このリポジトリ内で)
python3 scripts/nike.py review-context --base main

# レポート雛形生成
python3 scripts/nike.py review-init pr-review-test
ls docs/reviews/pr-review-test/
```

### テストコマンド
```bash
# 全テスト実行 (53 ケース)
python3 -m unittest discover -s scripts/tests -v

# pr-review 関連だけ
python3 -m unittest scripts.tests.test_nike.TestNormalizePR scripts.tests.test_nike.TestParseNumstat scripts.tests.test_nike.TestParseNameStatus scripts.tests.test_nike.TestMatchFeaturesFromPaths scripts.tests.test_nike.TestNikeReviewInit scripts.tests.test_nike.TestNikeReviewContextLocal -v
```

### 手動確認手順
1. このリポジトリで `python3 scripts/nike.py review-context --base main` を実行 → `mode=local`, `files` に変更ファイルが入り、`design_features` に `pr-review` が含まれることを確認
2. `python3 scripts/nike.py review-init smoke-test` → `docs/reviews/smoke-test/report.md` が生成され、観点別セクション 7 つを持つことを確認
3. SKILL.md の YAML frontmatter (`name: pr-review`, `description: ...`) が正しく書かれていることを確認
4. `nike validate pr-review` が `status: ok` を維持していること
5. `.claude-plugin/plugin.json` と `marketplace.json` の version が両方 `0.4.0` であること
