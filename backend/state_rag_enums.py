from enum import Enum


class ArtifactType(str, Enum):
    component = "component"
    page = "page"
    layout = "layout"
    config = "config"


class ArtifactSource(str, Enum):
    user_modified = "user_modified"
    ai_generated = "ai_generated"
    ai_modified = "ai_modified"
    system_generated = "system_generated"