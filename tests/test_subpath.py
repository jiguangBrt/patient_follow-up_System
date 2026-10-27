import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from patient_follow_up_system.link_urls import public_base_url
from patient_follow_up_system.main import app


@pytest.mark.parametrize("prefix", ["", "/patientfollowup"])
@pytest.mark.parametrize("page", ["/", "/login", "/doctor", "/patient", "/invite", "/intake", "/admin", "/clinical", "/team"])
def test_pages_keep_assets_inside_mount(prefix, page):
    host = FastAPI()
    host.mount(prefix or "/", app)
    with TestClient(host) as client:
        response = client.get(prefix + page)
        assert response.status_code == 200
        assert f'src="{prefix}/static/paths.js?' in response.text
        assert f'href="{prefix}/static/' in response.text
        assert f'href="{prefix}/static/theme.css?' in response.text
        assert f'src="{prefix}/static/accessibility.js?' in response.text
        assert response.headers["cache-control"] == "no-store"
        assert client.get(prefix + "/static/paths.js").status_code == 200
        assert client.get(prefix + "/static/theme.css").status_code == 200
        assert client.get(prefix + "/static/accessibility.js").status_code == 200
        assert client.get(prefix + "/health").json() == {"status": "ok"}
        if prefix:
            assert 'href="/static/' not in response.text
            assert 'src="/static/' not in response.text
            assert client.get("/static/paths.js").status_code == 404


def test_public_links_accept_application_prefix(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.test/patientfollowup/")
    request = Request({"type": "http", "scheme": "https", "server": ("example.test", 443), "path": "/", "headers": []})
    assert public_base_url(request) == "https://example.test/patientfollowup"


def test_trial_chat_is_disabled_without_model_configuration(monkeypatch):
    monkeypatch.setenv("MODEL_ENABLED", "false")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "测试"})
        assert response.status_code == 503
        assert "未启用" in response.json()["detail"]


@pytest.mark.parametrize("path", ["/../other", "/patientfollowup?token=x", "//other", "/%2e%2e"])
def test_public_links_reject_unsafe_prefix(monkeypatch, path):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.test" + path)
    request = Request({"type": "http", "scheme": "https", "server": ("example.test", 443), "path": "/", "headers": []})
    with pytest.raises(HTTPException):
        public_base_url(request)
