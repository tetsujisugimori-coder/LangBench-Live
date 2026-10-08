"""Frozen raw v2 snapshot reader from published 0ddeae3cdc76992a1a3d7ec6508039e73d8b00e6.
Function body is byte-for-byte, with imports supplied. It must reject encoded state.
"""
import re
from tools import startup_preparation as preparation
from tools.preparation_github import block, PreparationConflict
def snapshot_v2(body):
    contract = preparation.evidence_contract()
    if body.count('<!-- langbench-preparation-snapshot:') != 1:
        raise PreparationConflict('Mixed snapshot versions')
    saved = block(body, contract.SNAPSHOT_START, preparation.SNAPSHOT_END)
    contract.fields(saved, {'schema_version', 'kind', 'comment_id', 'input_version', 'input_digest', 'state', 'source_digest'}, 'v2 snapshot')
    if (type(saved['schema_version']) is not int or saved['schema_version'] != 2
            or saved['kind'] != 'startup_preparation_snapshot' or not contract.positive(saved['comment_id'])
            or not isinstance(saved['source_digest'], str) or not re.fullmatch('[a-f0-9]{64}', saved['source_digest'])):
        raise PreparationConflict('Invalid snapshot identity/version')
    state = contract.validate_state(saved['state'])
    if saved['input_version'] != state['input']['input_version'] or saved['input_digest'] != state['input_digest']:
        raise PreparationConflict('Mixed snapshot input binding')
    return saved
