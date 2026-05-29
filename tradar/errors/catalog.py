"""稳定错误事件名注册表。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorDefinition:
    error_class: str
    event: str
    severity: str
    default_user_message: str
    recoverable: bool


_DEFINITIONS = [
    ErrorDefinition(
        "RadarConfigError",
        "config.missing",
        "P0",
        "配置文件不存在。",
        True,
    ),
    ErrorDefinition(
        "ConnectorUnavailableError",
        "source.unreadable",
        "P0",
        "数据源不可读。",
        False,
    ),
    ErrorDefinition("ConnectorParseError", "source.too_large", "P2", "文件过大，已跳过。", True),
    ErrorDefinition(
        "ConnectorUnavailableWarning",
        "source.optional_root_missing",
        "P2",
        "可选项目 root 不存在，已跳过。",
        True,
    ),
    ErrorDefinition(
        "ConnectorUnavailableWarning",
        "source.core_no_data",
        "P1",
        "核心数据源没有可解析数据。",
        True,
    ),
    ErrorDefinition(
        "ConnectorQualityWarning",
        "source.evidence_below_quota",
        "P2",
        "某个 source_type 的 evidence 低于预算配额。",
        True,
    ),
    ErrorDefinition(
        "RadarConfigError",
        "source.broad_root_rejected",
        "P0",
        "扫描根目录过宽，已拒绝。",
        False,
    ),
    ErrorDefinition(
        "RadarConfigError",
        "source.output_unwritable",
        "P0",
        "输出目录不可写。",
        False,
    ),
    ErrorDefinition(
        "RadarConfigWarning",
        "source.repo_output_dir",
        "P1",
        (
            "输出目录位于 git repo 内，可能包含本地证据和未脱敏报告；"
            "这里的 path 指向 output_dir，请把该 output_dir 加入所在 repo 的 .gitignore，"
            "或改用用户级目录。"
        ),
        True,
    ),
    ErrorDefinition(
        "RadarConfigError",
        "config.invalid_agent_mode",
        "P1",
        "agent must be base, codex, or claude",
        True,
    ),
    ErrorDefinition(
        "RadarConfigError",
        "config.invalid_render_mode",
        "P1",
        "render must be base or enhanced",
        True,
    ),
    ErrorDefinition(
        "ConnectorParseError",
        "connector.parse_warning",
        "P1",
        "数据源解析存在警告。",
        True,
    ),
    ErrorDefinition(
        "ConnectorParseError",
        "connector.parse_failed",
        "P1",
        "单条记录解析失败。",
        True,
    ),
    ErrorDefinition("EvidenceStoreError", "evidence.deduped", "P2", "重复 evidence 已合并。", True),
    ErrorDefinition(
        "EvidenceValidationError",
        "evidence.validation_failed",
        "P1",
        "evidence 校验失败。",
        True,
    ),
    ErrorDefinition("AgentTimeoutError", "agent.timeout", "P0", "Analyst agent 超时。", False),
    ErrorDefinition(
        "AgentAdapterExecutionError",
        "agent.execution_failed",
        "P0",
        "Analyst agent 外呼失败。",
        False,
    ),
    ErrorDefinition(
        "AgentOutputSchemaError",
        "agent.schema_invalid",
        "P0",
        "Analyst agent 输出结构无效。",
        False,
    ),
    ErrorDefinition(
        "AgentOutputSchemaError",
        "repair.used",
        "P1",
        "已使用一次 schema repair。",
        True,
    ),
    ErrorDefinition("AgentOutputSchemaError", "repair.failed", "P0", "schema repair 失败。", False),
    ErrorDefinition(
        "EnhancedRenderValidationError",
        "render.enhanced_failed",
        "P1",
        "增强渲染失败，已回退 base HTML。",
        True,
    ),
    ErrorDefinition(
        "EnhancedRenderValidationError",
        "render.enhanced_static_prototype",
        "P1",
        "增强渲染没有生成可点击原型，已回退 base HTML。",
        True,
    ),
    ErrorDefinition(
        "RenderError",
        "render.required_section_missing",
        "P0",
        "HTML required section 缺失。",
        False,
    ),
    ErrorDefinition("RenderError", "report.partial", "P1", "报告只包含部分数据源。", True),
    ErrorDefinition("RenderError", "report.empty", "P1", "没有足够 evidence 生成项目卡。", True),
    ErrorDefinition("RenderError", "report.low_confidence", "P1", "报告证据不足。", True),
    ErrorDefinition(
        "DecisionStateError",
        "decision.unknown_card_id",
        "P1",
        "card_id 不在最近报告中，未写入 decision state。",
        True,
    ),
]


ERROR_CATALOG: dict[str, ErrorDefinition] = {
    definition.event: definition for definition in _DEFINITIONS
}


def get_event_definition(event: str) -> ErrorDefinition:
    return require_registered_event(event)


def require_registered_event(event: str) -> ErrorDefinition:
    try:
        return ERROR_CATALOG[event]
    except KeyError as exc:
        raise KeyError("unregistered Tradar event: " + event) from exc
