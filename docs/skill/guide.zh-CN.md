# Skill 上架指南

> 中文版 · [English](./guide.en.md)

这份指南面向想在 persona-agent 商城发布 Skill 的作者。它讲清楚 Skill 商品由哪些文件组成、SKILL.md 怎么写、清单怎么登记、用户安装时应用会做什么。读完它，你应该能整理出一个可以上架的 Skill 商品。

## Skill 是什么

Skill 是 persona-agent 的提示词层扩展能力。一个 Skill 就是一份带元数据头的能力包，它教 Agent 在特定场景下按什么流程做事。写日记、查天气、追踪科技资讯、管理任务清单，这些都靠 Skill 实现。

它和商城里另外两类商品的关系可以用一句话说清。Skill 是知识，内容会被拼进 Agent 的系统提示词，它没有进程也没有连接状态，装完即生效。MCP 是工具，它是一个真实运行的服务，Agent 通过协议调用它。Agent 是人格，装完会克隆出一个全新的对话主体。想做后两类商品，分别看 [MCP 上架指南](../mcp/guide.zh-CN.md) 和 [Agent 上架指南](../agent/guide.zh-CN.md)。

Skill 安装到全局技能池，所有 Agent 共享这份池子。装完不等于生效，用户还需要到某个 Agent 的技能页勾选分配，被分配的 Skill 内容才会拼进那个 Agent 的系统提示词。技能池支持热重载，安装后立刻可用，不需要重启应用。

## 商品长什么样

一个 Skill 商品就是 skills 目录下的一个文件夹。

```
skills/<skill-name>/
├── SKILL.md          ← 必须，技能主体
├── logo.svg          ← 推荐，商城卡片图标
└── <资源文件>        ← 可选，提示词模板、示例数据等
```

文件夹名就是机器键，由小写字母、数字、短横线组成，比如 diary-writing。logo 支持 SVG 或 PNG，文件名任意，在清单的 logo 字段里引用。缺 logo 时卡片会走内置的兜底图标，不阻塞上架，但会影响辨识度。

Skill 可以多文件。提示词模板、示例数据这类资源放在同一个文件夹里即可，安装时应用会把整个文件夹按原结构下载下来，SKILL.md 里用相对路径引用它们。反过来说，文件夹里不要放与运行无关的东西，开发笔记和草稿会被用户原样下载走。

## 编写 SKILL.md

SKILL.md 分两段，开头是元数据头，后面是 Markdown 正文。

```markdown
---
name: diary-writing
description: 帮你回顾一天、整理并写成结构化日记
---

# 日记助手

正文内容……
```

### 元数据头只认两个字段

应用里的解析器不是完整的 YAML 解析器。它逐行读取元数据头，按每行第一个冒号切分键和值。这个实现方式决定了三条硬规则。

每行只能写一个字段，键和值平铺着写，列表、块标量、嵌套结构都不支持。description 必须写在同一行里，换行、折叠写法、竖线块标量都会解析出错误内容。解析器只认 name 和 description 这两个字段，name 必填，description 可省略，省略时按空串处理，写了其他字段不会报错，但会被静默忽略。

frontmatter 里的 name 是机器键，必须是小写字母加数字加短横线的形式，而且必须等于文件夹名，原因在后面的同名规则一节讲。清单里也有一个 name，那是给人看的显示名，可以写中文，两个 name 含义不同，不要混淆。

### 正文怎么写

正文是 Agent 直接阅读的 Markdown。好的正文写清楚三件事。什么时候用，也就是什么场景、用户说了什么话时应该启用这个 Skill。怎么做，也就是步骤、格式要求和注意事项。什么时候不该用，也就是这个 Skill 的边界。

正文质量决定 Skill 好不好用。写的时候可以把自己想象成交接工作的同事，对面是一个聪明但不了解你工作流程的人，把操作手册写给他。

## 登记到清单

商品文件夹放好后，在本仓的 [skills/index.json](../../skills/index.json) 里追加一条记录。

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

各字段的职责如下。id 是机器键，值等于文件夹名，省略时应用会从 path 的末段推导出来，但显式写上更稳妥。name 是商城卡片上的显示名，可以写中文。description 是卡片简介，它必须与 frontmatter 里的 description 保持同文。author 是署名。homepage 是出处链接，必须是合法的 URL。path 是商品在仓库内的路径，末段必须等于文件夹名。logo 是文件夹内图片文件的名字。

有一点要特别小心。清单在服务端是整体过 schema 校验的，任何一条记录不合法，比如 name 为空、homepage 不是合法 URL、path 为空，都会让整个清单拉取失败，结果就是所有用户的 Skill 商城都打不开。改完清单务必确认 JSON 语法合法。

### 三处名字必须一致

文件夹名、frontmatter 的 name、清单的 id，这三处必须是同一个 kebab-case 字符串。

这不是君子协定。应用按文件夹名定位商品并判断它是否已安装，技能池在启动时按 frontmatter 的 name 索引技能。名字不一致时，同一个技能会在不同界面以不同身份出现，安装状态的判定也会错乱。审核会拒绝不一致的提交。

## 用户安装时会发生什么

用户在商城点安装后，应用先做三道校验。名字不合法返回 400。本地已存在同名技能返回 409，提示先卸载。清单里找不到条目返回 404。三关都过了才开始下载。

应用通过 GitHub Trees API 扫描商品文件夹下的全部文件，并发下载到本地 skills 目录。任何一个文件失败都会整体回滚，当作没装过。下载完成后，应用在技能目录里写入一份 skill-meta.json，把清单里的显示名、作者、图标地址记下来。这些信息只在此刻可得，此后的技能列表和详情页都从这份文件读。

最后应用解析下载下来的 SKILL.md 并把它加入技能池。解析失败则回滚整个目录，界面会提示用户向作者反馈。安装只负责装进全局池，不会自动分配给任何 Agent。商城的入口在侧边栏，用户装完后自己去某个 Agent 的技能页勾选分配。

## 发布前自查

- 文件夹名、frontmatter 的 name、清单的 id 三处一致
- frontmatter 只有 name 和 description 两个字段，description 写在单行
- 清单的 description 与 frontmatter 的 description 同文
- homepage 是合法 URL
- logo 已放进文件夹且清单已引用
- 文件夹里没有开发草稿等无关文件
- 清单 JSON 语法合法，没有使用 Git LFS

## 常见问题

**Skill 可以多文件吗？**

可以。资源文件放在同一个文件夹里，安装时整目录下载并保持相对结构，SKILL.md 里用相对路径引用。

**装完的 Skill 怎么更新？**

商城目前没有更新检测。用户想用新版，先卸载再重装。

**description 想写很长的说明怎么办？**

长内容写进正文。清单里的 description 是卡片简介，受单行解析限制，保持一句话就好。

**frontmatter 里写的别的字段为什么没生效？**

解析器只认 name 和 description，其余字段会被静默忽略。额外的说明放正文或清单里。

## 真实示例

[skills/diary-writing](../../skills/diary-writing) 是最小完整样本。它只有 SKILL.md 加 logo.svg，frontmatter 两个字段，清单一条登记，三处名字一致，照着它搭骨架最快。

[skills/ticktick-management](../../skills/ticktick-management) 值得看正文。它把任务创建原则、时间格式、错误处理写成 Agent 可以直接执行的操作规范，是正文写法的参考。
