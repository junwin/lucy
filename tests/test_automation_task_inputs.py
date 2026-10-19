"""Characterize the input boundary through the real automation coordinator."""

from copy import deepcopy

import pytest

from tests.test_automation_processor_nullable_inputs import (
    FakeStorage,
    RecordingFunctionProcessor,
    make_tasklist,
    run_tasklist,
)
from src.tasklists.task import Task
from src.tasklists.task_states import TASK_STATE_RUNNING, TASK_STATE_COMPLETED, TASK_STATE_FAILED


@pytest.mark.parametrize(
    'attachments, expected_files, expected_images',
    [
        ({'files': [1, 'two'], 'file': 'ignored', 'image_ids': [3]}, ['1', 'two'], ['3']),
        ({'files': [], 'file': 'ignored', 'image_ids': []}, [], []),
        ({'files': 'invalid', 'file': 7, 'image_ids': 'invalid'}, ['7'], None),
        ({'files': None, 'file': None}, None, None),
        ({}, None, None),
    ],
)
def test_input_order_attachment_precedence_and_checkpoint_mutation(
    monkeypatch, attachments, expected_files, expected_images
):
    tasklist = make_tasklist(instructions='  task instructions  ')
    tasklist.general_instructions = '  general instructions  '
    task = tasklist.tasks[0]
    task.meta = {**attachments, ' title ': 'example', '': 'skip', 'count': 2}
    original_meta = deepcopy(task.meta)
    snapshots = []

    def save(storage, account, key, data):
        snapshots.append((data.tasks[0].state, deepcopy(data.tasks[0].meta)))

    monkeypatch.setattr(FakeStorage, 'save_tasklist', save)
    processor = RecordingFunctionProcessor()
    run_tasklist(processor, tasklist)

    assert len(processor.calls) == 1
    call = processor.calls[0]
    assert call['message'] == 'general instructions\ntask instructions\ntitle = example\ncount = 2'
    assert call['file_ids'] == expected_files
    assert call['image_ids'] == expected_images
    assert snapshots[0] == (TASK_STATE_RUNNING, original_meta)
    remaining = {' title ': 'example', '': 'skip', 'count': 2}
    assert snapshots[1:] == [(TASK_STATE_COMPLETED, remaining)] * 2
    assert task.meta == remaining


def test_general_instructions_can_supply_an_otherwise_empty_task():
    tasklist = make_tasklist(instructions='')
    tasklist.general_instructions = '  use these instructions  '
    processor = RecordingFunctionProcessor()
    run_tasklist(processor, tasklist)
    assert [call['message'] for call in processor.calls] == ['use these instructions']


def test_attachment_only_task_keeps_existing_empty_message_warning():
    tasklist = make_tasklist(instructions='')
    tasklist.tasks[0].meta = {'files': ['file-1'], 'image_ids': ['image-1']}
    processor = RecordingFunctionProcessor()
    result, _, task, storage = run_tasklist(processor, tasklist)
    assert processor.calls == []
    assert task.meta == {}
    assert 'has no instructions' in result
    assert 'warning' in storage.records[0]['result']


def test_without_function_processor_attachments_are_not_consumed():
    tasklist = make_tasklist()
    tasklist.tasks[0].meta = {'files': ['file-1']}
    _, _, task, storage = run_tasklist(None, tasklist)
    assert task.meta == {'files': ['file-1']}
    assert 'note' in storage.records[0]['result']


def test_running_checkpoint_failure_prevents_input_consumption_and_execution(monkeypatch):
    tasklist = make_tasklist()
    tasklist.tasks[0].meta = {'files': ['file-1']}
    processor = RecordingFunctionProcessor()

    def fail_save(*args):
        raise OSError('checkpoint unavailable')

    monkeypatch.setattr(FakeStorage, 'save_tasklist', fail_save)
    result, _, task, storage = run_tasklist(processor, tasklist)
    assert 'Failed to persist RUNNING checkpoint' in result
    assert task.meta == {'files': ['file-1']}
    assert task.state == TASK_STATE_FAILED
    assert processor.calls == []
    assert storage.records == []


def test_multi_step_composes_each_task_once_in_sequence():
    tasklist = make_tasklist(instructions='first')
    tasklist.general_instructions = 'common'
    tasklist.tasks[0].meta = {'files': ['file-1']}
    tasklist.tasks.append(Task(id='second', name='T2', instructions='second', meta={'file': 'file-2'}))
    processor = RecordingFunctionProcessor()
    _, _, _, storage = run_tasklist(processor, tasklist, mode='multi-step')
    assert [(c['message'], c['file_ids']) for c in processor.calls] == [
        ('common\nfirst', ['file-1']), ('common\nsecond', ['file-2'])
    ]
    assert [r['task_id'] for r in storage.records] == [t.id for t in tasklist.tasks]
    assert all(t.state == TASK_STATE_COMPLETED and t.meta == {} for t in tasklist.tasks)
