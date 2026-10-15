"""Regression coverage for the probe's strict function schema."""
from types import SimpleNamespace

import pytest

from src.handlers import tool_selection_probe_handler as probe


def test_probe_schema_requires_every_property_and_accepts_null_overrides():
    tool = probe.ToolSelectionProbeHandler.tool_def()
    schema = tool['parameters']
    assert tool['strict'] is True
    assert schema['additionalProperties'] is False
    assert set(schema['required']) == set(schema['properties'])
    assert schema['properties']['prompt_text']['type'] == 'string'
    for name in ('account_name', 'context_name'):
        assert set(schema['properties'][name]['type']) == {'string', 'null'}


@pytest.mark.parametrize('overrides,expected', [
    ({'account_name': None, 'context_name': None}, ('junwin', 'request-context')),
    ({'account_name': 'other', 'context_name': 'override'}, ('other', 'override')),
])
def test_probe_resolves_nullable_and_explicit_overrides(monkeypatch, overrides, expected):
    calls = []

    class Pipeline:
        def __init__(self, **kwargs):
            pass

        def resolve(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(allowed=[], all_tools=[], eligible=[],
                                   required=[], prompt_based=[], active=[], meta={})

    monkeypatch.setattr(probe, 'ToolSelectionPipeline', Pipeline)
    result = probe.ToolSelectionProbeHandler(config={}).execute(
        {'prompt_text': 'Inspect selection', **overrides},
        account_name='junwin', context_name='request-context')
    assert result['ok'] is True
    assert (calls[0]['account_name'], calls[0]['context_name']) == expected
