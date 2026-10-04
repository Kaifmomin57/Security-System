"""
evidence/hasher.py
───────────────────
SHA-256 tamper-proof hashing for saved clips and snapshots.
Hash is computed at save time and stored in the DB event record.
"""

import hashlib
import logging
import os

logger = logging.getLogger(__name__)


def hash_file(file_path: str) -> str:
    """
    Compute SHA-256 hash of a file.
    Returns hex digest string, or empty string if file not found.
    """
    if not os.path.isfile(file_path):
        logger.warning(f"Cannot hash — file not found: {file_path}")
        return ""

    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        digest = sha256.hexdigest()
        logger.info(f"SHA-256 [{os.path.basename(file_path)}]: {digest[:16]}...")
        return digest
    except Exception as e:
        logger.error(f"Hashing failed for {file_path}: {e}")
        return ""


def verify_file(file_path: str, expected_hash: str) -> bool:
    """
    Verify a file's integrity against a stored hash.
    Returns True if the file is untampered.
    """
    current = hash_file(file_path)
    match = current == expected_hash
    if not match:
        logger.error(f"⚠️ TAMPER DETECTED: {file_path}")
    return match
