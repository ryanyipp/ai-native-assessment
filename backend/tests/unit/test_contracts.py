import pytest
from pydantic import TypeAdapter, ValidationError

from flowlens.browser.engine import normalise_route, state_signature
from flowlens.models.contracts import BrowserAction, Finding, Observation, ObservedElement
from flowlens.services.evidence import redact


def test_action_schema_rejects_bad_element_id():
    ta = TypeAdapter(BrowserAction)
    assert ta.validate_python({"type": "click", "element_id": "e3"}).element_id == "e3"
    with pytest.raises(ValidationError):
        ta.validate_python({"type": "click", "element_id": "#save"})
    with pytest.raises(ValidationError):
        ta.validate_python({"type": "eval", "script": "x"})


def test_explorer_cannot_confirm_its_own_finding():
    with pytest.raises(ValidationError):
        Finding(run_id="r", kind="persistence_check", reported_by="explorer-a", description="d",
                expected="e", observed="o", verification_status="confirmed")


def test_route_normalisation():
    assert normalise_route("http://h/drafts/3fa9b1c2?saved=1") == "/drafts/:id"
    assert normalise_route("http://h/drafts/new") == "/drafts/new"


def test_signature_ignores_values_but_not_emptiness():
    def obs(v):
        return Observation(url="http://h/drafts/abc12345", title="t", headings=["Edit"],
                           elements=[ObservedElement(id="e1", tag="input", role="textbox", name="Title", value=v)])
    assert state_signature(obs("a"))[0] == state_signature(obs("b"))[0]
    assert state_signature(obs("a"))[0] != state_signature(obs(""))[0]


def test_redact_openrouter_key():
    assert "sk-or" not in redact('{"auth": "sk-or-v1-abcdefabcdef1234567890"}')
