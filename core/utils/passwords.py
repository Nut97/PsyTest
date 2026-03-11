from __future__ import annotations

import hashlib


def encrypt_password(raw_password: str) -> str:
    md5_hex = hashlib.md5(str(raw_password).encode('utf-8')).hexdigest()
    return hashlib.sha1(md5_hex.encode('utf-8')).hexdigest()


def raw_password_from_id(id_number: str) -> str:
    value = str(id_number).strip()
    if len(value) < 6:
        raise ValueError('身份证号长度不足 6 位')
    return value[-6:]


def encrypt_password_from_id(id_number: str) -> str:
    return encrypt_password(raw_password_from_id(id_number))