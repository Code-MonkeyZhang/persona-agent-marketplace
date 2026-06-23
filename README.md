# persona-agent-marketplace

persona-agent 的官方商城仓库。应用从这里读取清单、下载 Skill（以及将来的 MCP / Agent 人物）。

## 目录结构

```
persona-agent-marketplace/
├── skills/
│   ├── index.json          ← Skill 清单
│   └── <skill-folder>/     ← 每个 Skill 一个文件夹
│       └── SKILL.md
├── mcp/                    ← 以后填
└── agents/                 ← 以后填
```

## 发布一个 Skill

往 `skills/` 加一个文件夹，在 `skills/index.json` 里加一条，提 Pull Request 即可。详细的打包规则和提交步骤见 persona-agent 项目的《作者发布指南》。

## 关键约束

- **文件夹名 === `SKILL.md` frontmatter 的 `name`**：两者必须完全相同（英文 kebab-case）。这是应用加载 Skill 的标识。
- **清单的 `description` === frontmatter 的 `description`**：写成同一段文字。
- 不要使用 Git LFS（会破坏应用的 raw 下载方式）。
