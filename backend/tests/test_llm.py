import pytest

from app import llm as llm_module


class _FakeHttpOptions:
    def __init__(self, **kw):
        self.kw = kw


class _FakeTypes:
    HttpOptions = _FakeHttpOptions


class _BoomHttpOptions:
    def __init__(self, **kw):
        raise TypeError("unsupported")


class _BoomTypes:
    HttpOptions = _BoomHttpOptions


def test_http_options_pin_v1beta():
    # The "-latest"/preview models are only served from v1beta. If this
    # ever regresses to v1, every Gemini call 404s again.
    opts = llm_module._http_options(_FakeTypes)

    assert opts.kw["api_version"] == "v1beta"
    assert opts.kw["timeout"] > 0


def test_http_options_fall_back_to_plain_dict():
    opts = llm_module._http_options(_BoomTypes)

    assert opts["api_version"] == "v1beta"
    assert opts["timeout"] > 0


def test_real_sdk_keeps_the_api_version():
    # Guards against the SDK silently dropping the field we depend on.
    genai = pytest.importorskip("google.genai")

    opts = llm_module._http_options(genai.types)

    assert opts.api_version == "v1beta"
