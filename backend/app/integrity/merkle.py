import hashlib


def merkle_root(leaf_hashes: list[str]) -> str:
    """Merkle root over hex leaf hashes. Odd levels duplicate the last node."""
    if not leaf_hashes:
        return hashlib.sha256(b"").hexdigest()
    level = [bytes.fromhex(h) for h in leaf_hashes]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()
