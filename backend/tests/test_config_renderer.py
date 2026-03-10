from __future__ import annotations

from types import SimpleNamespace

from app.constants import MASKED_VALUE
from app.services import config_renderer


def test_merge_provider_config_preserves_masked_secret_and_parses_extra_headers():
    existing = {
        "providers": {
            "openrouter": {
                "api_key": "sk-existing",
                "api_base": "https://openrouter.ai/api/v1",
                "extra_headers": {"HTTP-Referer": "https://before.example"},
            }
        }
    }

    merged = config_renderer.merge_provider_config(
        existing,
        {
            "openrouter": {
                "api_key": MASKED_VALUE,
                "api_base": "https://openrouter.ai/api/v1",
                "extra_headers_json": '{"X-Title":"Claw"}',
            }
        },
    )

    provider = merged["providers"]["openrouter"]
    assert provider["api_key"] == "sk-existing"
    assert provider["api_base"] == "https://openrouter.ai/api/v1"
    assert provider["extra_headers"] == {"X-Title": "Claw"}


def test_merge_openclaw_structured_values_accepts_raw_json5_seed():
    parsed = config_renderer.parse_openclaw_raw_json5(
        """
        {
          model: { primary: 'gpt-4.1-mini', fallbacks: ['gpt-4.1'] },
          sandbox: { mode: 'read-only' }
        }
        """
    )

    merged = config_renderer.merge_openclaw_structured_values(
        parsed,
        {
            "primary_model": "claude-sonnet-4-5",
            "fallback_models": "gpt-4.1, o3-mini",
            "session_dm_scope": "user",
        },
    )

    assert merged["model"]["primary"] == "claude-sonnet-4-5"
    assert merged["model"]["fallbacks"] == ["gpt-4.1", "o3-mini"]
    assert merged["sandbox"]["mode"] == "read-only"
    assert merged["session"]["dmScope"] == "user"


def test_merge_openclaw_structured_values_supports_models_providers_json5():
    merged = config_renderer.merge_openclaw_structured_values(
        config_renderer.default_openclaw_config(),
        {
            "providers_json5": """
            {
              moonshot: {
                baseUrl: "https://api.moonshot.ai/v1",
                apiKey: "${MOONSHOT_API_KEY}",
                api: "openai-completions",
                models: [{ id: "kimi-k2.5", name: "Kimi K2.5" }]
              }
            }
            """
        },
    )

    assert merged["models"]["providers"]["moonshot"]["baseUrl"] == "https://api.moonshot.ai/v1"
    assert merged["models"]["providers"]["moonshot"]["apiKey"] == "${MOONSHOT_API_KEY}"
    assert merged["models"]["providers"]["moonshot"]["models"][0]["id"] == "kimi-k2.5"


def test_load_openclaw_template_config_preserves_models_section(tmp_path):
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        """
        {
          agents: {
            defaults: {
              model: { primary: "moonshot/kimi-k2.5", fallbacks: [] },
              sandbox: { mode: "workspace-write" }
            }
          },
          models: {
            mode: "merge",
            providers: {
              moonshot: {
                baseUrl: "https://api.moonshot.ai/v1",
                apiKey: "${MOONSHOT_API_KEY}",
                api: "openai-completions",
                models: [{ id: "kimi-k2.5", name: "Kimi K2.5" }]
              }
            }
          }
        }
        """,
        encoding="utf-8",
    )

    loaded = config_renderer.load_openclaw_template_config(config_path)

    assert loaded["model"]["primary"] == "moonshot/kimi-k2.5"
    assert loaded["models"]["mode"] == "merge"
    assert loaded["models"]["providers"]["moonshot"]["apiKey"] == "${MOONSHOT_API_KEY}"


def test_render_openclaw_aggregate_payload_deduplicates_accounts():
    settings = SimpleNamespace(openclaw_gateway_port=18500)
    workspaces = [
        {
            "workspace": SimpleNamespace(id=1, name="Alpha"),
            "workspace_path": "/tmp/alpha/.openclaw/workspace",
            "openclaw_config": config_renderer.default_openclaw_config(),
            "openclaw_channel": {
                "enabled": True,
                "account_id": "shared-account",
                "app_id": "app-1",
                "app_secret": "secret-1",
            },
            "openclaw_binding": {"enabled": True, "channel": "feishu"},
        },
        {
            "workspace": SimpleNamespace(id=2, name="Beta"),
            "workspace_path": "/tmp/beta/.openclaw/workspace",
            "openclaw_config": config_renderer.default_openclaw_config(),
            "openclaw_channel": {
                "enabled": True,
                "account_id": "shared-account",
                "app_id": "app-1",
                "app_secret": "secret-1",
            },
            "openclaw_binding": {"enabled": True, "channel": "feishu"},
        },
    ]

    payload = config_renderer.render_openclaw_aggregate_payload(workspaces, settings)

    assert payload["gateway"]["port"] == 18500
    assert len(payload["channels"]["feishu"]["accounts"]) == 1
    assert len(payload["bindings"]) == 2
    assert payload["bindings"][0]["agentId"] == "workspace-1"
    assert payload["bindings"][1]["agentId"] == "workspace-2"
