---
name: implement
description: design Skill が作成した要件定義・基本設計・詳細設計に基づいてコードを実装する。`docs/design/<feature>/` を読み、設計通りにファイル作成・コード追加・既存コード変更を行い、進捗を implementation-log.md に記録する。ユーザーが「<機能名>を実装して」「設計に沿って実装」と依頼した場合に使用。決定的処理 (要件パース・プロジェクト検出・チェック実行) は nike CLI に委譲する。
---

# implement — 設計ドキュメントに基づく実装

## このスキルの役割

`docs/design/<feature-slug>/` に保存された設計ドキュメントを読み込み、設計に沿って実装を行う。実装の意図と差分を `implementation-log.md` に記録し、後続の `verify` Skill が検証できる状態にする。

## nike CLI の活用

CLI のパスはプラグイン環境で `${CLAUDE_PLUGIN_ROOT}/scripts/nike.py`、ローカルで `scripts/nike.py`。

| やりたいこと | コマンド | 効果 |
|------------|---------|------|
| feature の状況確認 | `python3 <nike.py> status [<slug>]` | どのフェーズまで進んでいるか JSON で取得 |
| 要件を構造化抽出 | `python3 <nike.py> parse-requirements <slug>` | FR/AC 一覧を JSON で取得（タスク計画の元データ） |
| implementation-log を seed | `python3 <nike.py> impl-init <slug>` | FR からタスクリストを自動生成した雛形を作成 |
| プロジェクトのコマンド検出 | `python3 <nike.py> detect` | lint/typecheck/test/build コマンドを推定 |
| チェック実行 | `python3 <nike.py> checks [--lint --typecheck --test --build]` | 指定 (or 全て) を実行し JSON で結果集約 |

これらを使えば「設計を読む」「コマンドを推測する」のための AI 往復を減らせる。

## 使い方

### ステップ 1: 状況確認

```bash
python3 <nike.py> status <slug>
```

レスポンスから以下を判断:

- `phases.design == "complete"` → そのまま実装フェーズへ
- `phases.design == "partial"` → 設計が不完全。下記「前提不足時の対応」へ
- `phases.implementation == "exists"` → 中断/再開シナリオ。`implementation-log.md` を Read して再開地点把握

**前提ドキュメント不足時の対応:**

| 状態 | 推奨アクション |
|------|--------------|
| `docs/design/<feature>/` 自体が無い | `design` Skill を先に実行することを提案。小規模変更ならユーザー合意のうえ簡易メモのみで進めてよいか確認 |
| requirements.md のみ存在 | 受け入れ基準を実装計画に直接落とし込んでよいか確認 |
| detailed-design.md のみ欠落 | basic-design.md から実装ステップを推測してよいか確認 |

ユーザーが「設計をスキップして進めてよい」と明言した場合は、`implementation-log.md` の冒頭に **「設計ドキュメントなしで実装した範囲」** セクションを設け、実装した機能・受け入れ条件・既知の制約を記録する。

### ステップ 2: 要件パース + 設計読込

```bash
python3 <nike.py> parse-requirements <slug>
```

これで FR/AC が JSON で得られる。あわせて `basic-design.md` と `detailed-design.md` を Read。

### ステップ 3: 実装計画とログ初期化

```bash
python3 <nike.py> impl-init <slug>
```

これで `implementation-log.md` が FR をタスクリスト形式で seed された状態で作成される。

タスク管理は **TaskCreate** ツールで実施。CLI が seed したタスクを起点に、依存関係や粒度に応じて分解する。

### ステップ 4: 既存コードの調査

実装前に以下を確認:

```bash
python3 <nike.py> detect
```

これで言語・パッケージマネージャ・lint/test/build コマンドが取得できる。さらに既存の類似機能の実装パターン、命名規則、抽象化レベルを Read で確認する。

設計が既存コードと矛盾する場合は実装を止め、ユーザーに報告する。

### ステップ 5: 実装

タスクを 1 つずつ完了させる。各タスクで:

1. 関連する既存ファイルを Read
2. 詳細設計に従ってコードを書く
3. 既存のスタイル・命名規則・抽象化レベルに合わせる
4. テストファイルがある場合は同時にテストも書く
5. タスクを完了マーク
6. `implementation-log.md` の「変更ファイル」「実装タスク状況」を Edit で更新

**やってはいけないこと:**
- 設計に書かれていない機能を勝手に追加する
- 「将来のため」の抽象化を入れる
- 動かないコードや TODO だらけのコードをコミット可能と判断する
- エラー処理や検証を、設計で要求されていない場所で過剰に追加する

### ステップ 6: 動作確認

```bash
python3 <nike.py> checks
```

検出された全チェック (lint / typecheck / test / build) が走り、結果が JSON で返る。`checks_failed > 0` なら原因を確認して修正。

UI を含む変更なら、可能ならローカル起動して目視確認する（detect の `commands.dev` を参照）。

### ステップ 7: implementation-log.md の最終更新

実装完了後（または中断時）、以下を Edit で記入:

- **実装サマリ**: 何を実装したか（1-3 行）
- **変更ファイル**: 表に新規/変更ファイルを記録
- **実装タスク状況**: チェックボックスを [x] に
- **設計との差分**: 設計と異なる実装をした場合、理由付きで記録
- **既知の制限・TODO**
- **検証用メモ (verify Skill 向け)**: 起動コマンド、テストコマンド、手動確認手順

「検証用メモ」は verify Skill が直接参照する。手抜きせず実コマンドを書くこと。

## 進め方の原則

- **設計を信じすぎない**。設計に矛盾や曖昧さを見つけたら、推測で進めず、ユーザーに確認する。
- **設計を疑いすぎない**。「設計と違うやり方の方が良さそう」と思っても、まずは設計通りに実装する。本当に変える必要があるなら implementation-log.md の「設計との差分」に必ず記録する。
- **タスク完了をこまめに記録する**。中断されても再開できるよう、TaskCreate と implementation-log.md を活用する。
- **既存パターンを尊重する**。新しい流儀を持ち込まない。
- **CLI でできることは CLI に任せる**。テンプレ生成・コマンド推定・チェック実行は nike CLI を使い、AI は判断と内容充填に集中する。
- 完了報告では「実装した機能」「変更ファイル」「未対応事項」「次に verify する方法」を簡潔に伝える。
