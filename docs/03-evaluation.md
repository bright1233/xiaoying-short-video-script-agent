# 评估记录

## 已执行测试

运行方式：`python -m pytest -q`。完整结果见 `examples/test-results.txt`。接口示例由 `python -m scripts.generate_examples` 调用 FastAPI 测试客户端产生，输入、实际响应和 Trace 均为仓库文件，不是手写的预设日志。

| 验收点 | 输入 | 实际输出 | Trace / 检查点 |
|---|---|---|---|
| 正常生成及超时长修正 | `examples/inputs/normal_overlength.json` | `examples/outputs/normal_overlength.json`：`completed`，最终 30 秒 | `examples/traces/normal_overlength.json`：初稿 38 秒，修改后重新估时为 30 秒，并重新检查 |
| 缺关键信息 | `examples/inputs/missing_input.json` | `examples/outputs/missing_input.json`：`needs_input` | `examples/traces/missing_input.json`：输入校验阶段停止，无工具调用 |
| 无素材 | `examples/inputs/no_material.json` | `examples/outputs/no_material.json`：`needs_input` | `examples/traces/no_material.json`：检索无结果后请求补充 |
| 工具失败 | `examples/inputs/tool_failure.json` | `examples/outputs/tool_failure.json`：故障恢复后 `completed` | `examples/traces/tool_failure.json`：首次估时异常，观察后重试；`tests/test_acceptance.py` 另验证未恢复故障返回 `tool_failed` |
| 规则风险 | `examples/inputs/rule_risk.json` | `examples/outputs/rule_risk.json`：删除无依据效果宣称后 `completed` | `examples/traces/rule_risk.json`：首次规则检查失败，修改后重新估时、重新检查 |
| 真实模型：有素材 | `examples/inputs/live_normal.json` | `examples/outputs/live_normal.json`：`completed`，最终 24 秒 | `examples/traces/live_normal.json`：检索到 P01/P02；首次规则检查失败后模型修改脚本，重新估时与复检通过 |
| 真实模型：无素材 | `examples/inputs/live_no_material.json` | `examples/outputs/live_no_material.json`：`needs_input` | `examples/traces/live_no_material.json`：两次检索均为空，模型转为请求补充资料 |

测试还覆盖调用上限、提前 `finish` 被门禁拒绝、无效时长或模式被拒绝、素材 ID 与事实原文对应。`data/materials.json` 中 P01 原文仅为“支持字幕”，因此规则风险用例中的“效率提升80%”不能保留在最终脚本。

## 目前的验证边界

前五组示例是 `mock`，用于验证完整 HTTP 链路、状态门禁和工具结果的处理；**它们不能证明真实模型决策效果**。另两组 `live` 示例由 `qwen3.8-flash` 实际调用产生：有素材时模型继续写稿，并在规则失败后修改、复检；无素材时模型改写查询一次后请求补充。`tests/test_live_evidence.py` 对保存的真实记录执行独立断言。

联调中保留了 `live_normal_initial.json` 和 `live_no_material_initial.json` 的输出与 Trace，作为修复前证据。初次正常路径虽返回 `completed`，但包含素材未证明的“点击入口”“拖动裁剪框”等操作；初次无素材路径重复空检索过多。随后增加界面操作约束和完整的近期观察历史，再次运行发现一次模型回复是无效 JSON，故启用官方支持的 JSON 输出模式。当前两条 `live` 记录来自修复后的代码，均已核对。旧记录不作为达标结果。

时长是按文字与计划镜头时长估计，实际配音和剪辑可能不同。规则检查通过精确事实引用和模式检测约束明显风险，无法穷尽隐含产品断言；提交前应人工复核最终文案。素材是合成资料，不代表真实产品规格。
