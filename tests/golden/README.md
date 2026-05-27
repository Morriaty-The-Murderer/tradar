# Golden Report Checks

`tests/golden` 保存脱敏 evidence pack、validated report 和 checklist 期望值。

默认 `uv run pytest` 会跳过这里的检查；需要显式执行：

```bash
uv run pytest tests/golden --run-llm-eval
```

这里不提交真实 agent raw output，也不保存真实本地路径。fixture 只保留结构、证据链和产品判断 checklist 所需字段。
