import bcrypt

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    Returns the hash as a utf-8 string.
    """
    if not password:
        return ""
    # bcrypt.hashpw expects bytes
    pw_bytes = password.encode('utf-8')
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against a bcrypt hash.
    """
    if not password or not hashed_password:
        return False
    try:
        pw_bytes = password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception:
        return False
