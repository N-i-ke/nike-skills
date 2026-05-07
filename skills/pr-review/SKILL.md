---
name: pr-review
description: ローカルブランチの差分または GitHub PR をレビューする。設計ドキュメント整合・セキュリティ・可読性・運用・拡張性・テスト網羅・CLAUDE.md 暗黙契約の各観点で指摘を生成し、チャットに出力する。許可制で `gh pr review` 経由の PR コメント投稿にも対応。差分取得・レポート雛形生成は nike CLI に委譲する。ユーザーが「PR レビュー」「セルフレビュー」「PR #N をレビュー」と依頼した場合に使用。
---

# pr-review — マージ前の PR レビュー

## このスキルの役割

ローカルブランチの差分（セルフレビュー）または GitHub PR をレビューし、観点抜けを防ぐ。指摘はチャットに出力し、ユーザーが明示的に許可した場合のみ GitHub PR にコメントとして投稿する。

成果物（小規模 PR の場合）はチャットメッセージのみ。大規模 PR や明示指示時は `docs/reviews/<slug>/report.md` を併用する。

## nike CLI の活用

CLI のパスはプラグイン環境で `${CLAUDE_PLUGIN_ROOT}/scripts/nike.py`、ローカルで `scripts/nike.py`。

| やりたいこと | コマンド | 効果 |
|------------|---------|------|
| 差分・PR メタの取得 | `python3 <nike.py> review-context [<pr>] [--base <ref>]` | files / stats / commits / design_features / claude_md を JSON で返す |
| レポート雛形生成 | `python3 <nike.py> review-init <slug> [--force]` | `docs/reviews/<slug>/report.md` を観点別セクション付きで生成 |
| 設計ドキュメント有無確認 | `python3 <nike.py> status <slug>` | feature の有無確認 |
| 要件構造化（整合チェック用） | `python3 <nike.py> parse-requirements <slug>` | FR/AC を JSON で取得 |
| 静的解析・テストの実行 | `python3 <nike.py> checks` | レビュー時に念のため CI 同等のチェックを走らせる |

## レビュー観点

| # | 観点 | 関連 FR | 主な確認内容 |
|---|------|--------|-------------|
| 1 | ドキュメント整合 | FR-02 | requirements.md の FR を実装が満たしているか / 設計外の追加が無いか |
| 2 | セキュリティ | FR-03 | 認証情報のハードコード、コマンド実行・SQL 文字列結合の入力検証、API ハンドラの認可 |
| 3 | 可読性・保守性 | FR-04 | 命名・関数サイズ・責務の単一性・コメント |
| 4 | テスト網羅 | FR-04 | 新規 public 関数に対応するテスト追加の有無 |
| 5 | 運用面 | FR-05 | エラーハンドリング、例外の握りつぶし、ログ、マジックナンバー |
| 6 | 拡張性・破壊的変更 | FR-05 | 公開 API / CLI / 設定の互換性、マイグレーション戦略 |
| 7 | CLAUDE.md 暗黙契約 | FR-06 | プロジェクト直下 CLAUDE.md に書かれた規約・禁止事項に違反していないか |

各指摘は **観点 / 重要度 (blocker / major / minor / nit) / ファイル:行 / 現状 / 提案** を含める。

## 使い方

### ステップ 1: レビュー対象の特定

ユーザーが PR 番号 / URL を指定したら PR モード、指定が無ければローカルモード（セルフレビュー）。

```bash
# ローカルモード (セルフレビュー)
python3 <nike.py> review-context

# PR モード
python3 <nike.py> review-context 42
python3 <nike.py> review-context https://github.com/owner/repo/pull/42
```

返ってきた JSON の `mode`, `base`, `head`, `pr`, `stats.files_changed` を確認する。

**入力不足時の対応:**

| 状態 | 推奨アクション |
|------|--------------|
| `error: not a git repository` | git リポジトリ外で起動された。ユーザーに状況を確認 |
| `error: gh required for PR mode` | `gh` 未インストール / 未認証。ユーザーに案内 |
| `error: pr not found` | PR 番号誤り / 権限不足。ユーザーに確認 |

### ステップ 2: レポート方式の決定

`stats.files_changed` を見る:

- **≦ 50 ファイル**: チャット直接出力で十分。レポートファイルは作成しない。
- **\> 50 ファイル または明示指示**: `nike review-init <slug>` でレポートファイルを生成し、Edit で埋める。

スラグはユーザーと合意して決める（例: `pr-42-2026-05-08`, `selfreview-feat-x-2026-05-08`）。

### ステップ 3: 前提資料の読込

`review-context` の出力を見て、以下があれば読み込む:

- `design_features` に slug が入っていれば: `nike status <slug>` と `nike parse-requirements <slug>` で設計と AC を取得（FR-02 観点）
- `claude_md` が `"CLAUDE.md"` なら: `CLAUDE.md` を Read（FR-06 観点）
- `commits` をループしてコミットメッセージを確認（CLAUDE.md にコミット規約があれば違反を検出）

### ステップ 4: 観点別チェック

§レビュー観点 の 7 項目を順番に検査する。差分が大きい場合はファイルを先に概観し、優先度の高いものから読む。

差分の現物確認には以下を使う:

```bash
# ローカル
git diff <base_sha>...<head_sha> -- <file>

# PR
gh pr diff <num> -- <file>
```

`review-context` が返した base/head の SHA を使えば一貫性が保てる。

### ステップ 5: 指摘の集約

各指摘について以下を構造化して書く:

```
- [blocker] scripts/nike.py:142 (セキュリティ)
  現状: ユーザー入力をそのまま subprocess.run の shell=True に渡している
  提案: shell=False にしてリスト引数で渡すか、入力を validate する
```

重要度の目安:
- **blocker**: マージ前に必ず直す（セキュリティ脆弱性、致命的なバグ、設計違反）
- **major**: できれば直す（保守性低下、テスト欠如、運用リスク）
- **minor**: 望ましい改善（命名、ロジック整理）
- **nit**: 好みの範囲（typo、フォーマット、コメント微修正）

### ステップ 6: レポート出力

**チャット直接出力** が既定:

```markdown
## PR Review: <タイトル / モード>
**総合判定**: APPROVE / COMMENT / REQUEST_CHANGES
**理由**: ...

### 強み
- ...

### 指摘 (合計 N 件: blocker x, major x, minor x, nit x)

#### blocker
- ...

#### major
- ...

(以下重要度順)

### 次のアクション
- ...
```

**ファイル併用** の場合は `nike review-init <slug>` でテンプレ生成 → Edit で観点別セクションを埋める → チャットにはサマリ + ファイルパスを案内。

### ステップ 7: GitHub への投稿（オプション・許可制）

ユーザーが明示的に「投稿してほしい」と言わない限り、`gh pr review` / `gh pr comment` は **絶対に** 実行しない。

許可された場合のフロー:

1. 投稿モードを確認する: `COMMENT` (情報共有) / `APPROVE` (承認) / `REQUEST_CHANGES` (修正要求)
2. 投稿先 PR 番号を確認する（`review-context` の `pr.number` を使う）
3. レポート本文を一時ファイルに書き出すか、レポートファイルが既にあればそれを使う
4. 実行:

```bash
# COMMENT モード
gh pr review <num> --comment -F <report-or-tempfile>

# APPROVE モード（明示許可があった場合のみ）
gh pr review <num> --approve -F <report-or-tempfile>

# REQUEST_CHANGES モード（誤検知のリスクが高いため特に慎重に）
gh pr review <num> --request-changes -F <report-or-tempfile>
```

5. 投稿成功 / 失敗をチャットで報告。失敗時は `error.detail` をユーザーに伝える。

### ステップ 8: 仕上げ

- 投稿があった場合、レポートファイルの「投稿履歴」セクションを Edit で更新
- 検出した認証情報（例: API キーが見つかった等）はレポートに **マスクして** 記載。生の値はチャット・ファイルに残さない

## 進め方の原則

- **既定はチャット出力のみ**。レポートファイル作成も GitHub 投稿もユーザー指示があったときだけ。
- **CLI に任せる**。差分取得・PR メタ取得・レポート雛形生成は `nike review-context` / `review-init` を使い、AI トークンは観点判断と表現に使う。
- **指摘は具体的に**。「リファクタしてほしい」ではなく「`X 関数の中に副作用が混在しているので Y を切り出すと良い`」のように、ファイル:行と提案を必ず添える。
- **観点抜けを優先**。表現の磨きこみよりも、漏れを減らすことに時間を使う。
- **誤投稿しない**。`gh pr review` の `--approve` や `--request-changes` は不可逆性が高いため、必ず明示確認を取る。
- **巨大 PR は分割を提案**。100 ファイル超ならファイル種別ごとに分割レビューする方針をユーザーに提案する。
- 完了報告では「総合判定」「主要な blocker / major」「次のアクション」「（投稿していれば）投稿先 URL」を簡潔に伝える。
