# 题目 4：短视频脚本 Agent

这是校招笔试题 4 的可运行 HTTP API 项目。LangGraph 负责状态与路由；模型选择检索、提交草稿、估时、规则检查、追问或结束。业务工具使用仓库内的合成素材和规则。仅生成脚本，不生成视频或接入发布系统。

## 环境与安装

Python 3.12。以下命令在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Mock 模式无需填写模型变量。`.env.example` 已预填 `qwen3.8-flash` 和华北 2（北京）的现有 OpenAI 兼容 Base URL；Live 模式只需在本地 `.env` 填入**同地域百炼按量计费 API Key**。切勿提交 `.env`。若使用其他地域的 Key，须改为对应地域的 Base URL。官方推荐使用业务空间专属域名，取得 Workspace ID 后可将现有地址替换为 `.env.example` 中的格式。[模型信息](https://help.aliyun.com/zh/model-studio/qwen3-8-flash)、[地域与域名](https://help.aliyun.com/zh/model-studio/regions)、[套餐使用范围](https://help.aliyun.com/zh/model-studio/more-tools)。

## 运行 HTTP API

```powershell
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

另开终端，执行可复制的 Mock 请求：

```powershell
$body = Get-Content examples/inputs/normal_overlength.json -Raw -Encoding UTF8
Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/scripts/generate -Method Post -ContentType 'application/json; charset=utf-8' -Body $body | ConvertTo-Json -Depth 20
```

将输入 JSON 中的 `mode` 改为 `live` 可调用千问。`GET /health` 用于健康检查。业务字段不足返回 `needs_input`；请求类型错误返回 HTTP 422。成功执行 HTTP 请求不等于脚本完成，请检查响应体的 `status`。

取得真实模型配置后，执行 `python -m scripts.capture_live_examples` 保存两组实际调用结果，并人工核对模型动作是否随工具结果改变。脚本不会把 Mock 输出写入 live 文件。

## 评审入口

```powershell
python -m pytest -q
python -m scripts.generate_examples
```

- [需求与成功标准](docs/01-requirements.md)
- [方案及动态决策](docs/02-solution.md)
- [验收结果与限制](docs/03-evaluation.md)
- [AI 使用记录](docs/04-ai-usage.md)
- [复盘](docs/05-retrospective.md)
- [示例输入](examples/inputs/normal_overlength.json)、[实际 HTTP 输出](examples/outputs/normal_overlength.json)、[逐步 Trace](examples/traces/normal_overlength.json)

`examples/` 包含明确标记为 `mock` 的离线流程记录；这些记录不作为真实模型决策效果证据。另有两条 `qwen3.8-flash` 的真实模型记录：[正常脚本 Trace](examples/traces/live_normal.json) 与 [无素材 Trace](examples/traces/live_no_material.json)。`*_initial.json` 是修复前留存的失败证据，评估文档说明了原因。

GitHub 仓库：[bright1233/xiaoying-short-video-script-agent](https://github.com/bright1233/xiaoying-short-video-script-agent)。最终提交 SHA 请以提交时仓库 `main` 分支的 SHA 为准，并与题号 4 一起提交。
