"""Review states never upgrade declared receipts into independent proof."""
import json

import pytest

from exporters.skill_bundle import compile_skill_bundle
from test_trust_codex_ld import owned_case  # noqa: F401


@pytest.mark.parametrize('state', ['observed', 'inferred', 'uncertain', 'verified_by_execution'])
def test_owned_observation_retains_explicit_verification_scope(tmp_path, owned_case, state):
    source, claim = owned_case
    claim.update(review_state=state, requires_human_approval=True)
    target = tmp_path / 'scope.json'
    bundle = compile_skill_bundle([claim], source, str(target))
    assert json.loads(target.read_text()) == bundle
    assert bundle['procedure_claims'] == [claim]
    assert not {'evidence_backed', 'hard_proof_boundary'} & bundle.keys()
    assert bundle['review_gate_passed'] is True
    assert bundle['verification_scope'] == {
        'authorization': 'declared', 'references': 'IDs_present_unresolved',
        'execution': 'reported_receipts_not_independently_verified',
    }
