import json
from types import SimpleNamespace

from src.handlers.text_replace_handler import TextReplaceHandler
from src.message_processors.edit_diagnostics import log_edit_diagnostic
from src.prompt_builders.prompt_sections import PromptSections


def test_lucy_text_replace_uses_named_root(tmp_path):
    target=tmp_path/'index.html';target.write_text('<img src="old.jpg">')
    config=SimpleNamespace(get=lambda key, default=None: {'external_roots': {'boutique':str(tmp_path)}}.get(key,default))
    result=TextReplaceHandler(config).execute({'external_root':'boutique','path':'index.html',
        'old_text':'old.jpg','new_text':'New Arrivals.jpg','check_only':False})
    assert result['applied']
    assert target.read_text()=='<img src="New Arrivals.jpg">'


def test_prompt_includes_exact_edit_and_recovery_guidance():
    agent=SimpleNamespace(allowed_tools=['text_replace'])
    config=SimpleNamespace(get=lambda key, default=None: {'external_roots':{'repo':'/tmp/repo'}}.get(key,default))
    guidance=PromptSections.build_file_root_instructions(config,agent)
    assert 'prefer text_replace' in guidance
    assert 'matches exactly once' in guidance
    assert 'unchanged context lines' in guidance
    assert 'do not repeatedly guess' in guidance


def test_edit_log_is_parseable_bounded_and_excludes_unrelated_fields(caplog):
    with caplog.at_level('INFO'):
        log_edit_diagnostic('patch_apply', json.dumps({'patch_content':'p'*20000,
            'path':'index.html','password':'hidden'}), {'ok':False,'stderr':'s'*10000,
            'api_key':'hidden','error_code':'malformed_patch'}, correlation_id='cid',call_id='call')
    import ast
    data=json.loads(ast.literal_eval(caplog.records[0].getMessage().split(' diagnostic=',1)[1]))
    assert len(data['parameters']['patch_content'])<16100
    assert len(data['result']['stderr'])<4100
    assert 'hidden' not in json.dumps(data)
    assert data['result']['error_code']=='malformed_patch'


def test_other_tools_do_not_get_edit_diagnostics(caplog):
    with caplog.at_level('INFO'):
        log_edit_diagnostic('file_load', {}, {}, correlation_id='cid',call_id='call')
    assert not caplog.records


def test_raw_patch_execution_logs_diagnostics_without_breaking_loop(make_proc, llm_adapter, caplog):
    from tests.conftest import FakeAgent, FakeRegistry, setup_tool_then_text
    class RawPatch:
        def execute_raw(self, arguments_raw, **context):
            return json.dumps({'ok':False,'applied':False,'error_code':'zero_context_hunk',
                               'stderr':'patch does not apply','details':'Use text_replace'})
    registry=FakeRegistry(handler_by_name={'patch_apply':RawPatch()},tool_defs=[{'name':'patch_apply'}])
    agent=FakeAgent(max_function_call_iterations=3)
    agent.allowed_tools=['patch_apply']
    setup_tool_then_text(llm_adapter,tool_name='patch_apply',
        tool_args=json.dumps({'path':'index.html','patch_content':'--- a/index.html\n+++ b/index.html\n'}),
        final_text='Patch needs context')
    proc=make_proc(registry=registry)
    with caplog.at_level('INFO'):
        result=proc.process_message(primary_agent=agent,account={'accountId':'alice'},
                                    message='Change image',conversation_id='session')
    assert result.text=='Patch needs context'
    assert 'tool_edit_diagnostic' in caplog.text
    assert 'zero_context_hunk' in caplog.text
