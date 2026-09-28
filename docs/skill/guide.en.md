# Skill Publishing Guide

> English · [中文版](./guide.zh-CN.md)

This guide is for authors who want to publish a Skill on the persona-agent marketplace. It explains which files make up a Skill product, how to write SKILL.md, how to register the product in the manifest, and what the app does when a user installs it. By the end you should be able to package a Skill that is ready for review.

## What a Skill is

A Skill is the prompt-layer extension mechanism of persona-agent. Each Skill is a capability document with a metadata header, and it teaches the Agent what workflow to follow in a given scenario. Keeping a diary, checking the weather, tracking tech news, and managing a task list are all done through Skills.

The relationship to the other two product kinds is easy to state. A Skill is knowledge. Its content gets assembled into the system prompt of an Agent, it runs no process and carries no connection status, and it takes effect the moment it is installed. An MCP product is a tool. It is a real running service that the Agent calls over a protocol. An Agent product is a persona. Installing one clones a brand new conversation partner. For those two kinds see the [MCP publishing guide](./guide.zh-CN.md) and the [Agent publishing guide](./guide.zh-CN.md).

A Skill installs into the global skill pool, which every Agent shares. Installation alone does not activate it. The user still assigns the Skill on the skills page of a specific Agent, and only then is the content spliced into that Agent's system prompt. The pool supports hot reload, so an installed Skill is usable immediately without restarting the app.

## What the product looks like

One Skill product is one folder under the skills directory.

```
skills/<skill-name>/
├── SKILL.md          ← required, the skill body
├── logo.svg          ← recommended, marketplace card icon
└── <resource files>  ← optional, prompt templates, sample data
```

The folder name is the machine key. It consists of lowercase letters, digits, and hyphens, as in diary-writing. The logo can be SVG or PNG under any file name and is referenced by the logo field of the manifest entry. When the logo is missing the card falls back to a built-in icon, which does not block publishing but does hurt recognition.

A Skill can span multiple files. Put prompt templates and sample data in the same folder, and the installer downloads the whole folder while preserving the structure, with SKILL.md referring to them by relative paths. By the same token, do not put anything unrelated in the folder. Development notes and drafts get downloaded verbatim by every user.

## Writing SKILL.md

SKILL.md has two parts, a metadata header at the top and a Markdown body below.

```markdown
---
name: diary-writing
description: 帮你回顾一天、整理并写成结构化日记
---

# Diary Helper

Body content ...
```

### The header only understands two fields

The parser inside the app is not a full YAML parser. It reads the header line by line and splits each line at its first colon. That implementation leads to three hard rules.

Each line carries exactly one field written flat as key and value. Lists, block scalars, and nesting are not supported. The description must stay on a single line. Line breaks, folded styles, and pipe block scalars all parse into wrong content. The parser only understands name and description. The name field is required, the description field is optional and defaults to an empty string, and any extra field is silently ignored rather than rejected.

The name in the frontmatter is the machine key. It must use lowercase letters, digits, and hyphens, and it must equal the folder name, for reasons covered later under the same-name rule. The manifest also has a field called name, which is the human-facing display name and may be Chinese. The two names mean different things, so do not confuse them.

### Writing the body

The body is Markdown that the Agent reads directly. A good body answers three questions. When to use it, meaning which scenarios and which user utterings should trigger the Skill. How to do it, meaning the steps, format requirements, and cautions. When not to use it, meaning the boundary of the Skill.

Body quality decides whether a Skill is any good. Imagine handing over your workflow to a capable colleague who has never seen it, and write the operating manual for that person.

## Registering in the manifest

After the product folder is in place, append one entry to [skills/index.json](../../skills/index.json) in this repository.

```json
{
  "id": "diary-writing",
  "name": "日记助手",
  "description": "帮你回顾一天、整理并写成结构化日记",
  "author": "persona-agent",
  "homepage": "https://github.com/Code-MonkeyZhang/persona-agent-marketplace/tree/main/skills/diary-writing",
  "path": "skills/diary-writing",
  "logo": "logo.svg"
}
```

Each field has one job. The id is the machine key and equals the folder name. The app derives it from the last segment of path when it is absent, but writing it explicitly is safer. The name is the display name shown on the marketplace card and may be Chinese. The description is the card blurb and must stay identical to the description in the frontmatter. The author is the credit line. The homepage is the source link and must be a valid URL. The path is the product location inside the repository, and its last segment must equal the folder name. The logo is the file name of an image inside the product folder.

One caution deserves emphasis. The server validates the whole manifest against a schema. A single invalid entry, such as an empty name, a homepage that is not a URL, or an empty path, makes the entire manifest fetch fail, which means the Skill tab breaks for every user. Always confirm the JSON is syntactically valid after editing.

### Three names must agree

The folder name, the frontmatter name, and the manifest id must be the same kebab-case string.

This is not an honor system. The app locates a product and decides whether it is installed by the folder name, while the skill pool indexes skills by the frontmatter name at startup. When the names disagree, one skill shows up under different identities on different screens and the installed-state checks go wrong. Review rejects inconsistent submissions.

## What happens when a user installs

After the user clicks install, the app runs three checks first. An illegal name returns 400. A skill with the same name already present locally returns 409 and asks the user to uninstall first. A product missing from the manifest returns 404. Only after all three pass does the download begin.

The app scans every file under the product folder through the GitHub Trees API and downloads them concurrently into the local skills directory. A failure on any single file rolls the whole install back as if nothing happened. After the download the app writes a skill-meta.json file into the skill folder, recording the display name, author, and icon URL from the manifest entry. That information is only available at install time, and every later list and detail view reads it from this file.

Finally the app parses the downloaded SKILL.md and adds the skill to the pool. A parse failure rolls the folder back and tells the user to report to the author. Installation only puts the skill into the global pool and never assigns it to any Agent. When the user installs from the skills page of a specific Agent, the frontend additionally completes the assignment for that Agent.

## Pre-publish checklist

- Folder name, frontmatter name, and manifest id all agree
- Frontmatter contains only name and description, with description on a single line
- Manifest description matches the frontmatter description word for word
- Homepage is a valid URL
- Logo file exists and is referenced by the manifest
- No drafts or unrelated files inside the folder
- Manifest JSON is valid and no Git LFS is used

## FAQ

**Can a Skill contain multiple files?**

Yes. Put resources in the same folder. The installer downloads the whole directory and keeps the structure, and SKILL.md references the files by relative paths.

**How do users update an installed Skill?**

The marketplace has no update detection yet. Users who want a new version uninstall first and install again.

**I have a long description to write. Where does it go?**

Long content belongs in the body. The manifest description is the card blurb and, due to the single-line parsing rule, should stay one sentence.

**Why did the extra fields in my frontmatter do nothing?**

The parser only understands name and description and silently ignores the rest. Put extra information in the body or in the manifest.

## Real examples

[skills/diary-writing](../../skills/diary-writing) is the minimal complete sample. It has SKILL.md plus logo.svg, a two-field frontmatter, one manifest entry, and identical names everywhere. Copying its skeleton is the fastest start.

[skills/ticktick-management](../../skills/ticktick-management) is the one to read for body writing. It turns task creation rules, time formats, and error handling into an operating spec the Agent can execute directly.
