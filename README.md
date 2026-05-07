# nike-skills

設計 → 実装 → 検証、および調査 のソフトウェア開発ワークフローを支援する Claude Code Skill 集。

決定的な処理 (テンプレート生成・要件パース・コマンド検出・チェック実行・スキャナ実行) は `nike` CLI に委譲し、AI は内容の充填と判断に集中することで **AI 往復コール数とトークン消費を抑える** 設計。

## 含まれる Skill

| Skill | 役割 | 主な成果物 |
|-------|------|-----------|
| [`design`](skills/design/SKILL.md) | 要件定義・基本設計・詳細設計を作成 | `docs/design/<feature>/{requirements,basic-design,detailed-design}.md` |
| [`implement`](skills/implement/SKILL.md) | 設計ドキュメントに基づき実装 | ソースコード、`docs/design/<feature>/implementation-log.md` |
| [`verify`](skills/verify/SKILL.md) | 完成した機能を自動検証 | `docs/design/<feature>/verification-report.md` |
| [`pr-review`](skills/pr-review/SKILL.md) | ローカル差分 / GitHub PR をマージ前にレビュー | チャット出力、必要に応じ `docs/reviews/<slug>/report.md` |
| [`investigate`](skills/investigate/SKILL.md) | 不具合・脆弱性の調査 (根本原因解析、セキュリティレビュー) | `docs/investigations/<slug>/report.md` |

## nike CLI

すべての Skill は `scripts/nike.py` を共通インフラとして使う。標準ライブラリのみで動作 (Python 3.9+)。全サブコマンドは JSON を出力するため、AI は 1 回の Bash 呼び出しで構造化データを受け取れる。

```
nike init <slug> [--name "<人間向け名>"] [--force]
nike status [<slug>]
nike parse-requirements <slug>
nike validate <slug> [--strict]
nike impl-init <slug> [--force]
nike verify-init <slug> [--force]
nike investigate-init <slug> [--type bug|security|both] [--title "<title>"] [--force]
nike review-context [<pr>] [--base <ref>]
nike review-init <slug> [--force]
nike detect
nike checks [--lint] [--typecheck] [--test] [--build]
nike scan [--timeout N] [--output-limit N]
```

| サブコマンド | 機械化する処理 |
|------------|--------------|
| `init` | requirements/basic-design/detailed-design テンプレ3点を一括生成 |
| `status` | feature ごとにどのフェーズが完了/欠落しているかを返す |
| `parse-requirements` | requirements.md から FR/AC を構造化 JSON で抽出 |
| `validate` | 設計ドキュメントを lint (FR/AC フォーマット崩れ・ID 重複・必須セクション欠落・cross-doc 参照) |
| `impl-init` | 要件から FR をタスク化した implementation-log.md を seed |
| `verify-init` | 要件から AC 表入りの verification-report.md を生成 |
| `investigate-init` | 調査レポート雛形 (`docs/investigations/<slug>/report.md`) を生成 |
| `review-context` | ローカル差分または GitHub PR の files/stats/commits/design_features/claude_md を JSON で集約 |
| `review-init` | 観点別セクション付きの `docs/reviews/<slug>/report.md` を生成 |
| `detect` | package.json / pyproject.toml / Cargo.toml / go.mod から lint/test/build コマンドを推定 |
| `checks` | 検出コマンドを実行し、stdout/stderr 末尾と exit code を JSON で返す |
| `scan` | 利用可能なセキュリティスキャナ (npm audit / pip-audit / cargo audit / gosec / govulncheck / semgrep / bandit / safety) を一括実行し JSON 集約 |

詳細は `scripts/nike.py --help`。

## 想定ワークフロー

```
# 1. 設計
nike init user-auth --name "ユーザー認証"
# AI が3つのテンプレを Edit で埋める (要件定義 → 基本設計 → 詳細設計)

# 2. 実装
nike impl-init user-auth     # FR をタスク化したログをseed
nike detect                  # プロジェクトのコマンドを取得
# AI が設計に沿って実装、Edit でログ更新
nike checks                  # 静的解析・テストを一括実行

# 3. 検証
nike verify-init user-auth   # AC 表入りレポートを生成
nike checks                  # 検証
# AI が AC ごとに PASS/FAIL を Edit で記入、サマリを仕上げる

# 4. 調査 (ad-hoc)
nike investigate-init search-xss --type security --title "検索フォームのXSS疑義"
nike scan                    # 利用可能なスキャナを一括実行
# AI が証拠を集めレポートを仕上げる。修正は implement Skill に引き渡す
```

各 Skill は `docs/design/<feature>/` または `docs/investigations/<slug>/` を介して成果物を引き継ぐので、別セッションで再開しても文脈が失われない。

## インストール

### プラグインとして利用する場合

```bash
# Claude Code 内で
/plugin marketplace add N-i-ke/nike-skills
/plugin install nike-skills@nike-skills
```

プラグイン環境では nike CLI のパスは `${CLAUDE_PLUGIN_ROOT}/scripts/nike.py`。

### 個別 Skill をコピーして使う場合

`skills/<skill-name>/` を `~/.claude/skills/` または `<your-project>/.claude/skills/` にコピーし、`scripts/` ディレクトリも同梱してパスを Skill から呼び出せる場所に置く。

## ディレクトリ構成

```
nike-skills/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/
│   ├── design/SKILL.md
│   ├── implement/SKILL.md
│   ├── verify/SKILL.md
│   ├── pr-review/SKILL.md
│   └── investigate/SKILL.md
├── scripts/
│   ├── nike.py
│   ├── templates/
│   │   ├── requirements.md
│   │   ├── basic-design.md
│   │   ├── detailed-design.md
│   │   ├── implementation-log.md
│   │   ├── verification-report.md
│   │   ├── review-report.md
│   │   └── investigation-report.md
│   └── tests/test_nike.py
├── examples/
│   ├── README.md
│   └── url-shortener/    完成形のサンプル feature
├── CLAUDE.md
└── README.md
```

## 完成形のサンプル

[`examples/url-shortener/`](examples/url-shortener/) に、URL 短縮サービスを題材にした 5 つの artifact (requirements / basic-design / detailed-design / implementation-log / verification-report) を完成形で置いてある。設計書の書き方に迷ったら参考にしてほしい。`nike validate url-shortener` でクリーンに通る形になっている。

## 受け入れ基準の記述ルール

`nike parse-requirements` は requirements.md から自動抽出するため、以下のフォーマットを守ること:

```markdown
## 4. 機能要件
### FR-01: <機能名>
**説明**: <一文>

**受け入れ基準**:
- Given <前提>, When <操作>, Then <結果>
- Given <前提>, When <操作>, Then <結果>
```

- 見出しレベル `###`、ID は `FR-` + 連番
- 受け入れ基準は `- Given ..., When ..., Then ...` の一行形式（区切り文字は `,` `，` `、` のいずれも可）

このフォーマットを崩すと verify Skill の AC 表自動生成が動かない。
