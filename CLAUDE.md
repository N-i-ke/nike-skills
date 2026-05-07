# CLAUDE.md

このファイルは、このリポジトリで作業する Claude Code セッション向けのオリエンテーション。

## 何のプロジェクトか

Claude Code 用プラグイン `nike-skills`。設計 → 実装 → 検証 → PR レビュー → 調査 のソフトウェア開発ワークフローを支援する 5 つの Skill と、決定的処理を肩代わりする `nike` CLI を提供する。AI 往復コール数とトークン消費を抑えることが設計目標。

詳細は [`README.md`](README.md) を参照。

## 暗黙の契約（壊すと壊れる）

### 1. nike.py ↔ templates ↔ SKILL.md の三点整合

3 つは独立したファイルだが、内容は密結合している。1 つを変えるなら他の 2 つを必ず確認する。

| 触る対象 | 連動して見る場所 |
|---------|----------------|
| `scripts/nike.py` のサブコマンド追加・変更 | `skills/*/SKILL.md` の CLI 利用説明、`README.md` のサブコマンド表、`scripts/tests/test_nike.py` |
| `scripts/templates/*.md` の見出し変更 | `nike.py` の正規表現（特に `parse_requirements_md`）、SKILL.md の手順説明 |
| `skills/*/SKILL.md` のフォーマット要求 | `templates/` の対応箇所、`nike.py` のパーサ |

### 2. `parse_requirements_md` の正規表現と requirements.md テンプレートの暗黙契約

`scripts/nike.py` の `parse_requirements_md` は以下のフォーマットを前提に正規表現で抽出している:

```markdown
## 4. 機能要件        ← 「機能要件」見出し（番号は任意）
### FR-01: <name>     ← FR-連番、コロンの後に名前
**説明**: <一文>

**受け入れ基準**:
- Given <前提>, When <操作>, Then <結果>   ← 一行で。区切りは , ， 、
```

このフォーマットを崩すと:
- `nike parse-requirements` が空の配列を返す
- `nike impl-init` が空の task list を生成する
- `nike verify-init` が AC 表に「未記載」を吐く
- 結果として 4 つの Skill すべてが下流で機能しなくなる

テンプレートを変える場合は、必ず `scripts/tests/test_nike.py::TestParseRequirements` をローカルで実行し、新フォーマットでも抽出できることを確認する。

### 3. JSON 出力契約

`nike` CLI は全サブコマンドで JSON を stdout に出力する。Skill 側がこれを `Bash` ツールで受け取り JSON.parse して使う前提。エラー時も JSON 構造を保つ（`{"error": "..."}` 形式）。`print()` で生文字列を吐かないこと。

### 4. 終了コード

- `0`: 成功
- `1`: 回復可能なエラー（ファイル未存在など。stdout に JSON エラー）
- `2`: コマンド失敗（`checks` でテスト落ち等）

## ローカル開発

### テスト実行

```bash
python3 -m unittest discover -s scripts/tests -v
```

stdlib のみで動くため `pytest` 等のインストール不要。

### CLI 動作確認

```bash
# 一時ディレクトリで一通り回す
TMP=$(mktemp -d) && cd "$TMP"
python3 /path/to/scripts/nike.py init demo --name "デモ"
python3 /path/to/scripts/nike.py status
```

### CI

`.github/workflows/test.yml` が push / PR で発火し、Python 3.9〜3.12 マトリックスで unittest + JSON manifest 検証 + `--help` スモークテストを実行する。

## ワークフロー

### コミット

- `Co-Authored-By: Claude` 行は **付けない**（リポジトリオーナーの方針）
- メッセージは日本語可。何を変えたか + なぜを書く。コミット粒度は「テスト + CI」「Skill 追加」のような論理単位

### PR

`main` への直接 push は harness ポリシーで拒否される。常にフィーチャーブランチを切って PR 経由でマージする:

```
git checkout -b <type>/<short-name>
# ... commit
git push -u origin <branch>
gh pr create --base main --head <branch> --title "..." --body "..."
gh pr merge <num> --merge --delete-branch
```

ブランチ命名規則: `feat/`, `fix/`, `chore/`, `docs/`, `refactor/`, `test/`。

### 履歴の経緯（豆知識）

リポジトリ初期化時に Co-Authored-By 付きコミットを誤って main に push した経緯がある。その後、書き換えた履歴を `init/skills` ブランチに作り、`git merge -s ours main --allow-unrelated-histories` で不整合履歴をリンクして PR #1 でマージした。`git log --graph` で2系統の履歴が見えるのはこの理由。改めて main を rewrite する必要はない。

## バージョニング

`.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の `version` を、機能追加で minor / 重大変更で major / 軽微で patch を bump する。両方同じ数字を保つ。

## 既存 Skill / CLI の拡張ポイント（思い出した時の参考）

- `nike.py`: 新サブコマンドは `cmd_*` 関数 + `argparse` の `add_parser` ペアで追加
- `templates/`: 新テンプレ追加は `render_template` で `{{KEY}}` 変数を入れる
- 新 Skill 追加: `skills/<name>/SKILL.md`（YAML frontmatter で `name` と `description` 必須）

## 参考

- [README.md](README.md) — ユーザー向け概要
- [scripts/nike.py](scripts/nike.py) — CLI 本体
- [scripts/tests/test_nike.py](scripts/tests/test_nike.py) — 入出力契約のリビングドキュメント
