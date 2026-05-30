# Tradar | 创新者的行动雷达

**Trace Radar for Builders**

从你的工作痕迹中，捕捉值得启动的项目信号。

[English](README.md) | [简体中文](README.zh-CN.md)

Tradar 是一个 local-first CLI，用来把你的 coding-agent 工作痕迹转成有证据链的项目雷达。它会读取 Codex sessions、Claude Code sessions、项目文档和 git traces，然后生成可追溯的 HTML 报告，包含项目机会卡、48 小时 demo 建议、决策提示和 debug artifacts。

Tradar 来自 **trace** 和 **radar** 的组合。它的目标是帮助 builder 从自己的真实工作痕迹里发现已经反复出现、但还没有被系统命名和落地的项目信号。

## 它做什么

- 扫描本地 Codex 和 Claude Code 工作痕迹。
- 读取 `AGENTS.md`、`CLAUDE.md`、`README.md`、`CHANGELOG.md`、`docs/**/*.md`、`notes/**/*.md` 等项目意图文档。
- 把 trace evidence 归一化到本地 SQLite store。
- 按来源配额和 token 预算构建 evidence pack。
- 不调用外部 analyst 时，也能生成 base HTML report。
- 可选调用 Codex analyst agent 生成项目机会卡。
- 可选调用 Codex HTML design subagent 增强报告视觉布局。
- 写出完整 debug bundle，保证每条建议都能回到本地证据。

## 当前状态

Tradar 目前是 v0.2 早期 CLI。它可以从源码 checkout 运行，可以构建本地 wheel 和 source distribution，并已准备好基于 PyPI trusted publishing 的发布自动化。

## 环境要求

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- 可选：Codex CLI，用于 `--agent codex` 或 `--render enhanced`
- 可选：Claude Code CLI，用于 `--agent claude`

## 快速开始

安装依赖：

```bash
uv sync
```

初始化本地 sources：

```bash
uv run tradar init \
  --project-root /path/to/project
```

`tradar init` 默认使用 `~/.codex/sessions` 和 `~/.claude/projects`。

检查 source 状态：

```bash
uv run tradar sources doctor
```

只扫描 evidence，不调用 analyst agent：

```bash
uv run tradar scan
```

基于已有 evidence 生成 base report：

```bash
uv run tradar generate --days 30
```

在交互式终端里，`generate` 会自动打开生成的 `report.html`；脚本场景可加
`--no-open`。

执行 scan + analyst generation：

```bash
uv run tradar run --days 30 --agent codex
```

执行 scan + Claude Code analyst generation：

```bash
uv run tradar run --days 30 --agent claude
```

生成增强 HTML report：

```bash
uv run tradar run --days 30 --agent codex --render enhanced
```

验证某次 run 的结构：

```bash
uv run tradar golden-check ~/.local/share/tradar/runs/<run_id>
```

查看 CLI 帮助：

```bash
uv run tradar --help
```

## 核心命令

- `tradar init`：写入本地配置并执行 source diagnostics。
- `tradar sources doctor`：检查已配置 source，不执行扫描。
- `tradar scan`：读取 sources 并写入本地 evidence store。
- `tradar generate --days 30`：基于已有 evidence 生成报告。
- `tradar run --days 30`：执行 `scan + generate`。
- `tradar accept <card_id>`：把某张机会卡标记为接受。
- `tradar snooze <card_id>`：延后处理某张机会卡。
- `tradar reject <card_id>`：拒绝某张机会卡。
- `tradar golden-check <run_dir>`：执行确定性的报告结构检查。

## Report Modes

Tradar 把 evidence processing、analyst judgment 和 presentation 分开：

- `--agent base`：确定性的本地报告，不调用外部 analyst。
- `--agent codex`：把有边界的 evidence pack 发送给 Codex analyst adapter。
- `--agent claude`：把有边界的 evidence pack 发送给 Claude Code analyst adapter。
- `--render base`：使用确定性的 base HTML renderer。
- `--render enhanced`：把 base HTML 发送给 HTML design subagent；如果 required sections 缺失，会回退到 base HTML。

## 输出位置

默认情况下，Tradar 会把本地状态写到：

- config：`~/.config/tradar/config.toml`
- state：`~/.local/share/tradar/tradar.sqlite`
- runs：`~/.local/share/tradar/runs/<run_id>/`

每个 run 目录通常包含：

- `run.json`
- `warnings.jsonl`
- `evidence_pack.json`
- `agent_raw_output.json`
- `validated_report.json`
- `render.log`
- `report.html`

使用外部 agent adapters 时，run 目录还可能包含：

- `agent_prompt.md`
- `agent_last_message.json`
- `schema_repair_prompt.md`
- `schema_repair_last_message.json`
- `html_design_prompt.md`
- `html_design_last_message.html`

## 隐私和安全边界

Tradar 是 local-first 工具，但报告可能包含来自本地工作痕迹的摘要和片段。除非已经审阅和脱敏，否则不要公开 run 目录。

重要边界：

- Source content 只作为不可信 evidence，不作为可执行指令。
- Project documents 使用 allowlist；Tradar 不会递归读取仓库里的所有 Markdown。
- Evidence packs 会先按 item 和 token 预算裁剪，再发送给 analyst adapter。
- `scan` 不调用外部 agents。
- `generate` 不会隐式执行 scan。
- Decision commands 只写本地 decision state。

不要提交本地 session traces、生成的 run 目录、本地 SQLite 数据库或未脱敏报告。

## 开发

运行测试：

```bash
uv run pytest
```

运行可选 golden fixture checks：

```bash
uv run pytest tests/golden --run-llm-eval
```

运行 lint 和类型检查：

```bash
uv run ruff check .
uv run mypy tradar
```

可选启用 pre-push hook，在推送前自动跑 lint、类型检查和测试：

```bash
git config core.hooksPath .githooks
```

## 文档

- [使用指南](docs/usage.md)
- [架构说明](docs/architecture.md)
- [产品原则](docs/product-principles.md)
- [里程碑](docs/milestones.md)
- [开源边界](docs/open-source-boundary.md)
- [隐私模型](docs/privacy.md)
- [发布和 PR 流程](docs/release.md)
- [配置示例](examples/config.toml)

## 参与贡献

Tradar 仍处在早期 MVP 阶段。欢迎围绕 source connectors、privacy controls、report quality 和 packaging 提 issue 或 PR。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 仓库结构

```text
tradar/
  agent_runner/      # Codex, Claude Code, schema repair, and HTML design adapters
  cli/               # Typer CLI
  config/            # Local config and defaults
  connectors/        # Codex, Claude Code, project docs, and git parsers
  evidence/          # Normalization, packing, privacy gate, SQLite store
  golden/            # Deterministic golden report checks
  renderer/          # Base and enhanced HTML rendering
  schemas/           # Pydantic data contracts
  state/             # Local decision state
tests/
docs/
```

## Roadmap

- 改进 noisy agent traces 里的 source discovery 和去重。
- 增强 redaction 和 privacy policy 控制。
- 提升 enhanced HTML report 的设计质量。

## License

MIT。详见 [LICENSE](LICENSE)。
