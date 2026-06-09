# Credits: TSun × Kittens
"""
core/crypto.py
~~~~~~~~~~~~~~
Low-level cryptography helpers: AES-CBC encryption and lightweight
protobuf-style binary encoding used when communicating with the
FreeFire / Garena endpoints.
"""

from __future__ import annotations

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


# ── Varint (Protocol-Buffer style) ────────────────────────────────────────────

def encode_varint(value: int) -> bytes:
    """Encode a non-negative integer as a protobuf-style varint."""
    if value < 0:
        return b""
    chunks: list[int] = []
    while True:
        chunk = value & 0x7F
        value >>= 7
        if value:
            chunk |= 0x80
        chunks.append(chunk)
        if not value:
            break
    return bytes(chunks)


def create_varint_field(field_number: int, value: int) -> bytes:
    """Encode a varint field (wire type 0)."""
    header = (field_number << 3) | 0
    return encode_varint(header) + encode_varint(value)


def create_length_delimited_field(field_number: int, value: str | bytes) -> bytes:
    """Encode a length-delimited field (wire type 2)."""
    header = (field_number << 3) | 2
    payload = value.encode() if isinstance(value, str) else value
    return encode_varint(header) + encode_varint(len(payload)) + payload


def build_proto_packet(fields: dict) -> bytes:
    """
    Recursively build a raw protobuf-style binary packet from a dict.

    Keys are field numbers (int). Values may be:
        - int   → varint field
        - str   → length-delimited field
        - bytes → length-delimited field
        - dict  → nested message (length-delimited)
    """
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested = build_proto_packet(value)
            packet.extend(create_length_delimited_field(field, nested))
        elif isinstance(value, int):
            packet.extend(create_varint_field(field, value))
        elif isinstance(value, (str, bytes)):
            packet.extend(create_length_delimited_field(field, value))
    return bytes(packet)


# ── AES-CBC Encryption ────────────────────────────────────────────────────────

_AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
_AES_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])


def aes_encrypt_hex(hex_payload: str) -> bytes:
    """Decrypt a hex string, AES-CBC-encrypt it, return raw ciphertext bytes."""
    plaintext = bytes.fromhex(hex_payload)
    cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
    return cipher.encrypt(pad(plaintext, AES.block_size))


def aes_encrypt_to_hex(hex_payload: str) -> str:
    """AES-CBC-encrypt a hex payload and return the ciphertext as a hex string."""
    plaintext = bytes.fromhex(hex_payload)
    cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
    return cipher.encrypt(pad(plaintext, AES.block_size)).hex()
