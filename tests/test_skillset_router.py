import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.agent import Agent
from src.routing.skillset_router import SkillsetRouter


class Manager:
    def __init__(self, agents):
        self.agents = agents

    def get_available_agents(self):
        return self.agents

    def get_agent(self, name):
        return next((a for a in self.agents if a.name == name), None)

    def is_valid(self, name):
        return self.get_agent(name) is not None


def make_router(value=None, agents=None):
    agents = agents or [Agent(name="lucy"), Agent(name="lumia", skillset=["image-processing", "image-creation"],
        skills=["image-cli"], default_context="image_tool", prompt_policy={"procedural_tokens": 4000})]
    adapter = Mock()
    adapter.get_text.return_value = json.dumps(value or {"kind": "specialist", "capabilities": ["image-creation"], "confidence": .95})
    config = SimpleNamespace(get=lambda key, default=None: default)
    return SkillsetRouter(Manager(agents), config, adapter)


def payload(**kwargs):
    return {"routing": "auto", "agentName": "lucy", "question": "Create a boutique image", "accountName": "alice", **kwargs}


def test_specialist_match_sends_only_compact_capability_catalog():
    router = make_router()
    result = router.route(payload(image_ids=["photo"]))
    assert result.selected_agent == "lumia"
    assert result.capabilities == ("image-creation",)
    call = router.llm_adapter.call_model.call_args.kwargs
    assert "tools" not in call
    request = json.loads(call["input"][1]["content"])
    assert request["image_count"] == 1
    assert request["catalog"] == [{"name": "lumia", "skillset": ["image-processing", "image-creation"]}]
    assert "image-cli" not in json.dumps(request)
    assert result.classifier_calls == 1


@pytest.mark.parametrize("overrides,reason", [
    ({"routing": "explicit"}, "explicit_selection"),
    ({"contextName": "project"}, "explicit_context"),
    ({"contextName": "none"}, "explicit_context"),
    ({"question": "Thanks!"}, "conversational"),
    ({"question": "okay"}, "conversational"),
])
def test_no_classifier_for_explicit_or_conversational_requests(overrides, reason):
    router = make_router()
    result = router.route(payload(**overrides))
    assert result.reason == reason
    assert result.selected_agent == "lucy"
    assert result.classifier_calls == 0
    router.llm_adapter.call_model.assert_not_called()


@pytest.mark.parametrize("overrides", [{"question": "thanks, now edit this image"}, {"question": "thanks", "image_ids": ["img"]}])
def test_acknowledgement_near_misses_and_attachments_are_classified(overrides):
    router = make_router()
    router.route(payload(**overrides))
    router.llm_adapter.call_model.assert_called_once()


@pytest.mark.parametrize("classification", [
    {"kind": "specialist", "capabilities": ["image-creation"], "confidence": .2},
    {"kind": "clarify", "capabilities": [], "confidence": 1},
    {"kind": "specialist", "capabilities": ["unknown"], "confidence": 1},
    {"kind": "specialist", "capabilities": [], "confidence": 1},
    {"kind": "general", "capabilities": ["image-creation"], "confidence": 1},
    {"kind": "specialist", "capabilities": "image-creation", "confidence": 1},
    {"kind": "specialist", "capabilities": ["image-creation"], "confidence": True},
    {"kind": "specialist", "capabilities": ["image-creation"], "confidence": float("nan")},
    [],
])
def test_invalid_or_uncertain_classification_does_not_select_specialist(classification):
    router = make_router()
    router.llm_adapter.get_text.return_value = json.dumps(classification)
    result = router.route(payload())
    assert result.selected_agent == "lucy"
    assert result.clarification


def test_classifier_failure_asks_for_guidance():
    router = make_router()
    router.llm_adapter.call_model.side_effect = RuntimeError("unavailable")
    result = router.route(payload())
    assert result.reason == "classifier_failure"
    assert result.clarification


def test_general_and_omitted_agent_use_fallback():
    router = make_router({"kind": "general", "capabilities": [], "confidence": .9})
    assert router.route(payload(agentName="")).selected_agent == "lucy"


def test_duplicate_matches_ask_instead_of_arbitrary_choice():
    router = make_router(agents=[Agent(name="lucy"), Agent(name="a", skillset=["image-creation"]), Agent(name="b", skillset=["image-creation"])])
    assert router.route(payload()).reason == "ambiguous_specialists"


def test_task_requiring_different_specialists_is_not_silently_split():
    router = make_router({"kind": "specialist", "capabilities": ["writing", "image-creation"], "confidence": .95},
        [Agent(name="lucy"), Agent(name="belle", skillset=["writing"]), Agent(name="lumia", skillset=["image-creation"])])
    assert router.route(payload()).reason == "no_match"


def test_internal_and_non_chat_agents_are_excluded():
    router = make_router(agents=[Agent(name="lucy"), Agent(name="mcp", skillset=["image-creation"]),
        Agent(name="worker", message_processor="automation_processor", skillset=["image-creation"])])
    router.config = SimpleNamespace(get=lambda key, default=None: {"direct_answers_enabled": False} if key == "request_routing" else default)
    assert router.catalog() == []
    assert router.route(payload()).reason == "no_specialists"
    router.llm_adapter.call_model.assert_not_called()


def test_recent_history_is_scoped_active_visible_and_bounded():
    router = make_router()
    store = Mock()
    store.get_session.return_value = SimpleNamespace(account_name="alice")
    store.get_recent_events.return_value = SimpleNamespace(events=[
        SimpleNamespace(role="assistant", kind="tool_result", content="secret tool output"),
        *[SimpleNamespace(role="user", kind="user_message", content="x" * 1000) for _ in range(6)],
    ])
    router.episodic_store = store
    router.route(payload(conversationId="session"))
    request = json.loads(router.llm_adapter.call_model.call_args.kwargs["input"][1]["content"])
    assert len(request["recent_conversation"]) == 4
    assert all(len(e["content"]) == 800 for e in request["recent_conversation"])
    assert store.get_recent_events.call_args.kwargs == {"account_name": "alice", "session_id": "session", "count": 4, "event_kinds": ["user_message", "assistant_message"]}


def test_foreign_session_is_rejected_before_reading_history():
    router = make_router()
    store = Mock()
    store.get_session.return_value = SimpleNamespace(account_name="someone_else")
    router.episodic_store = store
    with pytest.raises(ValueError, match="does not belong"):
        router.route(payload(conversationId="session"))
    store.get_session.assert_called_once_with(account_name="alice", session_id="session")
    router.llm_adapter.call_model.assert_not_called()


def test_oversized_request_is_not_silently_routed_from_a_prefix():
    router = make_router()
    result = router.route(payload(question="x" * 12001))
    assert result.reason == "request_too_long"
    assert result.clarification
    assert result.classifier_calls == 0
    router.llm_adapter.call_model.assert_not_called()


def test_history_failure_does_not_execute_a_specialist_without_context():
    router = make_router()
    router.episodic_store = Mock()
    router.episodic_store.get_session.side_effect = OSError("unavailable")
    result = router.route(payload(conversationId="session"))
    assert result.reason == "history_failure"
    assert result.clarification
    router.llm_adapter.call_model.assert_not_called()


def test_classifier_uses_active_fallback_model_and_requests_json():
    router = make_router()
    router.route(payload())
    call = router.llm_adapter.call_model.call_args.kwargs
    assert call['model'] == router.agent_manager.get_agent('lucy').model
    assert call['text'] == {'format': {'type': 'json_object'}}


def test_fenced_json_response_is_accepted():
    router = make_router()
    router.llm_adapter.get_text.return_value = '```json\n{"kind":"specialist","capabilities":["image-processing"],"confidence":0.95}\n```'
    assert router.route(payload()).selected_agent == 'lumia'


def test_image_sidecar_request_routes_by_capability():
    router = make_router({'kind': 'specialist', 'capabilities': ['image-processing'], 'confidence': .95})
    result = router.route(payload(question='i need help with image work - to create new sidecars for the new images in pi_share photography/work/2026/output'))
    assert result.selected_agent == 'lumia'


def test_capability_answer_after_clarification_does_not_repeat_classifier():
    router = make_router()
    router.llm_adapter.call_model.side_effect = RuntimeError('unavailable')
    router.episodic_store = Mock()
    router.episodic_store.get_session.return_value = SimpleNamespace(account_name="alice")
    router.episodic_store.get_recent_events.return_value = SimpleNamespace(events=[
        SimpleNamespace(role='user', kind='user_message', content='Create sidecars for new images'),
        SimpleNamespace(role='assistant', kind='assistant_message', content='Which specialist or type of work should handle this request?'),
    ])
    result = router.route(payload(conversationId='session', question='one that can work with images i.e. image-processing'))
    assert result.selected_agent == 'lumia'
    assert result.reason == 'user_selection'
    assert not result.clarification
    router.llm_adapter.call_model.assert_not_called()


def test_named_specialist_resolves_shared_capability():
    router = make_router(agents=[Agent(name='lucy'), Agent(name='colin', skillset=['development']), Agent(name='star', skillset=['development'])])
    assert router.route(payload(question='development')).clarification.endswith('colin, star.')
    assert router.route(payload(question='colin')).selected_agent == 'colin'
    router.llm_adapter.call_model.assert_not_called()


def test_classifier_failure_does_not_ask_an_unanswerable_generic_question():
    router = make_router()
    router.llm_adapter.call_model.side_effect = RuntimeError('unavailable')
    result = router.route(payload())
    assert result.clarification.startswith('Automatic routing is unavailable.')
    assert 'image-processing' in result.clarification


def test_classifier_model_override_uses_provider_inference():
    router = make_router()
    router.agent_manager.get_agent('lucy').provider = 'deepseek'
    router.config = SimpleNamespace(get=lambda key, default=None: {'model': 'gpt-5-mini'} if key == 'request_routing' else default)
    router.route(payload())
    call = router.llm_adapter.call_model.call_args.kwargs
    assert call['model'] == 'gpt-5-mini'
    assert call['provider'] is None
