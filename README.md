# persona-agent-marketplace

The official marketplace repository for persona-agent. The app reads the
manifests and downloads Skills, MCP servers, Agent Apps, and Agent personas
from here.

## Directory Structure

```
persona-agent-marketplace/
├── skills/
│   ├── index.json          ← Skill manifest
│   └── <skill-folder>/     ← One folder per Skill
│       ├── SKILL.md
│       └── logo.svg        ← Card icon, referenced by the logo field
├── mcp/
│   ├── index.json          ← MCP & Agent App manifest
│   └── <name>/             ← One folder per product
│       ├── mcp.json        ← Launch config (agentApp: true marks an Agent App)
│       ├── icon.png        ← Card & app-bar icon
│       └── src/ + ui/ ...  ← Server source + built Web UI (Agent Apps)
├── agents/
│   ├── index.json          ← Agent persona manifest
│   └── <name>/             ← One folder per persona
│       ├── config.json
│       ├── systemPrompt.md
│       └── assets/
└── docs/
    └── agent-app/          ← Developer docs (not distributed to users)
```

Agent Apps live under `mcp/` — there is no separate `apps/` directory. An
Agent App is an MCP product whose `mcp.json` carries `agentApp: true`; the
marketplace buckets such products into the "Apps" tab.

## Building an Agent App

An Agent App is an MCP Server + Web UI combo: the user interacts with a
visual panel while the Agent sees only standard MCP tools. To build one,
read the developer guide:

- [Agent App Developer Guide (English)](./docs/agent-app/guide.en.md)
- [Agent App 开发指南（中文）](./docs/agent-app/guide.zh-CN.md)

## Publishing

Add your folder under the right category, register it in that category's
`index.json`, and open a Pull Request. Each category has a dedicated guide
covering the full requirements:

- [Skill publishing guide (中文)](./docs/skill/guide.zh-CN.md) | [English](./docs/skill/guide.en.md)
- [MCP publishing guide (中文)](./docs/mcp/guide.zh-CN.md) | [English](./docs/mcp/guide.en.md)
- [Agent publishing guide (中文)](./docs/agent/guide.zh-CN.md) | [English](./docs/agent/guide.en.md)
- [Agent App developer guide (中文)](./docs/agent-app/guide.zh-CN.md) | [English](./docs/agent-app/guide.en.md)

### Skills

- **Folder name === frontmatter `name` === manifest `id`**: all three carry
  the same lowercase kebab-case machine key. The app loads a Skill by its
  frontmatter `name`; the manifest `id` states the same key explicitly so
  identity never has to be derived from `path`.
- **Manifest `name` is the display name**: the frontmatter `name` is a
  machine key while the manifest `name` is what users see on cards, so the
  two may differ in wording even though both are called `name`.
- **Manifest `description` === frontmatter `description`**: keep them as the
  same text.
- Every entry carries a `logo` image (SVG or PNG) in its folder, referenced
  by the `logo` field; the card falls back to a built-in icon when absent.

### MCP Servers

- Product lives under `mcp/<name>/` and must contain a `mcp.json` launch
  config. `${SERVERS_DIR}` in it is replaced with the actual install
  directory at install time.
- Register an entry in `mcp/index.json` with `id` / `name` / `description` /
  `author` / `homepage` / `path` / `logo` / and `runtime: "uv"` when the
  server runs on uv (the installer then pre-installs dependencies via
  `uv sync`, so commit `uv.lock` for reproducibility).

### Agent Apps

An Agent App inherits all MCP constraints, plus:

- `mcp.json` must contain `agentApp: true` and a `supportedUI` array
  (`"desktop"` / `"mobile"`).
- **Same-name rule**: folder name === manifest `id` === the last segment of
  the `index.json` entry's `path` === the installed `mcp.json` key === the
  notification `source`. All five must match.
- The built Web UI under `ui/` **must be committed** — users have no Node
  and cannot rebuild. Strip `web/` sources, `node_modules/`, `data/`, and
  logs before publishing, and make sure `.gitignore` does not exclude
  `ui/`.
- `icon.png` serves double duty: marketplace card (via the `logo` field)
  and runtime app bar (served by your HTTP server at `/icon.png`).

See the [developer guide](./docs/agent-app/guide.en.md) for the full spec,
a minimal server skeleton, and the publishing checklist.

### Agent Personas

- Product lives under `agents/<name>/` with `config.json`,
  `systemPrompt.md`, and `assets/` (optional `voiceSample` file referenced
  from the manifest entry).
- Register an entry in `agents/index.json` with `id` / `name` /
  `description` / `author` / `homepage` / `path`. `id` equals the folder
  name. An optional `logo` overrides the default `assets/avatar.png` card
  image; omit it to keep the card and the chat avatar on the same picture.

## Key Constraints

- **`name` means two different things**: in `SKILL.md` frontmatter it is the
  lowercase kebab-case machine key the app loads Skills by; in the manifest
  it is the display name shown on cards. Keep frontmatter `name` === folder
  name === manifest `id` so the machine identity stays unambiguous.
- **Manifest `description` === frontmatter `description`**: keep them as the same text.
- **Commit build outputs, strip sources**: anything needed at runtime
  (`ui/` builds, `uv.lock`, `icon.png`) must be in the repo; anything
  needed only for development (`web/`, `node_modules/`, `data/`, logs)
  must be stripped. Users download raw files and run them directly.
- Do not use Git LFS (it breaks the app's raw download mechanism).
