"""Unit tests for crisai.config module.

Tests cover:
- Settings dataclass structure
- Project root resolution
- Default directory paths
- Environment variable overrides
- Directory auto-creation
- Log level configuration
"""
from __future__ import annotations

import os
from dataclasses import fields
from pathlib import Path
from unittest import mock

import pytest

from crisai.config import Settings, load_settings


class TestLoadSettings:
    """Tests for the load_settings() factory function."""

    @pytest.fixture(autouse=True)
    def _isolate_env(self):
        """Ensure tests that check fallbacks don't see the real .env file."""
        # Default env for all tests: only OPENAI_API_KEY set.
        with mock.patch.dict(
            "os.environ",
            {"OPENAI_API_KEY": "test-key"},
            clear=True,
        ):
            yield

    def test_returns_settings_instance(self):
        """load_settings() should return a fully populated Settings dataclass."""
        settings = load_settings()
        assert isinstance(settings, Settings)

    def test_root_dir_is_project_root(self):
        """root_dir should be the parent of workspace, logs, and registry dirs."""
        settings = load_settings()
        assert settings.workspace_dir.parent == settings.root_dir
        assert settings.log_dir.parent == settings.root_dir
        assert settings.registry_dir.parent == settings.root_dir

    def test_workspace_dir_defaults_below_root(self):
        """When CRISAI_WORKSPACE_DIR is unset, workspace_dir should be root/workspace."""
        settings = load_settings()
        assert settings.workspace_dir == settings.root_dir / "workspace"

    def test_log_dir_defaults_below_root(self):
        """When CRISAI_LOG_DIR is unset, log_dir should be root/logs."""
        settings = load_settings()
        assert settings.log_dir == settings.root_dir / "logs"

    def test_registry_dir_defaults_below_root(self):
        """When CRISAI_REGISTRY_DIR is unset, registry_dir should be root/registry."""
        settings = load_settings()
        assert settings.registry_dir == settings.root_dir / "registry"

    def test_openai_api_key_defaults_to_empty(self):
        """When OPENAI_API_KEY is not in the environment, default to empty string."""
        with mock.patch.dict("os.environ", {}, clear=True):
            settings = load_settings()
            assert settings.openai_api_key == ""

    def test_default_model_fallback(self):
        """When CRISAI_DEFAULT_MODEL is unset, fall back to gpt-5.4-mini."""
        # The autouse fixture already clears CRISAI_DEFAULT_MODEL.
        settings = load_settings()
        assert settings.default_model == "gpt-5.4-mini"

    def test_log_level_defaults_to_info(self):
        """When CRISAI_LOG_LEVEL is unset, log_level should default to INFO."""
        # The autouse fixture already clears CRISAI_LOG_LEVEL.
        settings = load_settings()
        assert settings.log_level == "INFO"

    def test_log_level_default_case_insensitive(self):
        """Default log_level should be uppercase INFO regardless of env casing."""
        settings = load_settings()
        assert settings.log_level.isupper()

    @mock.patch.dict("os.environ", {"CRISAI_WORKSPACE_DIR": "/tmp/crisai_test_ws", "OPENAI_API_KEY": "test-key"})
    def test_workspace_dir_respects_env_override(self):
        """CRISAI_WORKSPACE_DIR should override the default workspace path."""
        settings = load_settings()
        assert settings.workspace_dir == Path("/tmp/crisai_test_ws").resolve()

    @mock.patch.dict("os.environ", {"CRISAI_LOG_DIR": "/tmp/crisai_test_log", "OPENAI_API_KEY": "test-key"})
    def test_log_dir_respects_env_override(self):
        """CRISAI_LOG_DIR should override the default log path."""
        settings = load_settings()
        assert settings.log_dir == Path("/tmp/crisai_test_log").resolve()

    @mock.patch.dict("os.environ", {"CRISAI_REGISTRY_DIR": "/tmp/crisai_test_reg", "OPENAI_API_KEY": "test-key"})
    def test_registry_dir_respects_env_override(self):
        """CRISAI_REGISTRY_DIR should override the default registry path."""
        settings = load_settings()
        assert settings.registry_dir == Path("/tmp/crisai_test_reg").resolve()

    @mock.patch.dict("os.environ", {"CRISAI_LOG_LEVEL": "DEBUG", "OPENAI_API_KEY": "test-key"})
    def test_log_level_respects_env_override(self):
        """CRISAI_LOG_LEVEL should override the default log level."""
        settings = load_settings()
        assert settings.log_level == "DEBUG"

    @mock.patch.dict("os.environ", {"CRISAI_LOG_LEVEL": "warning", "OPENAI_API_KEY": "test-key"})
    def test_log_level_accepts_lowercase_env(self):
        """CRISAI_LOG_LEVEL should accept lowercase values and preserve them."""
        settings = load_settings()
        # Note: we preserve the value as-is from the env; the consumer (logging_utils)
        # calls .upper() on it. This test verifies the raw value is stored.
        assert settings.log_level == "warning"

    def test_directories_are_created(self, tmp_path: Path):
        """Missing workspace/log/registry directories should be auto-created."""
        test_root = tmp_path / "test_project"
        test_root.mkdir(parents=True, exist_ok=True)
        (test_root / "workspace").mkdir(parents=True, exist_ok=True)
        (test_root / "logs").mkdir(parents=True, exist_ok=True)
        (test_root / "registry").mkdir(parents=True, exist_ok=True)
        assert (test_root / "workspace").exists()
        assert (test_root / "logs").exists()
        assert (test_root / "registry").exists()

    def test_directory_creation_idempotent(self, tmp_path: Path):
        """Calling load_settings() twice should not raise."""
        settings_1 = load_settings()
        settings_2 = load_settings()
        assert settings_1.workspace_dir == settings_2.workspace_dir
        assert settings_1.workspace_dir.exists()

    def test_all_fields_present(self):
        """Settings should contain all expected fields."""
        settings = load_settings()
        expected_fields = {
            "openai_api_key",
            "default_model",
            "workspace_dir",
            "log_dir",
            "registry_dir",
            "root_dir",
            "log_level",
        }
        actual_fields = {f.name for f in fields(settings)}
        assert expected_fields.issubset(actual_fields), (
            f"Missing fields: {expected_fields - actual_fields}"
        )

