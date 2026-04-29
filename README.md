# nike-skills

設計 → 実装 → 検証 のソフトウェア開発ワークフローを支援する Claude Code Skill 集。

## 含まれる Skill

| Skill | 役割 | 主な成果物 |
|-------|------|-----------|
| [`design`](skills/design/SKILL.md) | 要件定義・基本設計・詳細設計を作成 | `docs/design/<feature>/{requirements,basic-design,detailed-design}.md` |
| [`implement`](skills/implement/SKILL.md) | 設計ドキュメントに基づき実装 | ソースコード、`docs/design/<feature>/implementation-log.md` |
| [`verify`](skills/verify/SKILL.md) | 完成した機能を自動検証 | `docs/design/<feature>/verification-report.md` |

## 想定ワークフロー

```
/design  ユーザー認証機能      ← 設計書を作る
/implement  ユーザー認証機能   ← 設計書を読んで実装
/verify  ユーザー認証機能      ← 要件を満たしているか検証
```

各 Skill は `docs/design/<feature>/` を介して成果物を引き継ぐので、別セッションで再開しても文脈が失われません。

## インストール

### プラグインとして利用する場合

```bash
# Claude Code 内で
/plugin marketplace add N-i-ke/nike-skills
/plugin install nike-skills
```

### 個別 Skill をコピーして使う場合

`skills/<skill-name>/` ディレクトリを `~/.claude/skills/` または `<your-project>/.claude/skills/` にコピーしてください。

## ディレクトリ構成

```
nike-skills/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── design/SKILL.md
│   ├── implement/SKILL.md
│   └── verify/SKILL.md
└── README.md
```
