# Context Guard — Codex Context Window Monitor & Session Handoff

[![Tests](https://github.com/Cand1ePower/codex-context-guard/actions/workflows/test.yml/badge.svg)](https://github.com/Cand1ePower/codex-context-guard/actions/workflows/test.yml)

**Codex 上下文窗口监测、token 用量提醒、新建对话建议和会话交接。**

A lightweight Agent Skill for Codex context window monitoring, token usage alerts, context rot management, and session handoff / resume. Get a reminder before a chat becomes overloaded, save the current task state, and continue in a fresh conversation.

当在同一个对话里持续调试、编辑文档或处理项目时，Context Guard 会在适当节点检查用量，提醒整理工作状态，并帮助新对话交接。

## 功能

| 功能 | 实际行为 |
|---|---|
| 上下文检查 | 从当前 Codex 会话本地日志提取上次请求的输入 token 与报告窗口 |
| 提醒策略 | 百分比与绝对 token 预算任一达到即提醒，支持自定义 |
| 任务边界判断 | 切换项目或独立大任务时，可在低用量时建议新建对话 |
| 提醒去重 | 同一会话已确认的同等级提醒不重复；升级或压缩后可再提醒 |
| 创建交接 | 自动附带必要元数据，由 agent 填写真实目标、进度、约束和下一步 |
| 列出交接 | 查找项目内最近的交接记录 |
| 校验交接 | 检查缺失内容、占位符和可能的凭据；不使用虚假的质量分数 |
| 过时检查 | 对比选定文件 SHA-256、Git 分支、HEAD、工作区状态与时间 |
| 恢复任务 | 读取最新相关交接，核实状态后继续，不重新载入整段旧聊天 |

## 安装与启用

通过 Skills CLI 安装：

```bash
npx skills add Cand1ePower/codex-context-guard --skill context-guard -g -y
```

或在 Codex 中请求：

```text
请用 skill-installer 从 Cand1ePower/codex-context-guard 安装 skills/context-guard。
```

**仅安装 skill 不保证每轮都会检查。** 在全局 `~/.codex/AGENTS.md` 追加下面的规则，把路径换成实际安装目录，保留原有配置：

```markdown
For substantive tasks, use context-guard at <installed-skill-dir>/SKILL.md.
Run its scripts/check_context.py at the start, after unusually large tool output,
and at major phase boundaries. Keep normal results silent. Suggest a fresh chat
for a separate major objective or the skill's usage thresholds. Finish the current
safe unit and provide a concise handoff. Unknown telemetry stays unknown.
Do not interrupt work or repeat acknowledged reminders.

```

详见[证据与校准说明](skills/context-guard/references/context-quality.md)。脚本测试验证策略实现，不验证模型质量。若新对话一开始就因全局指令、技能目录或必需材料超过预算，应先精简固定输入或调整任务预算，避免反复重开。

## 创建和恢复交接

下面的操作由 agent 完成

```bash
python <skill-dir>/scripts/handoff.py create --project <project-dir> --title "任务名称" --file <relative-artifact>
python <skill-dir>/scripts/handoff.py list --project <project-dir>
python <skill-dir>/scripts/handoff.py validate <handoff.md>
python <skill-dir>/scripts/handoff.py check <handoff.md> --project <project-dir>
python <skill-dir>/scripts/handoff.py resume <handoff.md> --project <project-dir>
```
