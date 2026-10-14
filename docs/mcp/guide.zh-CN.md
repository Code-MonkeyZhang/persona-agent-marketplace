# MCP 上架指南

> 中文版 · [English](./guide.en.md)

这份指南面向想在 persona-agent 商城发布 MCP 服务的作者。它讲清楚 MCP 商品有哪两种形态、mcp.json 怎么写、清单怎么登记、uv 运行时怎么配合、用户安装时应用会做什么。带界面的 Agent App 也是 MCP 商品的一种，本文只覆盖通用要求，App 专属的部分看 [Agent App 开发指南](../agent-app/guide.zh-CN.md)。

## MCP 商品是什么

MCP 让 Agent 能操作外部世界。读写 Notion、管理待办清单、查询天气、播放音乐，这些都是 MCP 服务的职责。商城里的 MCP 商品分两种形态。

远程托管型的服务跑在云端，商品里只有一小段连接配置。Notion 和滴答清单这类官方 MCP 属于这一类。用户安装时，应用只是把配置写进本地然后去连远端，本地不需要任何运行时。

自研代码型把实现代码随仓库分发，装到用户本地运行。它的启动配置用 uv 拉起进程，安装时应用会自动预装依赖。

有一类明确不收。配置写成 npx 现场拉某个 npm 包，或者 uvx 现场拉某个 Python 包，每次启动都依赖包管理器在线下载，这种运行时现拉包型做不到下载即用、断网可用，对普通用户也不友好。这是产品决策，审核会拒绝这类提交。

Agent App 是自研型的超集。它在 mcp.json 里加 agentApp 标记并附带 Web UI，本文的所有通用要求对它同样适用，界面、通知、端口这些 App 专属的约定在 App 指南里讲。

## 商品长什么样

远程托管型的最小结构只需要两个文件。

```
mcp/<name>/
├── mcp.json          ← 必须，连接配置
└── logo.png          ← 推荐，商城卡片图标
```

自研代码型要带上完整的代码与依赖清单。

```
mcp/<name>/
├── mcp.json          ← 必须，启动配置
├── logo.png          ← 推荐，商城卡片图标
├── pyproject.toml    ← 必须，包定义
├── uv.lock           ← 必须，锁定依赖保证可复现
├── .python-version   ← 必须，固定解释器版本
├── src/              ← 服务源码
└── ui/               ← Agent App 才有，Web UI 构建产物
```

文件夹名是机器键，由小写字母、数字、短横线组成。logo 支持 SVG 或 PNG，缺失时卡片走扳手兜底图标。自研型必须提交 uv.lock，用户机器上的依赖复现靠它保证，没有它 uv sync 可能装出和你验证过的版本不同的依赖。自研型同样必须提交 .python-version，内容写一个发布满两年的稳定版本号，当前统一是 3.12。uv sync 和 uv run 都按它选解释器，版本不固定时 uv 会拉当天最新的 Python，刚发布的解释器上大量 C 扩展依赖还没有预编译 wheel，会回退到源码编译，Windows 用户机器没有编译工具直接安装失败。

用户运行时用不到的东西不要进仓。web 前端源码、node_modules、data 数据目录、日志都会被原样下载到用户机器上，Agent App 指南里有一份开发仓与发布物的对照表可以参考。

## 编写 mcp.json

mcp.json 是商品的连接配置，安装时它的内容会被写进用户配置。两种形态各看一个真实样本。

远程托管型，取自本仓的 notion 商品。

```json
{
  "type": "streamable_http",
  "url": "https://mcp.notion.com/mcp"
}
```

自研代码型，取自本仓的 cloud-music-mcp 商品。

```json
{
  "type": "stdio",
  "command": "uv",
  "args": ["run", "--directory", "${SERVERS_DIR}/cloud-music-mcp", "cloud-music-mcp"]
}
```

type 字段二选一。stdio 表示应用要启动一个本地进程，streamable_http 表示应用去连接一个远端服务。

远程型靠 url 指向服务端点，需要的话可以用 headers 带自定义请求头。stdio 型靠 command 和 args 启动进程，自研型的 command 固定写 uv，args 里写包名和参数，工作目录可以用 cwd 指定。env 字段放服务自身运行需要的环境变量。要注意每个用户各不相同的凭据，比如 API Key，目前商城没有交付通道，装完后应用也没有填写入口，这类值写进商品对用户没有意义。description 是可选的描述。disabled 置 true 可以禁用这个服务。connect_timeout 和 execute_timeout 分别控制连接和执行的超时。agentApp 和 supportedUI 是 Agent App 专属字段，普通 MCP 不写。

### 占位符

自研型不知道自己会被装到用户的哪个目录，所以 mcp.json 里用 ${SERVERS_DIR} 代表本地服务目录。安装时应用对整个 JSON 做字符串替换，这个占位符可以出现在任何嵌套位置，args、cwd、env 里都能用，替换完成后就是真实的安装路径。写死绝对路径的商品无法在用户机器上工作。

### 同名规则

文件夹名、清单的 id、清单 path 的末段、安装后用户 mcp.json 里的 key，四处必须是同一个 kebab-case 字符串。应用在安装、索引、卸载的全链路都按这一个名字对齐，任何一处不一致都会导致安装失败或者卸载残留。Agent App 还要再加通知的 source，一共五处，细节看 App 指南。

## 登记到清单

在本仓的 [mcp/index.json](../../mcp/index.json) 里追加一条记录。

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

基座字段和 Skill 清单一致，id、name、description、author、homepage、path、logo 的含义不在这里重复，看 [Skill 上架指南](../skill/guide.zh-CN.md) 的登记一节。MCP 另有两个专属字段。

runtime 声明商品需要的本地运行时，自研型写 uv，它告诉应用在下载前先检测环境。远程型在本地没有进程，不写这个字段。agentApp 置 true 表示这是 Agent App，商城据此把商品分进应用 Tab，普通 MCP 不写。

和 Skill 一样，清单在服务端整体过 schema 校验，一条坏记录会让整个 MCP 商城打不开。改完清单确认 JSON 语法合法。

## 运行时与 uv

自研型涉及两个 uv 开关，它们各管一段，容易混淆。

清单里的 runtime 是下载前的环境拦截。应用先检测本机的 uv 是否就绪，没装就直接拒绝安装，一个字节都不下载，同时提示用户先去设置页把环境装好。mcp.json 里的 command 是安装时的依赖预装开关。启动命令为 uv 的商品，安装过程会先在商品目录跑一次 uv sync，把依赖装到位，这样首次连接不会因为现场拉依赖而超时。

通常两个开关同时出现，但机制是独立的。前者管环境有没有，后者管依赖装不装。用户侧的 uv 环境由应用引导一键安装，作者不用操心，但 uv.lock 必须提交，uv sync 靠它复现依赖版本。

## 用户安装时会发生什么

用户点安装后，应用先做三道校验。名字不合法返回 400。本地已存在同名服务返回 409。清单里找不到条目返回 404。商品声明了 runtime 为 uv 时，还会在下载前检测 uv 环境，缺失就直接拒绝，不下载任何东西。

校验通过后，应用扫描商品文件夹的全部文件并发下载到本地服务目录，任何一个文件失败都整体回滚。接着读商品的 mcp.json，解析失败同样回滚并提示用户向作者反馈。解析成功后替换占位符，把清单里的显示名、作者、简介、出处和图标地址并入配置，一起写进用户的 mcp.json，此后的列表和详情页都从配置条目读。启动命令为 uv 的商品这时跑依赖预装。最后注册进连接池并发起连接。

连接失败不算安装失败。安装以配置写入和入池为成功标准，连接结果作为状态透出给界面。可能的结果是已连接并提供若干工具，也可能是需要授权或者断开连接带错误信息，用户在设置页能看到状态并处理。需要授权的情况只出现在支持 OAuth 的远程服务上，握手返回需要授权时，设置页会出现授权按钮，用户点一下走完授权流程。

卸载是断连、出池、删配置、删目录四步，全程热生效，不用重启应用。

## 发布前自查

- 文件夹名、清单的 id、path 的末段三处一致
- 形态判断清楚，远程型只有 url，自研型带完整代码
- 远程型不写 runtime，自研型写 uv 且 mcp.json 的 command 为 uv
- 路径全部用 ${SERVERS_DIR} 占位符，没有写死
- 服务不依赖用户各自持有的静态 API Key，需要登录的走 OAuth
- uv.lock 已提交
- .python-version 已提交，值为发布满两年的稳定版本，当前统一 3.12
- 已剥离 web 源码、node_modules、data 目录和日志
- homepage 是合法 URL，logo 已放且被引用
- 清单 JSON 语法合法，没有使用 Git LFS

## 常见问题

**远程型要不要写 runtime？**

不要。runtime 声明的是本地运行时需求，远程型在本地没有进程，写了反而会让应用做不必要的 uv 检测。

**为什么必须提交 uv.lock？**

用户机器上 uv sync 按 lock 文件复现你验证过的依赖版本。没有它可能装出行为不同的版本，而且安装过程无法离线完成。

**为什么必须提交 .python-version？**

uv 不固定版本时永远拿当天最新的 Python 解释器。Python 每发一个新版本，所有带 C 代码的依赖都要重新编译一轮再逐个发布，中间存在一段成品不齐的空窗期，用户随时可能赶上。文件里写死 3.12 这类成熟版本后，用户机器走的全是预编译成品，不触发任何编译。

**我的服务要 API Key，怎么交给用户？**

现在没有通道。商城不传凭据，装完后应用也没有填写 env 的入口，静态 Key 型服务装上就连不通。需要用户身份的服务目前只有 OAuth 一条路，装完在设置页点授权。静态 Key 型服务建议先不上架，等应用补上凭据填写能力。仓库是公开的，任何情况下都不要把真实凭据写进商品。

**npx 启动的 MCP 为什么不收？**

运行时现拉包做不到下载即用、断网可用。把服务代码放进商品做成自研代码型就能上架。

**安装成功但连接失败怎么办？**

这不影响安装成立。用户在设置页能看到连接状态和错误信息，也能手动重连。作者要保证的是 mcp.json 配置正确、依赖锁完整。

## 真实示例

[mcp/notion](../../mcp/notion) 是远程托管型的最小样本，一个 mcp.json 加一个图标，适合照抄骨架。

[mcp/cloud-music-mcp](../../mcp/cloud-music-mcp) 是自研代码型的完整样本，uv 启动加完整源码加锁文件。

[mcp/rock-paper-scissors](../../mcp/rock-paper-scissors) 是 Agent App 的样本，配合 [Agent App 开发指南](../agent-app/guide.zh-CN.md) 阅读。
