# MCP Publishing Guide

> English · [中文版](./guide.zh-CN.md)

This guide is for authors who want to publish an MCP service on the persona-agent marketplace. It explains the two accepted product shapes, how to write mcp.json, how to register in the manifest, how the uv runtime fits in, and what the app does when a user installs. Agent Apps with a Web UI are also MCP products, and this guide covers only the requirements shared by all of them. Everything specific to apps lives in the [Agent App developer guide](../agent-app/guide.en.md).

## What an MCP product is

MCP lets the Agent act on the external world. Reading Notion, managing a todo list, checking the weather, and playing music are all jobs for MCP services. The marketplace accepts two product shapes.

A remotely hosted product runs its service in the cloud, and the product itself is nothing more than a short connection config. The official Notion and TickTick services belong to this shape. When a user installs one, the app writes the config locally and connects to the remote endpoint, and the local machine needs no runtime at all.

A self-hosted product ships its implementation code through the repository and runs locally on the user's machine. Its launch config starts the process with uv, and the installer pre-installs the dependencies automatically.

One shape is explicitly rejected. Configs that pull a package at launch time through npx or uvx depend on a package manager being online at every start. Such products cannot guarantee install-and-forget or offline use, and they are hostile to non-technical users. This is a product decision, and review rejects such submissions.

An Agent App is a superset of the self-hosted shape. It adds an agentApp flag to mcp.json and ships a Web UI. Every general requirement in this guide applies to apps as well, and the app-specific conventions for the UI, notifications, and ports are covered in the app guide.

## What the product looks like

The minimal remotely hosted product is two files.

```
mcp/<name>/
├── mcp.json          ← required, connection config
└── logo.png          ← recommended, marketplace card icon
```

A self-hosted product carries the full code and a dependency lock.

```
mcp/<name>/
├── mcp.json          ← required, launch config
├── logo.png          ← recommended, marketplace card icon
├── pyproject.toml    ← required, package definition
├── uv.lock           ← required, reproducible dependency lock
├── src/              ← server sources
└── ui/               ← Agent Apps only, built Web UI
```

The folder name is the machine key, made of lowercase letters, digits, and hyphens. The logo can be SVG or PNG, and a missing logo falls back to a wrench icon on the card. A self-hosted product must commit uv.lock, because reproducing your verified dependency set on the user's machine depends on it. Without it uv sync may install versions that behave differently.

Nothing the user does not need at runtime belongs in the repository. Web frontend sources, node_modules, data directories, and logs all get downloaded verbatim onto user machines. The Agent App guide has a comparison between the development repo and the published product worth copying.

## Writing mcp.json

mcp.json is the connection config of the product, and its content is written into the user's config at install time. Here is one real sample for each shape.

The remotely hosted one comes from the notion product in this repository.

```json
{
  "type": "streamable_http",
  "url": "https://mcp.notion.com/mcp"
}
```

The self-hosted one comes from cloud-music-mcp.

```json
{
  "type": "stdio",
  "command": "uv",
  "args": ["run", "--directory", "${SERVERS_DIR}/cloud-music-mcp", "cloud-music-mcp"]
}
```

The type field takes one of two values. A type of stdio means the app starts a local process, and streamable_http means the app connects to a remote service.

A remote product points at its endpoint through url and may attach custom request headers through headers. A stdio product starts its process through command and args. The command for a self-hosted product is always uv, the args carry the package name and parameters, and cwd can set the working directory. The env field holds environment variables the service itself needs. Note that per-user credentials such as API keys currently have no delivery channel. The marketplace does not carry them, the app offers no entry to fill them in after install, so writing them into the product does nothing for the user. The description field is optional. Setting disabled to true disables the service. The connect_timeout and execute_timeout fields control connection and execution timeouts. The agentApp and supportedUI fields belong to Agent Apps, and a plain MCP product does not write them.

### The placeholder

A self-hosted product cannot know which directory it will land in, so mcp.json uses ${SERVERS_DIR} to stand for the local servers directory. At install time the app performs a string replacement over the whole JSON, and the placeholder may appear at any nested position, in args, cwd, or env, and becomes the real install path afterwards. A product with a hardcoded absolute path cannot work on user machines.

### The same-name rule

The folder name, the manifest id, the last segment of the manifest path, and the key inside the user's mcp.json after install must all be the same kebab-case string. The app aligns install, indexing, and uninstall on this one name, and any mismatch causes a failed install or an uninstall leftover. An Agent App adds the notification source, five names in total, with the details in the app guide.

## Registering in the manifest

Append one entry to [mcp/index.json](../../mcp/index.json) in this repository.

```json
{
  "id": "cloud-music-mcp",
  "name": "网易云音乐",
  "description": "搜索、播放和管理网易云音乐歌单",
  "author": "Code-MonkeyZhang",
  "homepage": "https://github.com/Code-MonkeyZhang/persona-agent-marketplace/tree/main/mcp/cloud-music-mcp",
  "path": "mcp/cloud-music-mcp",
  "logo": "logo.png",
  "runtime": "uv"
}
```

The base fields match the Skill manifest, and their meanings are not repeated here. See the registering section of the [Skill publishing guide](../skill/guide.en.md). MCP adds two fields of its own.

The runtime field declares the local runtime a product needs. A self-hosted product writes uv, which tells the app to check the environment before downloading. A remote product runs no local process and omits the field. Setting agentApp to true marks an Agent App, and the marketplace buckets such products into the apps tab. A plain MCP product does not write it.

As with Skills, the server validates the whole manifest against a schema, and one bad entry breaks the entire MCP tab for every user. Confirm the JSON is valid after editing.

## The runtime and uv

A self-hosted product involves two uv switches, and they guard different stages, which makes them easy to confuse.

The runtime field in the manifest is the environment gate before download. The app first checks whether uv is present on the machine. When it is missing the install is refused without downloading a single byte, and the user is told to set up the environment from the settings page first. The command field in mcp.json is the dependency pre-install switch. For a product whose launch command is uv, the installer runs uv sync in the product directory before connecting, so the first connection does not time out from fetching dependencies on the spot.

The two usually appear together, but the mechanisms are independent. The first one asks whether the environment exists, and the second one decides whether dependencies get installed. The uv environment on the user side is set up through the app itself, so authors do not need to worry about it, but uv.lock must be committed, because uv sync relies on it to reproduce the dependency versions.

## What happens when a user installs

After the user clicks install, the app runs three checks first. An illegal name returns 400. A service with the same name already present locally returns 409. A product missing from the manifest returns 404. A product that declares runtime uv additionally gets an environment check before any download, and a missing uv refuses the install outright.

Once the checks pass, the app scans every file under the product folder and downloads them concurrently into the local servers directory, and a failure on any file rolls the whole install back. The app then reads the product mcp.json, and a parse failure rolls back as well and tells the user to report to the author. On success the app substitutes the placeholder, writes the config into the user's mcp.json, and records an mcp-meta.json inside the product directory holding the display name, author, description, homepage, and icon URL, which every later list and detail view reads from. A product whose launch command is uv runs its dependency pre-install at this point. Finally the service is registered into the connection pool and a connection is attempted.

A failed connection does not count as a failed install. Installation succeeds once the config is written and the server enters the pool, and the connection result surfaces as status in the UI. The outcomes are connected with a tool count, needs authorization, or disconnected with an error message, all visible on the settings page. Authorization applies only to remote services that support OAuth. The handshake reports that auth is needed, an authorize button appears on the settings page, and the user clicks through the flow.

Uninstall is four steps, disconnect, leave the pool, remove the config entry, and delete the directory, all effective immediately without a restart.

## Pre-publish checklist

- Folder name, manifest id, and the last segment of path all agree
- The shape is clear, a remote product holds only a url, a self-hosted one carries full code
- A remote product omits runtime, a self-hosted one writes uv and keeps command as uv
- Paths use the ${SERVERS_DIR} placeholder with nothing hardcoded
- The service does not depend on a per-user static API key, and login goes through OAuth
- uv.lock is committed
- Web sources, node_modules, data directories, and logs are stripped
- Homepage is a valid URL, and the logo exists and is referenced
- Manifest JSON is valid and no Git LFS is used

## FAQ

**Should a remote product write runtime?**

No. runtime declares a local runtime need, and a remote product runs no local process. Writing it would only trigger a needless uv check.

**Why must uv.lock be committed?**

uv sync on the user's machine reproduces the dependency versions you verified through the lock file. Without it the install may resolve different versions, and the install cannot run offline.

**My service needs an API key. How does it reach the user?**

There is no channel today. The marketplace does not carry credentials, and the app has no entry for filling in env values after install, so a static-key service simply fails to connect. Services that need a user identity have exactly one path, OAuth, with an authorize button on the settings page after install. Static-key products are best held back until the app gains a credential entry. The repository is public, so never write real credentials into a product.

**Why is an npx-launched MCP rejected?**

Pulling a package at launch time cannot guarantee install-and-forget or offline use. Put the service code into the product as a self-hosted product and it can be listed.

**The install succeeded but the connection failed. What now?**

The install stands. The user sees the status and the error on the settings page and can trigger a reconnect. What the author must guarantee is a correct mcp.json and a complete dependency lock.

## Real examples

[mcp/notion](../../mcp/notion) is the minimal remote sample, one mcp.json plus one icon, and the fastest skeleton to copy.

[mcp/cloud-music-mcp](../../mcp/cloud-music-mcp) is the complete self-hosted sample, uv launch with full sources and a lock file.

[mcp/rock-paper-scissors](../../mcp/rock-paper-scissors) is the Agent App sample, to be read together with the [Agent App developer guide](../agent-app/guide.en.md).
