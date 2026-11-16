import hashlib

from django.contrib.auth.hashers import PBKDF2PasswordHasher


class LegacyPBKDF2SHA256PasswordHasher(PBKDF2PasswordHasher):
    """Read the original raw-byte salts; Django upgrades these hashes at login."""

    algorithm = "legacy_pbkdf2_sha256"
    iterations = 200_000

    def encode(self, password, salt, iterations=None):
        self._check_encode_args(password, salt)
        iterations = iterations or self.iterations
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
        return f"{self.algorithm}${iterations}${salt}${digest.hex()}"
