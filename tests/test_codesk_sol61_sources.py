import ast

import pytest

from experiments.codesk_sol61_sources import MODEL, ROOTS, model_replacement


def test_operational_model_literals_replaced_not_comments_or_partial_strings():
    source = b'# gpt-6-sol remains a provenance comment\nMODEL="gpt-6-sol"\nLABEL="old gpt-6-sol trial"\n'
    updated, lines = model_replacement(source)
    assert lines == [2]
    assert b'# gpt-6-sol remains a provenance comment' in updated
    assert b'LABEL="old gpt-6-sol trial"' in updated
    assert ast.parse(updated).body[0].value.value == MODEL


def test_unicode_offsets_and_default_parameter_are_valid():
    source = 'label="中文"; MODEL="gpt-6-sol"\ndef init(model="gpt-6-sol"):\n    return model\n'.encode()
    updated, lines = model_replacement(source)
    assert lines == [1, 2]
    tree = ast.parse(updated)
    assert tree.body[1].value.value == MODEL
    assert tree.body[2].args.defaults[0].value == MODEL


def test_existing_sol61_or_other_models_unchanged():
    source = b'MODEL="gpt-6.1-sol"\nOTHER="gpt-6-astra"\n'
    assert model_replacement(source) == (source, [])


def test_historical_results_not_selected_as_source_roots():
    for roots in ROOTS.values():
        assert not set(roots) & {'outputs', 'runs', 'docs', 'audits', 'benchmarks'}


def test_invalid_source_is_not_silently_rewritten():
    with pytest.raises(SyntaxError):
        model_replacement(b'MODEL=\n')
