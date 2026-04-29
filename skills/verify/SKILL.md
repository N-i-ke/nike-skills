---
name: verify
description: implement Skill で実装された機能が要件を満たしているかを自動検証する。要件定義の受け入れ基準・テスト・型チェック・リント・手動確認手順を体系的に実行し、`docs/design/<feature>/verification-report.md` にレポートを出力する。ユーザーが「検証して」「テストして」「動作確認して」と依頼した場合に使用。決定的処理 (要件パース・コマンド検出・チェック実行・レポート雛形生成) は nike CLI に委譲する。
---

# verify — 完成機能の自動検証

## このスキルの役割

`docs/design/<feature-slug>/` の設計ドキュメントと implementation-log.md を読み、実装が要件を満たしているか体系的に検証する。検証結果は `verification-report.md` に出力し、未充足項目があれば実装担当（ユーザーまたは `implement` Skill）にフィードバックする。

## nike CLI の活用

CLI のパスはプラグイン環境で `${CLAUDE_PLUGIN_ROOT}/scripts/nike.py`、ローカルで `scripts/nike.py`。

| やりたいこと | コマンド | 効果 |
|------------|---------|------|
| feature 状況確認 | `python3 <nike.py> status <slug>` | 何が揃っていて何が無いかを JSON で取得 |
| 要件構造化 | `python3 <nike.py> parse-requirements <slug>` | FR/AC を JSON で取得（PASS/FAIL 判定の根拠） |
| レポート雛形生成 | `python3 <nike.py> verify-init <slug>` | AC 表入りの verification-report.md を作成 |
| プロジェクト検出 | `python3 <nike.py> detect` | lint/typecheck/test/build コマンドを推定 |
| チェック一括実行 | `python3 <nike.py> checks` | 全チェックを実行し JSON で結果集約 (truncated 出力付き) |

## 検証する観点

| カテゴリ | 内容 | 失敗時の扱い |
|---------|------|-------------|
| 静的解析 | 型チェック / リント / フォーマット | 即時報告、修正提案 |
| ユニットテスト | 既存および新規テストの実行 | 失敗テストを特定 |
| 統合テスト | 要件をまたぐ振る舞い | シナリオ単位で報告 |
| 受け入れ基準 | requirements.md の Given/When/Then | 各項目 PASS/FAIL/N/A |
| 設計整合性 | basic/detailed-design との差分確認 | 差分を列挙 |
| 非機能要件 | 性能・セキュリティ・アクセシビリティなど | 確認可能な範囲で |

## 使い方

### ステップ 1: 入力確認

```bash
python3 <nike.py> status <slug>
```

**前提資料の不足時の対応:**

| 状態 | 推奨アクション |
|------|--------------|
| `docs/design/<feature>/` が無い | 検証範囲不明。ユーザーに確認するか、`git diff` / 直近コミットから対象を推定してよいか合意を取る |
| requirements.md が無い | 受け入れ基準が無いため PASS/FAIL 判定不能。implementation-log.md の内容だけ検証する旨を明示 |
| implementation-log.md が無い | 検証コマンド不明。`nike detect` の結果を使う旨をレポートに明記 |

入力不足の場合、レポート先頭に **「前提資料の不足」** セクションを設け、何が無かったか・どう代替したかを記録する。

### ステップ 2: レポート雛形生成

```bash
python3 <nike.py> verify-init <slug>
```

これで `verification-report.md` が AC 表 (NOT_VERIFIED で初期化) 入りで生成される。git のコミット SHA も自動で記録される。

### ステップ 3: 検証計画の作成

```bash
python3 <nike.py> parse-requirements <slug>
```

返ってきた FR/AC それぞれに対して、検証手段 (ユニットテスト / E2E / 手動 / N/A) を決める。`implementation-log.md` の「検証用メモ」にテストコマンドが書かれていればそれを優先。書かれていなければ `nike detect` の結果から推定。

TaskCreate で各検証項目をタスク化すると進捗管理が楽。

### ステップ 4: 静的解析・テストの実行

```bash
python3 <nike.py> checks
```

これで lint / typecheck / test / build が一括実行され、結果が JSON で返る。`results[].passed` / `stdout_tail` / `stderr_tail` を確認。

特定のチェックだけ走らせたい場合は `--lint` `--typecheck` `--test` `--build` を組み合わせる。

```bash
python3 <nike.py> checks --lint --typecheck   # 軽いものだけ先に
python3 <nike.py> checks --test              # その後テスト
```

実装ログに固有のテストコマンド（例: `pnpm test src/auth`）が書かれている場合、それは `nike checks` ではなく直接 Bash で実行する（CLI の検出はプロジェクト全体のコマンドを返すため）。

### ステップ 5: 受け入れ基準の判定

`verification-report.md` の AC 表（NOT_VERIFIED 初期状態）を Edit で更新する。各 AC に対して:

- **PASS**: 自動テストで担保されている、または手動確認で動作を確認できた
- **FAIL**: テストが落ちた、または期待通りに動かない
- **N/A**: 検証対象外（スコープ外、他チーム責務など）
- **NOT_VERIFIED**: 自動も手動も実行不能。理由を必ず備考欄に記載

UI を伴う AC は、可能なら開発サーバー (`detect` の `commands.dev`) を起動して動作を確認する。起動できない場合は明示的に NOT_VERIFIED とする。

### ステップ 6: 設計整合性チェック

- 実装されたファイルが detailed-design.md のファイル構成と一致しているか
- 関数シグネチャや API スキーマが設計と一致しているか
- implementation-log.md の「設計との差分」セクションに、未承認の差分が入っていないか

差分があれば「設計との差分」セクションに列挙し、それが意図的か否か判別する。

### ステップ 7: レポート仕上げ

`verification-report.md` の以下を Edit で埋める:

- **総合判定**: ✅ PASS / ⚠️ PARTIAL / ❌ FAIL のいずれか
- **サマリ**: 受け入れ基準の集計、静的解析・テストの結果
- **自動検証コマンドの実行結果**: `nike checks` の `results` を整形して貼る (失敗時のスニペット中心に)
- **推奨アクション**: FAIL / NOT_VERIFIED への対応案
- **次に実行すべきこと**: 例「`implement` Skill で FAIL を修正後、再 `verify`」

## 進め方の原則

- **コマンドを推測しない**。`nike detect` または implementation-log の検証用メモから実コマンドを取得する。
- **失敗を隠さない**。テストが落ちたら、それを正直にレポートに記載する。「ほぼ動いている」と曖昧にしない。
- **検証できないものは検証できないと書く**。NOT_VERIFIED を活用する。
- **修正は基本しない**。verify Skill の役割は検証とレポート。修正は `implement` Skill またはユーザーに任せる。ただし軽微な lint 修正など、ユーザーが許可した範囲なら可。
- **レポートは差分追記でなく上書きで良い**。verification-report.md は最新の検証結果を表す。過去ログが必要なら git history で追える。
- **CLI に任せられるところは任せる**。ファイル列挙・要件パース・コマンド実行は `nike` を使い、AI は判定と説明に集中する。
- 結果報告時は「総合判定」「主要な失敗項目」「次のアクション」を簡潔に口頭で伝え、詳細はレポートファイルを参照させる。
