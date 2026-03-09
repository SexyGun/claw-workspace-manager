from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_normalize_legacy_nanobot_unit_template():
    settings = Settings(nanobot_unit_template="claw-nanobot@{workspace_id.service}")
    assert settings.nanobot_unit_template == "claw-nanobot@{workspace_id}.service"


def test_settings_reject_nanobot_unit_template_without_workspace_placeholder():
    with pytest.raises(ValidationError):
        Settings(nanobot_unit_template="claw-nanobot@workspace.service")
