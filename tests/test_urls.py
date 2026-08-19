"""Tests for email URL helpers."""

import pytest

from app.urls import absolute_href, resolve_email_base_url


class TestAbsoluteHref:
    def test_empty_href(self):
        assert absolute_href("", "https://example.com") == ""

    def test_already_absolute_https(self):
        assert absolute_href("https://foo.com/bar", "https://example.com") == "https://foo.com/bar"

    def test_already_absolute_http(self):
        assert absolute_href("http://foo.com/bar", "https://example.com") == "http://foo.com/bar"

    def test_relative_with_slash(self):
        assert absolute_href("/settings", "https://example.com") == "https://example.com/settings"

    def test_relative_without_slash(self):
        assert absolute_href("settings", "https://example.com") == "https://example.com/settings"

    def test_base_url_trailing_slash_stripped(self):
        assert absolute_href("/settings", "https://example.com/") == "https://example.com/settings"

    def test_no_base_url_returns_unchanged(self):
        assert absolute_href("/settings", "") == "/settings"


class TestResolveEmailBaseUrl:
    def test_env_var_takes_priority(self, monkeypatch):
        monkeypatch.setenv("REALM_PUBLIC_URL", "https://env.example/r/test/")
        config = {"base_url": "https://config.example", "logo_url": "https://abc.raw.icp0.io/logo.png"}
        assert resolve_email_base_url(config) == "https://env.example/r/test"

    def test_email_config_base_url(self, monkeypatch):
        monkeypatch.delenv("REALM_PUBLIC_URL", raising=False)
        config = {"base_url": "https://config.example/", "logo_url": "https://abc.raw.icp0.io/logo.png"}
        assert resolve_email_base_url(config) == "https://config.example"

    def test_derives_from_email_config_logo_url(self, monkeypatch):
        monkeypatch.delenv("REALM_PUBLIC_URL", raising=False)
        config = {"logo_url": "https://abc-raw.raw.icp0.io/custom/logo.png"}
        assert resolve_email_base_url(config) == "https://abc-raw.icp0.io"

    def test_derives_from_notification_logo_url(self, monkeypatch):
        monkeypatch.delenv("REALM_PUBLIC_URL", raising=False)
        config = {}
        notification = {"logo_url": "https://canister123.raw.icp0.io/custom/logo.png"}
        assert resolve_email_base_url(config, notification) == "https://canister123.icp0.io"

    def test_non_raw_logo_url_not_used(self, monkeypatch):
        monkeypatch.delenv("REALM_PUBLIC_URL", raising=False)
        config = {"logo_url": "https://cdn.example.com/logo.png"}
        assert resolve_email_base_url(config) == ""

    def test_empty_when_nothing_configured(self, monkeypatch):
        monkeypatch.delenv("REALM_PUBLIC_URL", raising=False)
        assert resolve_email_base_url({}) == ""
