from batch_reallocation.config import BatchReallocationConfig


def test_config_reads_standard_runtime_env(monkeypatch):
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.setenv("OMS_TENANT_ID", "LT")
    monkeypatch.setenv("CRM_MERCHANT_CODE", "LAN0000002")
    monkeypatch.setenv("OMS_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("USER", "lantester@item.com")

    cfg = BatchReallocationConfig()

    assert cfg.base_url == "https://oms.example.com"
    assert cfg.tenant_id == "LT"
    assert cfg.merchant_no == "LAN0000002"
    assert cfg.access_token == "token-123"
    assert cfg.user == "lantester@item.com"


def test_config_allows_analysis_without_user(monkeypatch):
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.setenv("OMS_TENANT_ID", "LT")
    monkeypatch.setenv("CRM_MERCHANT_CODE", "LAN0000002")
    monkeypatch.setenv("OMS_ACCESS_TOKEN", "token-123")
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("username", raising=False)
    monkeypatch.delenv("user", raising=False)

    cfg = BatchReallocationConfig()

    assert cfg.user is None
    cfg.validate_for_analysis()


def test_config_blocks_execution_without_user(monkeypatch):
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.setenv("OMS_TENANT_ID", "LT")
    monkeypatch.setenv("CRM_MERCHANT_CODE", "LAN0000002")
    monkeypatch.setenv("OMS_ACCESS_TOKEN", "token-123")
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("username", raising=False)
    monkeypatch.delenv("user", raising=False)

    cfg = BatchReallocationConfig()

    try:
        cfg.validate_for_execution()
    except ValueError as exc:
        assert "USER" in str(exc)
    else:
        raise AssertionError("expected validate_for_execution to fail")
