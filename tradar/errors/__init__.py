"""错误类型和事件名注册。"""

from tradar.errors.catalog import (
    ErrorDefinition,
    get_event_definition,
    require_registered_event,
)

__all__ = ["ErrorDefinition", "get_event_definition", "require_registered_event"]
