# persona-agent-marketplace

The official marketplace repository for persona-agent. The app reads the
manifest and downloads Skills (and later MCP servers / Agent personas) from here.

## Directory Structure

```
persona-agent-marketplace/
├── skills/
│   ├── index.json          ← Skill manifest
│   └── <skill-folder>/     ← One folder per Skill
│       └── SKILL.md
├── mcp/                    ← Future
└── agents/                 ← Future
```

## Publishing a Skill

Add a folder under `skills/`, add an entry to `skills/index.json`, and open a
Pull Request. For detailed packaging rules and submission steps, see the
"Author Publishing Guide" in the persona-agent project.

## Key Constraints

- **Folder name === the `name` in `SKILL.md` frontmatter**: the two must be
  identical (lowercase kebab-case). This is the identifier the app uses to load a Skill.
- **Manifest `description` === frontmatter `description`**: keep them as the same text.
- Do not use Git LFS (it breaks the app's raw download mechanism).
