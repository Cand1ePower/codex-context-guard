# Context Guard

给 Codex 用的轻量上下文提醒与会话交接技能。

在开始实质任务、读取大量工具输出和完成阶段性工作时，检查当前会话的本地用量记录。上下文增长时提醒收尾；需要新建对话时，整理一份新会话能直接接手的短摘要。

它是 **skill + 本地脚本 + 一条全局触发规则**，不调用模型 API，不需要 API key，没有常驻进程。

## 适用场景

- 经常在同一个对话里连续处理多个项目，忘记新开对话。
- 调试、资料检索或反复修改积累了大量日志和废弃方案。
- 希望换一个对话继续，但不想重新解释进度、约束和文件位置。

这不是模型质量检测器，也不计算费用。提醒阈值是工作习惯偏好，不表示某个百分比之后模型必然变差。

## 安装

要求 Python 3.10+；脚本只使用 Python 标准库。技能本身可用于支持 Agent Skills 的客户端，数字检查适配的是 Codex 本地 JSONL 会话记录。

在 Codex 中请求：

```text
请用 skill-installer 从 Cand1ePower/codex-context-guard 安装 skills/context-guard。
```

也可以通过 Skills CLI 全局安装：

```bash
npx skills add Cand1ePower/codex-context-guard --skill context-guard -g -y
```

默认路径由安装方式决定。确认技能目录中有 `SKILL.md` 和 `scripts/check_context.py`。如果新技能未显示，请重新打开 Codex。

### 启用主动检查

仅安装一个 skill 不保证模型每轮检查。将下面的短规则放入 Codex 全局 `~/.codex/AGENTS.md`，把路径替换成实际安装目录：

```markdown
For substantive tasks, use the context-guard skill at <installed-skill-dir>/SKILL.md.
Run its scripts/check_context.py at the start, after unusually large tool output,
and at major phase boundaries. Keep normal results silent. Suggest a fresh chat
for a separate major objective or the skill's usage thresholds; finish the current
safe unit and provide a concise handoff. Unknown telemetry stays unknown.
Do not interrupt work or repeat acknowledged reminders.
```

保留已有全局规则，只追加这一段。对极短问答无需额外执行脚本。

## 提醒方式

| 情况 | 默认处理 |
|---|---|
| 上次请求输入 / 报告窗口 < 50% | 静默继续 |
| 达到 50% | 简短建议完成当前阶段后整理交接 |
| 达到 70% | 建议到下一个安全节点后新建对话，为未完成工作准备摘要 |
| 换到另一个项目或独立的大任务 | 即使用量低，也建议新建对话 |
| 只有一个简短的相关追问 | 继续当前对话 |
| 日志缺失、过时或格式未知 | 明确用量未知，按任务边界判断 |

“安全节点”指当前编辑、生成、下载等操作已达到可保存、可接手的状态。提醒不会自动取消任务、关闭对话或要求用户先同意才能继续工作。用户选择继续时继续执行。

示例提醒：

> 上次请求的输入约占报告窗口的 58%。当前阶段完成后适合换新对话，我会附上进度、文件和下一步，方便继续。

50% / 70% 可调整，不是模型的官方质量边界，也不是费用阈值。高百分比会提醒，但低百分比不代表模型输出一定可靠。

## 数字从哪里来

脚本通过 `CODEX_THREAD_ID`，或备用的 `CODEX_SESSION_ID`，定位 `$CODEX_HOME/sessions` 下属于**这个会话**的日志；没有设置 `CODEX_HOME` 时使用 `~/.codex/sessions`。

只读取最多 4 MiB 的日志尾部，提取最近 `token_count` 事件中的：

- `last_token_usage.input_tokens`：上次请求的输入 token 数。
- `model_context_window`：该事件报告的窗口大小。
- 事件时间：默认超过 10 分钟不再触发数字提醒。

比例为前者除以后者。它不是当前瞬时使用量，也不包含后续尚未记入日志的新内容。不使用累计 `total_token_usage` 充当占用；缓存输入依然占据上下文，所以不会从输入中减掉缓存 token。

不会按“最新日志”猜测当前聊天，避免误读另一个并行会话。格式变化、计数无效、记录缺失或压缩后还没有新用量样本时，返回 `unknown` 或 `stale`，不编造数字。

本地 JSONL 是 Codex 的实现细节，未来可能变化。此版本以实际观察到的结构和合成测试为依据，没有承诺兼容所有 Codex 客户端。

## 手动检查和去重

```bash
python <installed-skill-dir>/scripts/check_context.py
python <installed-skill-dir>/scripts/check_context.py --warn-percent 40 --urgent-percent 60
```

输出是短 JSON。下面是**虚构示例**，不代表某个用户的实际会话：

```json
{"status":"ok","source":"local_codex_last_request","sampled_at":"2026-01-01T00:00:00Z","age_seconds":3,"last_input_tokens":180000,"reported_context_window":300000,"last_input_percent":60.0,"level":"watch","should_notify":true}
```

只有真正向用户提醒后才执行同一命令加 `--record`，记录已提醒级别。相同级别不反复提醒，升级到更高级别可以再提醒；检测到新的压缩事件、显著输入下降或窗口变化时可以重新提醒。

状态位于 `$CODEX_HOME/context-guard/`，只记录会话文件路径的哈希标识、提醒级别、计数和时间。不保存聊天正文，也不改写会话日志。

可用参数：

| 参数 | 用途 |
|---|---|
| `--session-file PATH` | 显式指定一个 JSONL；不自动选择其他会话 |
| `--codex-home PATH` | 指定 Codex 根目录 |
| `--session-id ID` | 覆盖环境变量中的会话 ID |
| `--state-dir PATH` | 指定提醒记录目录 |
| `--max-age-seconds N` | 用量样本最长有效时间，默认 600 秒 |
| `--record` | 确认已经向用户显示提醒 |

## 交接摘要包含什么

保留目标、当前决定、已验证状态、关键文件、未完成工作和下一步。普通任务通常只需要约 300–600 个中文字；复杂任务按实际需要增加。非代码任务也可以交接，例如视频生成、文档修订和资料整理。

优先在对话中交付摘要。需要文件且有写入授权时，使用项目内 `.codex/handoffs/`，采用时间戳命名，不覆盖原文件。新会话只读最新的相关摘要，再核实当前文件和进程；不会为了交接又载入整段旧聊天。

摘要由执行任务的模型整理，脚本只提供用量信息，不能保证摘要绝不遗漏。真实运行中的任务标识和待审批事项必须按原状态记录。

## 与已有 handoff 技能的区别

[softaworks/session-handoff](https://github.com/softaworks/agent-toolkit/tree/main/skills/session-handoff) 提供交接模板、Git 信息收集、过时检查和文档校验，适合系统整理开发任务。

Context Guard 聚焦在“什么时候提醒换对话”：增加当前 Codex 会话的用量读取、过时样本处理、提醒去重和全局触发方式。它使用较短的交接格式，支持非 Git 工作，不依赖读取完整历史交接链。

本仓库为独立实现，未复制上述项目的代码。相关资料：[Codex 技能配置](https://developers.openai.com/codex/skills)、[Codex 上下文和命令](https://developers.openai.com/codex/cli/slash-commands)。

## 验证

```bash
python -m unittest discover -s tests -v
```

测试覆盖阈值、累计与缓存计数的区分、过时/无效数据、局部 JSON 写入、准确会话选择、提醒去重、压缩后的重新提醒、有限读取以及不回显正文。CI 在 Windows 和 Linux、Python 3.10 与 3.13 上运行这些测试。

脚本测试不等于模型一定会遵守触发规则，也不证明换对话必然降低费用或提高质量。客户端是否载入全局规则和技能，需要在实际新会话中确认。

## 卸载

先移除自己追加的全局触发规则，再停用或移除 `context-guard` 技能。其他全局配置无需改变。可选删除 `$CODEX_HOME/context-guard/` 下的提醒状态文件；它们不包含聊天正文。

MIT License.
