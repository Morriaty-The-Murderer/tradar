# Tradar v0.2 Usage

## 推荐验证路径

1. 初始化或更新配置：

```bash
uv run tradar init \
  --project-root /path/to/project
```

`codex_session_paths` 和 `claude_project_paths` 默认分别写入
`~/.codex/sessions`、`~/.claude/projects`，通常只需要补充项目 root。

2. 检查数据源：

```bash
uv run tradar sources doctor
```

3. 扫描 evidence：

```bash
uv run tradar scan
```

4. 先生成离线 base report，确认 Evidence Store、debug bundle 和 HTML 渲染链路正常：

```bash
uv run tradar generate --days 30
```

5. 再进入真实 analyst agent 路径：

```bash
uv run tradar generate --days 30 --agent codex
```

或使用 Claude Code analyst 路径：

```bash
uv run tradar generate --days 30 --agent claude
```

日常使用可以直接执行：

```bash
uv run tradar run --days 30 --agent codex
```

需要增强 HTML 视觉层级时显式开启：

```bash
uv run tradar run --days 30 --agent codex --render enhanced
```

对生成后的 run 目录执行 checklist：

```bash
uv run tradar golden-check ~/.local/share/tradar/runs/<run_id>
```

## agent 路径边界

- `--agent base` 是默认值，只生成 evidence report，不调用外部 agent。
- `--agent codex` 会调用 `codex exec --json --output-last-message ... -`。
- `--agent claude` 会调用 `claude --bare -p --output-format json --no-session-persistence`。
- agent adapter 会把 analyst prompt、run context 和 evidence pack 组合成 `agent_prompt.md`。
- `agent_prompt.md` 只发送 `title`、`summary`、source metadata、recurrence 和 confidence，不发送 `raw_excerpt`。
- agent final message 必须是 `RadarReport` JSON。
- agent 外呼非零退出时会输出 `agent.execution_failed`，不会把 stderr 当成 schema JSON 继续 repair。
- agent 引用未知 `evidence_id` 时 fail fast，不生成假报告。
- schema repair 仍然最多只执行一次。

## agent binary 配置

默认配置会直接调用 PATH 里的主流 coding-agent binary：

```toml
codex_binary = "codex"
claude_binary = "claude"
```

如果本机使用 wrapper、版本固定路径或别名，可以把它们改成绝对路径，例如：

```toml
codex_binary = "/opt/homebrew/bin/codex"
claude_binary = "/opt/homebrew/bin/claude"
```

`--agent codex` 和 Codex schema repair 使用 `codex_binary`。`--agent claude` 和 Claude Code schema repair 使用 `claude_binary`。`--render enhanced` 当前仍使用 Codex HTML Design Subagent，因此使用 `codex_binary`。

Claude Code adapter 默认使用 `--bare`，避免脚本化调用隐式加载本机 `CLAUDE.md`、hooks、plugins 或 MCP 配置。使用该路径时，需要按 Claude Code CLI 要求提供可用于 bare mode 的认证方式，例如 `ANTHROPIC_API_KEY` 或显式 `--settings` 中的 `apiKeyHelper`。

## render 路径边界

- `--render base` 是默认值，只使用 base HTML renderer。
- `--render enhanced` 会调用 HTML Design Subagent。
- HTML Design Subagent 只接收已生成的 base HTML 和 `html_design.md` prompt。
- enhanced HTML 必须保留 required sections；缺失时回退 base HTML。
- enhanced 失败只影响视觉增强，不阻断报告生成。

## CLI 错误边界

- 配置文件不存在会输出 `config.missing` 和 `next_action=run_tradar_init_or_pass_--config`。
- 非法 `--agent` 会输出 `config.invalid_agent_mode` 和 `next_action=use_--agent_base_codex_or_claude`。
- 非法 `--render` 会输出 `config.invalid_render_mode` 和 `next_action=use_--render_base_or_enhanced`。
- Agent 外呼失败会输出 `agent.execution_failed`、artifact path 和 `next_action=inspect_agent_prompt_and_retry`。
- Agent 输出 schema 无效会输出 `agent.schema_invalid`、`run_id`、artifact path 和 `next_action=inspect_agent_raw_output_and_schema_repair`。
- `run` 会先校验 mode，再执行 scan，避免参数错误写入 Evidence Store。
- `scan` 遇到 `source.unreadable` / `source.broad_root_rejected` 这类可跳过的 P0 source，会跳过该 source、继续扫描其他源，并以非零退出码结束。
- `run` 遇到任何 P0 都会在 scan 前停止。

## decision 命令边界

- `accept` / `snooze` / `reject` 只接受配置 `output_dir` 下最近报告里出现过的 `card_id`。
- 未知或过期 `card_id` 会输出 `decision.unknown_card_id`，并且不会写入 decision state。
- decision 命令不重写历史报告，也不会触发 scan / generate。

## report status

- `complete`：Codex 和 Claude Code core source 都成功扫描，且窗口内有 evidence。
- `partial`：Codex 或 Claude Code 至少一个没有成功扫描，报告会标注失败源。
- `low_confidence`：core source 可用，但 evidence 数低于 `low_confidence_evidence_threshold`，报告会提示扩大窗口或使用 agent 复核。
- `empty`：没有 scan watermark 或没有 evidence，报告顶部会给出 `scan` / `run` CTA。

`generate` 不会隐式扫描；如果看到 `partial` 或 `empty`，先执行：

```bash
uv run tradar sources doctor
uv run tradar run --days 30
```

## privacy gate

scan 流程固定为：

```text
RawEvent -> PrivacyGate.filter() -> Normalizer -> Evidence Store
```

当前 `PrivacyGate` 是空实现，不做隐私分类，也不修改事件内容。它只保留后续加入脱敏或过滤策略时的稳定调用点。

project docs connector 只读取 `AGENTS.md`、`CLAUDE.md`、`README.md`、`CHANGELOG.md`、`docs/**/*.md` 和 `notes/**/*.md`。其他位置的 Markdown 默认不进入 evidence，避免把实现细节或临时草稿当成项目意图。

如果配置的 `output_dir` 已存在但不是目录，或其最近的已存在父目录不可写，`sources doctor` / `run` 会输出 `P0 source.output_unwritable` 并停止，避免 scan 后才在写 report 时失败。

如果 Codex 或 Claude Code core source 没有配置路径，或已配置路径下没有可解析 JSONL，`sources doctor` 会输出 `P1 source.core_no_data`。这不会阻断运行，但表示报告会缺少一个核心行为来源；生成报告时该提示会进入 `warnings.jsonl` 和 Run Summary。

如果可选 `project_roots` 不存在，`sources doctor` 会输出 `P2 source.optional_root_missing`。这不会阻断运行；scan / run 会跳过该 root，并把提示写入 `warnings.jsonl` 和 Run Summary。

如果配置的 `output_dir` 位于 git repo 内，`sources doctor` 会输出 `P1 source.repo_output_dir`。输出里的 `path=` 指向需要处理的 `output_dir`，不是当前执行命令的目录。这不会阻断运行，但表示 run artifact 可能包含本地 evidence 和未脱敏报告，应将该目录加入所在 repo 的 `.gitignore`，或改回默认用户级目录。生成报告时，P1 / P2 doctor 提示会写入 `warnings.jsonl` 和 Run Summary 的 `warning_events`。

如果源文件超过 `max_source_file_bytes`，`sources doctor` 会输出 `P2 source.too_large`。scan 会跳过该 JSONL / Markdown 文件，不写入 evidence，也不会送入 analyst agent。

如果某个已请求 source 有 evidence 但低于默认 source minimum，`generate` 会输出 `P2 source.evidence_below_quota`。这不会阻断运行，但表示该来源样本量偏少，报告质量可能偏向其他来源。

## redaction policy hooks

`scan` 会先通过 PrivacyGate 处理每条 RawEvent，再写入 SQLite。默认规则会脱敏常见的 API key、token、secret、password 赋值形态。命中规则时，event 的 `parse_warnings` 会增加 `privacy.redacted:<rule>`，后续 Run Summary 也会计入 warning。

可以在配置里增加本地正则 hook：

```toml
redaction_patterns = ["VIP-\\d+", "CUSTOM-TOKEN-[A-Z0-9]+"]
redaction_replacement = "<REDACTED>"
```

这些规则只影响后续 scan，不会回写已经生成的历史 run artifact。

## raw output 保存策略

默认会在 run 目录写入 `agent_raw_output.json`，便于追溯 agent 输出。如果不希望保存原始输出，在配置中设置：

```toml
save_agent_raw_output = false
```

关闭后不会写入 `agent_raw_output.json`，但仍会保留：

- `warnings.jsonl`
- `validated_report.json`
- `evidence_pack.json`
- `report.html`

## evidence pack 预算

默认配置包含两层 Evidence Pack 预算：

```toml
max_evidence_items = 120
max_pack_tokens = 24000
max_source_file_bytes = 52428800
agent_timeout_seconds = 300
schema_repair_timeout_seconds = 300
html_design_timeout_seconds = 300
codex_binary = "codex"
claude_binary = "claude"
```

`scan` 使用 `max_source_file_bytes` 跳过过大的 JSONL / Markdown 源文件，默认 50MB。`generate` 会把 `max_evidence_items` 和 `max_pack_tokens` 传给 pack builder。超出条数或 token 预算的 evidence 不会进入 analyst prompt，会记录在 `evidence_pack.json` 的 `omitted_summary` 中。

Pack builder 会在送入 analyst 前做一次信号级去重：标题和摘要归一化后相同的 noisy trace 只保留一个代表项，并把代表项的 `recurrence_count` 合并为该信号的总重复次数。被去重的条目会记录在 `omitted_summary.by_reason.duplicate_signal`。排序优先级是 recurrence、confidence、recency、id，因此同样重复次数下，高置信 evidence 会优先进入 pack。

`generate` 在交互式终端里会自动打开生成的 `report.html`。脚本或 CI 场景可使用 `--no-open`。

`agent_timeout_seconds` 控制 analyst agent 外呼超时，超时会输出 `agent.timeout` 并停止本次生成。`schema_repair_timeout_seconds` 控制一次 schema repair 外呼。`html_design_timeout_seconds` 控制增强 HTML 外呼；超时只会回退 base HTML。

默认 source minimums：

- `codex_session`: 20
- `claude_code_session`: 20
- `project_docs`: 10
- `git_commit`: 10

当 `max_evidence_items` 小到放不下默认配额时，pack builder 会降级为先给每个可用核心 source 保留 1 条，再按全局排序填充剩余预算。

生成报告时，如果某个已请求 source 的 evidence 数量大于 0 但低于默认 source minimum，本次 run 会在 `warnings.jsonl` 和 Run Summary 记录 `source.evidence_below_quota`。

Run Summary 会展示 `source_scan_file_counts` 和 `source_scan_elapsed_ms`，用于回看每类 source 本次扫描的文件规模和耗时。`confidence_note` 会包含 pack item 数、omitted 数和 duplicate signal 数，帮助判断报告是“信号足够”还是“噪音/预算截断较多”。使用 analyst agent 时，Run Summary 还会记录 `agent_elapsed_ms`、`search_used_count`、`search_trace_summary`、`repair_used` 和 `repair_elapsed_ms`。使用增强渲染时会记录 `enhanced_elapsed_ms`。

## debug retention

默认只保留最近 20 个 `run_*` debug bundle。可以在配置里调整：

```toml
debug_retention_run_count = 20
low_confidence_evidence_threshold = 3
```

设置为 `0` 时关闭自动清理。retention 只会删除配置 `output_dir` 下面命名为 `run_*` 且包含 `run.json` 的旧 run 子目录，不会清理其他文件夹。

## run 目录检查项

每个 run 目录至少检查：

- `run.json`：确认 `RunRecord.run_summary` 与 `validated_report.json` 中的 `run_summary` 一致。
- SQLite `runs` 表：确认本次 run 的 `RunRecord` 已持久化，供后续 UI 或 CLI 查询。
- `warnings.jsonl`：确认每行都有 `run_id`、`event`、`level`、`source_type`、`source_ref` 或 `path`、`message`。
- `run_summary.warning_events` / `source_warning_counts`：确认 parse warning 是否集中在某个 source。
- `evidence_pack.json`：确认送入 agent 的 evidence 是否合理。
- `agent_prompt.md`：确认 evidence 只作为不可信材料进入 prompt。
- `agent_raw_output.json`：确认 prompt hash、raw output 和 adapter warning 可追溯。
- `validated_report.json`：确认最终进入 renderer 的结构化报告。
- `html_design_prompt.md`：使用 enhanced render 时，确认输入只包含 base HTML。
- `report.html`：确认 HTML required sections 都存在。

## golden report 人工验收

当前版本不自动评价 agent 创意质量。人工验收时只判断：

- 机会卡是否来自真实行动证据，而不是泛泛总结。
- 证据链是否足够让用户回看来源。
- 最高置信方向是否值得启动一个 48 小时 demo。
- Demo Brief 是否能落到一屏原型、核心交互、所需数据和 kill signal。
- Product Credible Success Path 是否说明窄用户、替代方案、分发入口和两周验证信号。

`golden-check` 会自动检查结构化部分：

- 每张机会卡至少 2 条 evidence。
- 每张机会卡的 `card_id` 必须匹配系统生成规则。
- `This Week's Demo` 存在并绑定有效 `card_id`。
- `Demo Brief` 和 `Product Credible Success Path` 存在。
- Run Summary 包含 sources、prompt hash、`rendered_by` 和 confidence note。
- HTML Run Summary 链接本地 debug artifacts：`run.json`、`warnings.jsonl`、`evidence_pack.json`、`agent_raw_output.json`、`validated_report.json`、`render.log`、`report.html`。
- `Decision Prompt` 至少说明一个暂不做方向。

仍需人工判断：

- 至少 1 个方向是否真的让用户愿意启动 48 小时 demo。
- Product Credible Success Path 是否真的从证据链出发，而不是泛商业计划。
- HTML 中是否出现了没有 evidence 支撑的新项目判断。

脱敏 fixture 复现命令：

```bash
uv run pytest tests/golden --run-llm-eval
```
