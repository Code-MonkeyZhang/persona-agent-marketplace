# Agent 上架指南

> 中文版 · [English](./guide.en.md)

这份指南面向想在 persona-agent 商城发布 Agent 人设的作者。它讲清楚 Agent 商品和另外两类商品的本质区别、文件夹里放什么、config.json 和 systemPrompt.md 怎么写、用户安装时应用会做什么。读完它，你应该能打包出一个装完即可对话的 Agent 商品。

## Agent 商品是什么

Skill 和 MCP 装完是能力，它们是给某个 Agent 用的工具。Agent 商品装完是一个新的人格，它本身是对话的主体。这个区别决定了 Agent 商城的全部特殊行为。

安装一个 Agent 商品不是往全局池里塞东西，而是克隆。应用下载商品、读取人设配置、生成全新身份，创建出一个独立的新 Agent，装完自动切换过去，用户立刻能和它对话。新 Agent 有自己的会话记录和记忆目录，和手动创建的 Agent 完全平等。

由此有三条特殊规则。新 Agent 的技能和工具是空的，商城只负责把人格带过来，配什么 Skill 和 MCP 由用户装完自己决定。同一个模板只能装一次，每装一次就克隆一个新 Agent，允许重复装只会制造一堆重复的人格，想再来一份得先把之前那个删掉。没有卸载的概念，不想要了在 AgentEditor 里删除，会话和记忆一并清掉。

Agent 也没有连接状态的概念，它不去连任何外部服务，卡片上没有状态点。

## 商品长什么样

一个 Agent 商品就是 agents 目录下的一个文件夹。

```
agents/<name>/
├── config.json          ← 必须，运行参数
├── systemPrompt.md      ← 必须，人设提示词
├── voice-sample.mp3     ← 可选，语音克隆样本
└── assets/
    ├── avatar.png       ← 必须，卡片图与聊天头像
    ├── backgrounds/     ← 可选，背景图
    └── pose/            ← 可选，表情差分
```

文件夹名是机器键，由小写字母、数字、短横线组成。assets 里的 avatar.png 是卡片展示图与聊天头像的唯一约定来源，必须提供。pose 和 backgrounds 里的图片按文件名引用，中文文件名可以用。语音样本放商品根目录，格式没有硬性限制，mp3 已经实际验证过。

## 编写 config.json

config.json 描述 Agent 的运行参数。下面是本仓 arona 商品的真实文件。

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

name 是 Agent 的显示名，必填。defaultModel 是模型配置，必填，它包含 provider 和 model 两个字符串。maxSteps 是单次任务的最大步数，必填正整数。description 是简介，可省略。compressionThreshold 控制上下文压缩的触发阈值，省略时默认 50。dreamIntervalMinutes 控制记忆整理的间隔，省略时默认 120。voiceLanguage 声明语音语言偏好，可省略。

skillNames 和 mcpNames 这两个字段写了也会被清空，后面讲原因。systemPrompt 不要写在 config.json 里，它从 systemPrompt.md 文件注入，config.json 里就算写了也会被文件内容覆盖。

### 安装时会被洗掉的字段

就算写了这些字段，安装器也会删除或重置它们，不要指望它们生效。

被删除的是 id、createdAt、updatedAt、defaultWorkspacePath、voiceId、marketplaceSource。新 Agent 会有自己的新身份、自己的工作区，这些系统字段一律重新生成。skillNames 和 mcpNames 被清空成空数组，这是产品语义，人格先来，能力用户自己配。安装器还会写入一个 marketplaceSource 标识，格式为仓库所有者加仓库名加文件夹名，应用靠它判断同一个模板是否已经装过。

## 编写 systemPrompt.md

整份文件的内容会作为 systemPrompt 注入，它是人格的定义。纯 Markdown，没有格式要求。

systemPrompt 决定装完的 Agent 像不像，几条经验值得参考。定身份，写清楚这个人是谁、什么语气、和用户是什么关系。定边界，写清楚懂什么、不懂什么、遇到分外请求怎么应对。定习惯，写清楚口头禅、格式偏好、主动行为的分寸。

写完记得检查一件事。config.json 和 systemPrompt.md 两处不要同时出现 systemPrompt，安装器以文件为准，配置里的那份会被直接覆盖。

## 登记到清单

在本仓的 [agents/index.json](../../agents/index.json) 里追加一条记录。

```json
{
  "id": "makise-kurisu",
  "name": "牧濑红莉栖",
  "description": "18岁的天才脑科学家兼物理学家",
  "author": "persona-agent",
  "homepage": "https://github.com/Code-MonkeyZhang/persona-agent-marketplace/tree/main/agents/makise-kurisu",
  "path": "agents/makise-kurisu",
  "voiceSample": "voice-sample.mp3"
}
```

基座字段和 Skill 清单一致，id、name、description、author、homepage、path 的含义看 [Skill 上架指南](../skill/guide.zh-CN.md) 的登记一节。Agent 有两个可选的专属字段。

voiceSample 写语音样本的文件名，声明了文件就必须真实存在于商品文件夹，缺文件时语音功能静默缺失。logo 可以覆盖卡片展示图，不写时走 assets 里的 avatar.png，卡片和聊天头像共用一张图，现有商品都不写这个字段。

同名规则和 Skill 一样收敛在清单层面。文件夹名、清单的 id、path 的末段，三处必须是同一个 kebab-case 字符串。清单同样整体过 schema 校验，一条坏记录会让整个 Agent 商城打不开。

## 用户安装时会发生什么

用户点安装后，应用先校验名字并按文件夹名在清单里找条目，找不到返回 404。然后遍历本地所有 Agent 的来源标识，同一个模板已经装过就返回 409，卡片也会显示已安装并锁住按钮。

校验通过后，应用把整个商品文件夹下载到一个临时目录。因为新 Agent 的身份要等配置解析完才会生成，目标路径此刻还不知道，所以先下到临时位置。任何一步失败都会清理临时目录，不会留下半个残缺的 Agent。

接着应用读 config.json，把 systemPrompt.md 的内容注入进来，洗掉系统字段，清空技能和工具列表，写入来源标识，然后整体过 schema 校验，校验不过直接报错。校验通过后生成全新的 Agent 身份，创建完整的目录树，涵盖配置、资源、会话、记忆各自的目录，把 assets 整目录复制过去。清单声明了 voiceSample 且文件存在时，语音样本也一起复制。

最后注册会话管理，前端刷新列表并切换到这个新 Agent，安装接口返回 201 和新 Agent 的数据。用户想重装同一个模板，先去 AgentEditor 删掉旧的那个。

## 发布前自查

- 文件夹名、清单的 id、path 的末段三处一致
- config.json 有 name、defaultModel、maxSteps，没有 systemPrompt 和系统字段
- systemPrompt.md 存在且是人格主体
- assets 里的 avatar.png 存在
- voiceSample 声明与文件一致，或者都不写
- homepage 是合法 URL
- 清单 JSON 语法合法，没有使用 Git LFS

## 常见问题

**装完的人设更新了怎么办？**

商城没有更新机制。用户想用新版，删掉旧的 Agent 重装。注意删除会把会话和记忆一并清掉，这是用户侧的取舍。

**能不能带一套默认技能工具？**

不能。安装器会把 skillNames 和 mcpNames 清空。这是有意的产品语义，人格先来，能力由用户自己配。

**语音样本用什么格式？**

mp3 已验证可用。样本放商品根目录，清单的 voiceSample 写文件名，两处对得上就行。

**config.json 里写了 id 会怎样？**

会被删除。新 Agent 一定拿到新生成的身份，模板里的 id 不参与。

**头像可以不放 assets 里吗？**

不建议。avatar.png 是应用约定的默认位置，卡片和聊天头像都从它走。清单的 logo 字段虽然可以覆盖卡片图，但现有商品都不用，保持一张图最省心。

## 真实示例

[agents/arona](../../agents/arona) 是最小样本，config 加 systemPrompt 加头像，三样齐就能上架。

[agents/makise-kurisu](../../agents/makise-kurisu) 是全量样本，语音样本、背景图、六个表情差分齐全，想看资源怎么摆就看它。
