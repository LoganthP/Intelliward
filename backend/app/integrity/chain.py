import hashlib

GENESIS_HASH = "0" * 64


def chain_hash(prev_hash: str, canonical_payload: str) -> str:
    """h_i = SHA256(h_{i-1} || m_i)"""
    return hashlib.sha256((prev_hash + canonical_payload).encode("utf-8")).hexdigest()


def anchor_hash(prev_anchor: str, merkle_root: str) -> str:
    """a_k = SHA256(a_{k-1} || r_k)"""
    return hashlib.sha256((prev_anchor + merkle_root).encode("utf-8")).hexdigest()
