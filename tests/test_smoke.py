"""Basic smoke tests: make sure the core package modules import cleanly."""

import photoagents
from photoagents.core import loop


def test_package_has_version():
    assert isinstance(photoagents.__version__, str)
    assert photoagents.__version__


def test_step_outcome_defaults():
    outcome = loop.StepOutcome(data={"ok": True})
    assert outcome.next_prompt is None
    assert outcome.should_exit is False


def test_json_default_handles_sets():
    assert sorted(loop.json_default({1, 2, 3})) == [1, 2, 3]
