from dataclasses import fields
from functions.context import ContextHandlerParams, ContextResponse


def test_context_handler_params_is_dataclass():
    params = ContextHandlerParams(session_id="s1", project="proj")
    assert params.session_id == "s1"
    assert params.project == "proj"
    assert params.budget is None  # Optional with default None


def test_context_handler_params_with_budget():
    params = ContextHandlerParams(session_id="s1", project="proj", budget=500)
    assert params.budget == 500


def test_context_handler_params_attribute_not_dict():
    params = ContextHandlerParams(session_id="s1", project="proj")
    # Must use attribute access, not dict access
    assert params.project == "proj"
    assert params.session_id == "s1"
    assert not isinstance(params, dict)


def test_context_response_is_dataclass():
    resp = ContextResponse(context="some context")
    assert resp.context == "some context"
