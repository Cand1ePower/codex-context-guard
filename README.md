# Context Guard — Codex Context Window Monitor & Session Handoff

[![Tests](https://github.com/Cand1ePower/codex-context-guard/actions/workflows/test.yml/badge.svg)](https://github.com/Cand1ePower/codex-context-guard/actions/workflows/test.yml)

**Codex 上下文窗口监测、token 用量提醒、新建对话建议和会话交接恢复。**

A lightweight Agent Skill for Codex context window monitoring, token usage alerts, context rot management, and session handoff / resume. Get a reminder before a chat becomes overloaded, save the current task state, and continue in a fresh conversation.

当你习惯在同一个 agent 对话里持续调试、编辑文档或处理多个项目时，Context Guard 会在适当节点检查用量，提醒整理工作状态，并帮助新对话接手。

## 适合哪些需求

- “上下文太长，什么时候应该新建对话？”
- “Codex context window / token usage monitor 有没有现成 skill？”
- “长对话出现 context rot，想提前提醒。”
- “需要 session handoff、保存进度、恢复任务，不想重新解释一遍。”
- “希望减少无关历史、工具日志和废弃方案造成的上下文负担。”

这些是真实功能的检索词，不代表搜索引擎或其他 agent 必然优先推荐本项目。

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

Python 3.10+，仅使用标准库。脚本不额外调用模型 API、不需要 API key，没有常驻进程。正常 agent 和工具交互仍会产生上下文与相应使用量。

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

如果技能没有显示，重新打开 Codex。也可直接请求：

```text
用 context-guard 检查这次对话是否适合继续；如果需要换对话，保存交接摘要。
```

## 提醒阈值与质量证据

| 级别 | 默认触发条件，任一达到即可 | 建议 |
|---|---|---|
| 正常 | 未达到以下条件 | 静默继续 |
| 提前提醒 | 报告窗口的 35%，或输入 128,000 tokens | 完成当前阶段后准备交接 |
| 较强提醒 | 报告窗口的 50%，或输入 192,000 tokens | 在下一个安全节点后新建对话 |

**这些是保守的工作预算，不是已经测出的模型质量临界点。** 目前核对的资料没有给出当前 GPT-6.1 Sol 在固定百分比后必然明显变差的可靠结论。本项目没有运行新的模型质量基准实验。

[Context Rot](https://www.trychroma.com/research/context-rot)、[Lost in the Middle](https://arxiv.org/abs/2307.03172) 和 [RULER](https://arxiv.org/abs/2404.06654) 表明，输入长度、信息位置和任务复杂度会影响有效利用上下文的能力；旧模型的结果不能直接换算成当前模型的百分比阈值。

详见[证据与校准说明](skills/context-guard/references/context-quality.md)。脚本测试验证策略实现，不验证模型质量。若新对话一开始就因全局指令、技能目录或必需材料超过预算，应先精简固定输入或调整任务预算，避免反复重开。

## 手动检查上下文

```bash
python <skill-dir>/scripts/check_context.py
python <skill-dir>/scripts/check_context.py --warn-percent 30 --urgent-percent 45 --warn-tokens 100000 --urgent-tokens 160000
```

用 `--warn-tokens 0 --urgent-tokens 0` 关闭绝对 token 预算。只有实际向用户显示提醒后才加 `--record`，防止同等级重复提醒。

脚本使用 `CODEX_THREAD_ID` 或备用 `CODEX_SESSION_ID` 定位当前会话；默认目录为 `$CODEX_HOME/sessions` 或 `~/.codex/sessions`。只读取最多 4 MiB 日志尾部，不按“最新日志”猜测会话。

输出中的 `last_input_percent` 是**上次请求输入 / 事件报告窗口**，不是瞬时占用、累计消耗、质量分数或账单。缓存 token 不从占用中扣除。超过默认 600 秒或压缩后尚无新样本时，不触发数字报警。日志结构不兼容时返回未知，仍可按任务边界整理交接。

提醒状态只保存哈希标识、级别、计数与时间，位于 `$CODEX_HOME/context-guard/`。不保存聊天正文、不改写会话日志。

## 创建和恢复交接

下面的操作可直接让 agent 完成；脚本路径需换成实际安装路径。

```bash
python <skill-dir>/scripts/handoff.py create --project <project-dir> --title "任务名称" --file <relative-artifact>
python <skill-dir>/scripts/handoff.py list --project <project-dir>
python <skill-dir>/scripts/handoff.py validate <handoff.md>
python <skill-dir>/scripts/handoff.py check <handoff.md> --project <project-dir>
python <skill-dir>/scripts/handoff.py resume <handoff.md> --project <project-dir>
```

`create` 默认生成一个 UTF-8 草稿，位置为项目内 `.codex/handoffs/`。agent 必须填写目标、决定、已验证进度、验证证据、未完成工作、下一步、风险和授权边界。未填写的草稿不会通过校验。只有任务范围允许写文件时才创建文件。

也可先准备 UTF-8 JSON，通过 `--data <file.json>` 一次创建完整交接。JSON 必须恰好包含以下字符串字段：

```json
{
  "goal": "当前目标与范围",
  "decisions": "已确定的选择",
  "completed": "已完成并验证的工作",
  "verification": "实际执行的验证及结果；没有验证则写明",
  "pending": "尚未完成或正在运行的工作",
  "next_action": "新对话的第一步",
  "risks": "未解决的问题；没有则写明",
  "permissions": "已有授权范围与仍待批准的动作"
}
```

`--file` 可重复指定最多 30 个项目内文件。脚本保存哈希而不复制文件内容；Git 状态仅记录分支、HEAD 和工作区元数据。支持非 Git 的视频、文档和资料整理工作。

`--continues-from <previous.md>` 可关联同项目的上一份交接。新摘要应自包含，不默认加载整个历史链。

`check` 返回 `fresh`、`review` 或 `stale`。它只检查选定文件和 Git 元数据，不能证明其他文件未变、内容准确或所有外部任务状态仍然有效。非 Git 且没有文件基线时要求复核。凭据扫描是启发式检查，不保证发现所有秘密。

恢复时，agent 阅读最新相关摘要、核实当前状态、遵守当前授权，然后执行下一步。脚本不会自动运行摘要里的命令、提交代码、推送、取消任务或重复提交生成任务。

## 设计与来源

交接流程改编自 MIT 许可的 [softaworks/session-handoff](https://github.com/softaworks/agent-toolkit/tree/main/skills/session-handoff)，保留创建、列出、校验、过时检查和恢复能力，并增加选定文件哈希、精简格式及上下文预算策略。实现与文档格式为本项目重新编写。[第三方许可说明](skills/context-guard/THIRD_PARTY_NOTICES.md)。

供 agent 阅读的入口：[SKILL.md](skills/context-guard/SKILL.md)、[llms.txt](llms.txt)。

## 验证与限制

```bash
python -m unittest discover -s tests -v
```

CI 覆盖 Windows／Linux 和 Python 3.10／3.13。测试包含阈值、去重、过时样本、精确会话选择、正文不回显、交接创建/恢复、文件变化、Git 变化、路径范围和凭据拦截。

本地 JSONL 是实现细节，可能随客户端变化。skill 的提醒依赖 agent 遵循全局规则，不提供后台弹窗、自动切换对话或“质量绝不下降”的保证，也不保证一定节省费用。GitHub topics、README 和技能元数据有助于被搜索发现，但不能保证推荐顺序或 skills.sh 收录时间。

## 卸载

移除自己追加的全局触发规则，再停用或移除 `context-guard` 技能即可。可选清理 `$CODEX_HOME/context-guard/` 的提醒记录；现有项目交接文件可继续保留。

MIT License.
