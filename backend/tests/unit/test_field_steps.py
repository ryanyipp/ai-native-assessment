"""The browser step for a planned input follows the observed control type."""

import pytest

from flowlens.models.contracts import ControlRef, FormField, SelectOption
from flowlens.orchestration.review import CaseNotRunnable, field_step


def field(role, input_type=None, options=None):
    return FormField(control=ControlRef(role=role, name="F", input_type=input_type), options=options)


OPTIONS = [SelectOption(value="a", label="Annual"), SelectOption(value="s", label="Sick"),
           SelectOption(value="x", label="Closed", disabled=True)]


def test_text_like_inputs_are_filled():
    assert field_step(field("textbox", "date"), "2026-01-01").type == "fill"
    assert field_step(field("textbox"), "hello").value == "hello"


def test_a_select_uses_the_observed_option_value_by_value_or_label():
    assert field_step(field("combobox", options=OPTIONS), "s").value == "s"
    step = field_step(field("combobox", options=OPTIONS), " sick ")
    assert (step.type, step.value) == ("select", "s")


@pytest.mark.parametrize("value", ["Holiday", "Closed"])
def test_unknown_or_disabled_options_are_refused(value):
    with pytest.raises(CaseNotRunnable, match="no selectable option"):
        field_step(field("combobox", options=OPTIONS), value)


@pytest.mark.parametrize("value,state", [("true", True), ("ON", True), ("false", False), ("no", False)])
def test_a_checkbox_uses_the_intended_state(value, state):
    step = field_step(field("checkbox", "checkbox"), value)
    assert (step.type, step.checked) == ("check", state)


def test_a_checkbox_refuses_a_value_with_no_clear_state():
    with pytest.raises(CaseNotRunnable, match="needs true or false"):
        field_step(field("checkbox", "checkbox"), "maybe")


@pytest.mark.parametrize("role,input_type", [("radio", "radio"), ("textbox", "file")])
def test_unsupported_controls_are_refused(role, input_type):
    with pytest.raises(CaseNotRunnable, match="not supported"):
        field_step(field(role, input_type), "x")
