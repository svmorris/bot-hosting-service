"""
    This module has all security related functions
    like password hashes, UUID's and other filtering
    functions.
    The goal of this is that we can replace the way
    something is verified or hashed in one place
    rather than making sure its changed everywhere.
"""

import uuid
import string
import bcrypt


def is_uuid(uid: str) -> bool:
    """ Function verifies if string is a valid UUID """
    uid = str(uid)

    # UUID's can only contain hexdigits and hyphens
    for char in uid:
        if char not in string.hexdigits + '-':
            return False

    try:
        uuid.UUID(uid).version
    except NameError:
        return False

    return True




def gen_uuid() -> str:
    """
        Generates uuid.
        This is its own function so it can be
        be changed in one place if need be.
    """
    return str(uuid.uuid1())

def hash_password(password: str) -> str:
    """ bcrypt hash password for storage """
    password_bytes = password.encode("utf-8")
    password_encrypted = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=8))
    return password_encrypted.decode("utf-8")


def check_password(password: str, hashedpw: str) -> bool:
    """
        Use the built in password check
        to verify a password with salt.
        Returns:
            Boolian representing whether or not
            the password is correct.
    """
    password_bytes = password.encode("utf-8")
    hashedpw_bytes = hashedpw.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashedpw_bytes)
