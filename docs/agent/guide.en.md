# Agent Publishing Guide

> English · [中文版](./guide.zh-CN.md)

This guide is for authors who want to publish an Agent persona on the persona-agent marketplace. It explains how an Agent product differs from the other two kinds, what goes into the folder, how to write config.json and systemPrompt.md, and what the app does when a user installs. By the end you should be able to package a persona that is ready to chat the moment it is installed.

## What an Agent product is

Skills and MCP products install capabilities, which are tools for some Agent to use. An Agent product installs a new persona, and the persona itself is the conversation partner. That difference drives every special behavior of this category.

Installing an Agent product is a clone, not a pool insert. The app downloads the product, reads the persona config, generates a fresh identity, creates an independent new Agent, and switches to it immediately, so the user can start talking right away. The new Agent has its own sessions and its own memory directory, and it is fully equal to any manually created Agent.

Three rules follow from this. The new Agent starts with empty skills and empty tools, because the marketplace only delivers the persona, and what it can do is decided by the user afterwards. One template installs exactly once, because every install clones a new Agent, and allowing repeats would only manufacture duplicate personas, so a fresh copy requires deleting the old one first. There is no uninstall concept, and removing an unwanted Agent happens in the AgentEditor, which clears its sessions and memory along with it.

An Agent also has no connection status. It connects to nothing external, and its card carries no status dot.

## What the product looks like

One Agent product is one folder under the agents directory.

```
agents/<name>/
├── config.json          ← required, runtime parameters
├── systemPrompt.md      ← required, the persona prompt
└── assets/
    ├── avatar.png       ← required, card image and chat avatar
    ├── backgrounds/     ← optional, background art
    └── pose/            ← optional, expression variants
```

The folder name is the machine key, made of lowercase letters, digits, and hyphens. The avatar.png inside assets is the single agreed source for both the marketplace card and the chat avatar, so it must exist. Images under pose and backgrounds are referenced by file name, and Chinese file names work.

## Writing config.json

config.json describes the runtime parameters of the Agent. Below is the real file of the arona product in this repository.

```json
{
  "name": "阿罗娜",
  "description": "通用AI看板娘，负责管理日常事务",
  "defaultModel": {
    "provider": "deepseek",
    "model": "deepseek-v4-flash"
  },
  "maxSteps": 30,
  "compressionThreshold": 50,
  "dreamIntervalMinutes": 120,
  "skillNames": [],
  "mcpNames": []
}
```

The name is the display name of the Agent and is required. The defaultModel is the model config and is required, holding two strings, provider and model. The maxSteps is the step limit for a single task and must be a positive integer. The description is an optional blurb. The compressionThreshold controls when context compression triggers and defaults to 50 when omitted. The dreamIntervalMinutes controls how often memory consolidation runs and defaults to 120. The voiceLanguage declares a voice language preference and is optional.

The skillNames and mcpNames fields get emptied even when written, for the reason below. The systemPrompt must not be written into config.json. It is injected from the systemPrompt.md file, and even if a copy appears in the config, the file content overwrites it.

### Fields the installer washes away

Even when these fields are present, the installer deletes or resets them, so do not count on them.

The deleted ones are id, createdAt, updatedAt, defaultWorkspacePath, voiceId, and marketplaceSource. A new Agent gets its own identity and its own workspace, and these system fields are regenerated. The skillNames and mcpNames are reset to empty arrays, which is deliberate product semantics, the persona arrives first and the user wires up capabilities. The installer also writes a marketplaceSource identifier in the form of owner, repository, and folder name, and the app uses it to tell whether a template has already been installed.

## Writing systemPrompt.md

The entire file is injected as the systemPrompt, and it defines the persona. It is plain Markdown with no format requirements.

The systemPrompt decides whether the installed Agent feels right, and a few practices help. Define the identity, meaning who this person is, what tone it speaks in, and what relationship it has with the user. Define the boundary, meaning what it knows, what it does not, and how it responds to out-of-scope requests. Define the habits, meaning verbal tics, format preferences, and how much initiative it takes.

One check before submitting. Do not put systemPrompt in both config.json and systemPrompt.md. The installer takes the file as the source of truth and overwrites whatever the config carries.

## Registering in the manifest

Append one entry to [agents/index.json](../../agents/index.json) in this repository.

```json
{
  "id": "makise-kurisu",
  "name": "牧濑红莉栖",
  "description": "18岁的天才脑科学家兼物理学家",
  "author": "persona-agent",
  "homepage": "https://github.com/Code-MonkeyZhang/persona-agent-marketplace/tree/main/agents/makise-kurisu",
  "path": "agents/makise-kurisu"
}
```

The base fields match the Skill manifest, and their meanings are covered in the registering section of the [Skill publishing guide](../skill/guide.en.md). Agent carries no fields of its own today, and the voice identity is configured by the user in the client voice table after install, so goods never ship one.

The base logo can override the card image. When it is absent the app falls back to avatar.png inside assets, so the card and the chat avatar share one picture, and no product in the repository writes this field today.

The same-name rule stays at the manifest level, same as Skills. The folder name, the manifest id, and the last segment of path must be the same kebab-case string. The manifest is validated as a whole, and one bad entry breaks the entire Agent tab.

## What happens when a user installs

After the user clicks install, the app validates the name and locates the entry in the manifest by folder name, returning 404 when it is missing. It then checks the marketplace source column in the database, and a template that is already installed returns 409 while the card shows as installed with a locked button.

Once the checks pass, the app fetches the text of config.json and systemPrompt.md straight from the raw endpoints into memory. It injects the systemPrompt into the config, washes away the system fields, empties the skill and tool lists, writes the source identifier, and validates the whole thing against a schema, with an invalid config failing the install outright. On success it generates a fresh identity, writes the config together with the prompt into the database, and creates the asset and memory directories on disk.

The app then scans the file list of the product folder, skips the two text files, and downloads assets and any other files by relative path straight into the new Agent directory. A download failure rolls the whole install back, leaving no row and no directory behind.

Finally the app registers the session manager, the frontend refreshes the list and switches to the new Agent, and the install endpoint returns 201 with the new Agent data. Reinstalling the same template requires deleting the old Agent in the AgentEditor first.

## Pre-publish checklist

- Folder name, manifest id, and the last segment of path all agree
- config.json has name, defaultModel, and maxSteps, and carries no systemPrompt and no system fields
- systemPrompt.md exists and carries the persona
- avatar.png exists inside assets
- Homepage is a valid URL
- Manifest JSON is valid and no Git LFS is used

## FAQ

**The persona shipped an update. How do users get it?**

The marketplace has no update mechanism. A user who wants the new version deletes the old Agent and installs again. Note that deletion clears sessions and memory with it, which is the user's tradeoff to make.

**Can a product ship default skills and tools?**

No. The installer empties skillNames and mcpNames. This is deliberate product semantics, the persona arrives first and capabilities are wired up by the user.

**What happens to an id written into config.json?**

It gets deleted. A new Agent always receives a freshly generated identity, and the id in the template takes no part.

**Can the avatar live outside assets?**

Not recommended. avatar.png is the agreed default location, and both the card and the chat avatar read from it. The logo field in the manifest can override the card image, but no product uses it today, and sharing one picture is the simplest arrangement.

## Real examples

[agents/arona](../../agents/arona) is the minimal sample, config plus systemPrompt plus an avatar, and those three are enough to publish.

[agents/makise-kurisu](../../agents/makise-kurisu) is the full sample, with a background and six expression variants, and it is the one to read for arranging assets.
