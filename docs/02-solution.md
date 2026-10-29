# 方案与动态决策

## 技术取舍

- FastAPI：提供 `POST /v1/scripts/generate` 和 `GET /health`，用 Pydantic 校验输入输出。
- LangGraph 1.2.11：使用 `StateGraph`、节点、条件边与编译图维护状态和 Agent 循环；未使用多 Agent。一个模型决策者足以展示题目要求，且便于检查动作因工具结果而变化。
- `langchain-openai` 1.7.3：将模型 ID、Base URL、密钥注入兼容接口；模型配置由用户提供。`LiveModel` 生成动作，`MockModel` 仅提供离线流程夹具。
- 真实模型选用 `qwen3.8-flash`。默认华北 2（北京）现有兼容域名，凭据类型为百炼按量计费 API Key；地域、Key 和 Base URL 必须一致。可在取得 Workspace ID 后改用官方推荐的业务空间专属域名。Coding Plan 与 Token Plan 密钥不用于本 FastAPI 后端。依据：[模型信息](https://help.aliyun.com/zh/model-studio/qwen3-8-flash)、[地域配置](https://help.aliyun.com/zh/model-studio/regions)、[套餐限制](https://help.aliyun.com/zh/model-studio/more-tools)。
- 本地工具：素材检索、时长估算、品牌规则检查，不依赖外部业务系统。

## 图与状态

`START → agent → tool → agent` 是循环。模型动作是 `search`、`set_draft`、`estimate`、`check`、`finish` 或 `request_input`。条件边仅按**模型选择的动作**路由。`finish` 进入完成门禁，`request_input` 返回资料缺口。工具结果和异常写入 `history`，下一轮模型看到最新观察结果。

状态保存输入、已检索素材、当前草稿及版本、估时及其对应版本、规则检查及其对应版本、步数、工具调用次数和 Trace。每次 `set_draft` 均使旧估时和旧检查失效。完成门禁要求当前版本通过规则检查、估时不超过目标、有来源 ID，且引用的 ID 在本次检索中取得。门禁不负责替模型选择修正动作。

## 工具规则

`search_materials(query)` 在 `data/materials.json` 的名称、标签、事实原文中检索。`estimate_duration(draft)` 对每镜取计划时长与按每秒 4 字估计的旁白时长的较大值，再求和。`check_rules(draft)` 检查禁用词、无依据的量化效果宣称、素材 ID、`fact_claims` 与原文及脚本的对应关系。规则来源在 `data/brand_rules.json`。这些规则可复算，但不能代替完整的语义事实审查或真实成片计时。

## 错误与上限

工具异常作为观察结果回传模型，允许模型重试或结束；最终仍未恢复的故障返回 `tool_failed`。模型动作无效或模型调用失败也返回 `tool_failed`。达到 `MAX_AGENT_STEPS` 或 `MAX_TOOL_CALLS` 时返回 `incomplete`，并给出具体原因。HTTP 200 只表示接口返回了任务结果，不代表完成。

## Trace

每步包括模型选择的动作、参数、工具返回摘要、下一动作和简短依据。`decision_basis` 是模型输出的简述或 Mock 夹具的说明，不记录内部思维过程。`model_mode` 明确区分 `live` 与 `mock`。
