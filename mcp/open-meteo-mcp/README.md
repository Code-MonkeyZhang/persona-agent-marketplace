<p align="center">
  <img src="logo.svg" width="128" alt="Open-Meteo MCP Logo">
</p>

# Open-Meteo MCP 服务器

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) ![Pull Requests Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen)

> 数据源：[Open-Meteo](https://open-meteo.com/) 免费、无需 API Key 的天气 API

**🌤️ 让你的 AI Agent 拥有全球天气数据访问能力**

这是一个基于 [Open-Meteo](https://open-meteo.com/) 的 stdio MCP 服务器，让 Claude Desktop、OpenCode 等 AI Agent 通过工具调用获取全球任意坐标的天气、气候、海洋、空气质量、海拔、洪水、地理编码等数据。

Open-Meteo 是非商业用途免费的天气 API，**不需要 API Key**，适合在本地或 MCP 商城中开箱即用。

## ✨ 功能特性

- **🌍 全球覆盖**：基于 WGS84 坐标系，支持地球上任意经纬度
- **🆓 免费免 Key**：直接联网调用，不需要注册或鉴权
- **🧰 17 个工具**：覆盖预报、归档、空气质量、海洋、洪水、季节预测、气候预测、集合预报、地理编码、海拔，以及 7 个国家级气象模型（DWD / GFS / Météo-France / ECMWF / JMA / Met.no / GEM）
- **⚡ 纯 stdio 协议**：本地启动，不暴露 HTTP 端口，与 MCP 客户端无缝集成

## 🛠️ 工具列表

本服务器向 AI Agent 暴露以下 17 个工具：

| 工具名 | 数据来源 | 功能描述 |
| :--- | :--- | :--- |
| `weather_forecast` | api.open-meteo.com | 综合天气预报，支持逐小时/逐日数据 |
| `weather_archive` | archive-api.open-meteo.com | ERA5 历史天气归档（1940 至今） |
| `air_quality` | air-quality-api.open-meteo.com | 空气质量预报（PM2.5、PM10、AQI、花粉、UV 等） |
| `marine_weather` | marine-api.open-meteo.com | 海洋天气（浪高、浪向、海面温度） |
| `elevation` | api.open-meteo-mcp.com | 数字高程模型（DEM）海拔查询 |
| `flood_forecast` | flood-api.open-meteo.com | GloFAS 全球洪水感知系统的河流径流预报 |
| `geocoding` | geocoding-api.open-meteo.com | 地名 / 邮编 → 坐标转换 |
| `seasonal_forecast` | seasonal-api.open-meteo.com | 长期季节性预报（最长 9 个月） |
| `climate_projection` | climate-api.open-meteo.com | CMIP6 气候变化情景预测 |
| `ensemble_forecast` | ensemble-api.open-meteo.com | 集合预报，展示预报不确定性 |
| `dwd_icon_forecast` | api.open-meteo.com | 德国 DWD ICON 模型专用通道 |
| `gfs_forecast` | api.open-meteo.com | 美国 NOAA GFS 模型专用通道 |
| `meteofrance_forecast` | api.open-meteo.com | 法国 Météo-France 模型专用通道 |
| `ecmwf_forecast` | api.open-meteo.com | ECMWF 模型专用通道（`/v1/ecmwf` 端点） |
| `jma_forecast` | api.open-meteo.com | 日本气象厅 JMA 模型专用通道 |
| `metno_forecast` | api.open-meteo.com | 挪威气象局 Met.no 模型专用通道 |
| `gem_forecast` | api.open-meteo.com | 加拿大气象中心 GEM 模型专用通道 |

## 🚀 安装与使用

### 前置条件

- **操作系统**：macOS 或 Windows
- **Python**：3.10 或更高
- **uv**：用于运行 Python 包（[安装指南](https://docs.astral.sh/uv/getting-started/installation/)）
- **LLM 客户端**：Claude Desktop、OpenCode 或任何支持 MCP 的客户端

### 在 persona-agent 商城中安装

商城卡片里点击"安装"，应用会自动下载源码、调用 `uv sync` 预装依赖、写入 mcp 配置，**不需要手动操作**。

### 手动集成（开发者）

```bash
# 克隆源码
git clone <this-repo>
cd open-meteo-mcp

# 同步依赖（生成 .venv/）
uv sync

# 本地启动测试
uv run open-meteo-mcp
```

集成到 Claude Desktop 的 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "open-meteo": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/open-meteo-mcp",
        "open-meteo-mcp"
      ]
    }
  }
}
```

## 📖 使用示例

启动后，向你的 AI Agent 提问：

- "查一下巴黎明天会不会下雨"
- "珠穆朗玛峰的海拔是多少？"
- "2023 年 7 月北京的历史温度数据"
- "未来 7 天东京的逐小时温度和降水概率"
- "地中海当前的浪高和浪向"

Agent 会自动调用 `geocoding` 把地名转成坐标，再调用对应的天气工具，把原始 JSON 拼成自然语言回答给你。

## ⚠️ 已知限制

- **海拔精度**：`elevation` 工具基于 DEM 模型，与实测值有偏差。例如珠穆朗玛峰 DEM 数据约为 8724m，实际为 8848m。
- **ECMWF 模型 ID**：`ecmwf_forecast` 走 `/v1/ecmwf` 专用端点，模型 ID 与 `/v1/forecast` 不同。允许的 ID 是 `ecmwf_ifs` / `ecmwf_ifs025` / `best_match`。
- **归档日期范围**：`weather_archive` 基于 ERA5，最新数据通常滞后约 5 天。
- **数据速率**：Open-Meteo 免费版有速率限制（每分钟约 10000 次），并发场景下偶有 429，本服务器会原样返回错误信息。

## 📜 License

MIT License — 数据版权归 [Open-Meteo](https://open-meteo.com/) 所有，本仓库仅实现 MCP 接入层。

## 🙏 鸣谢

- [Open-Meteo](https://open-meteo.com/) — 提供免费、开放、无需 Key 的天气 API
- [Model Context Protocol](https://modelcontextprotocol.io/) — Anthropic 开源的 LLM 工具调用协议规范
- [原始 TS 实现](https://github.com/cmer81/open-meteo-mcp) — 本仓库在此基础上精简、翻译为 Python，删除了 HTTP/Express/鉴权等部署相关代码
