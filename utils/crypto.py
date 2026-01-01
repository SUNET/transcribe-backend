import base64
import os
import struct

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from typing import Iterator, Optional, Tuple


def generate_rsa_keypair(
    key_size: Optional[int] = 4096,
) -> Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """
    Generate an RSA key pair.
    Returns a tuple of (private_key, public_key).
    """

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )
    public_key = private_key.public_key()

    return private_key, public_key


def serialize_private_key(
    private_key: rsa.RSAPrivateKey,
    password: bytes,
) -> bytes:
    """
    Serialize the private key to PEM format.
    If a password is provided, the key will be encrypted.
    """

    encryption_algorithm = serialization.BestAvailableEncryption(password)

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=encryption_algorithm,
    )

    return pem


def serialize_public_key(
    public_key: rsa.RSAPublicKey,
) -> bytes:
    """
    Serialize the public key to PEM format.
    """

    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return pem


def deserialize_private_key(
    pem_data: bytes,
    password: bytes,
) -> rsa.RSAPrivateKey:
    """
    Deserialize a PEM-formatted private key.
    If the key is encrypted, provide the password.
    """

    if not isinstance(password, bytes):
        password = password.encode("utf-8")
    if not isinstance(pem_data, bytes):
        pem_data = pem_data.encode("utf-8")

    private_key = serialization.load_pem_private_key(
        pem_data,
        password=password,
    )

    return private_key


def deserialize_public_key(
    pem_data: bytes,
) -> rsa.RSAPublicKey:
    """
    Deserialize a PEM-formatted public key.
    """
    public_key = serialization.load_pem_public_key(
        pem_data,
    )

    return public_key


def validate_password(
    private_key_pem: bytes,
    password: bytes,
) -> bool:
    """
    Validate if the provided password can decrypt the private key.
    Returns True if the password is correct, False otherwise.
    """

    if not isinstance(password, bytes):
        password = password.encode("utf-8")

    try:
        if deserialize_private_key(private_key_pem, password.encode("utf-8")):
            return True
    except Exception as e:
        print(e)
        return False


def encrypt_string(
    public_key: rsa.RSAPublicKey,
    plaintext: str,
) -> bytes:
    """
    Encrypt arbitrarily large strings using hybrid RSA + AES-GCM.
    Returns a binary blob containing:
    [ RSA-encrypted AES key | nonce | AES-GCM ciphertext ]
    """

    # 1. Generate symmetric key
    aes_key = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(aes_key)

    # 2. Encrypt plaintext with AES-GCM
    nonce = os.urandom(12)  # 96-bit nonce (recommended)
    plaintext_bytes = plaintext.encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)

    # 3. Encrypt AES key with RSA
    encrypted_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    result = base64.b64encode(encrypted_key + nonce + ciphertext)

    # 4. Concatenate everything
    return result.decode("utf-8")


def decrypt_string(
    private_key: rsa.RSAPrivateKey,
    blob: str,
) -> str:
    """
    Decrypt data encrypted by encrypt_string().
    """
    blob = base64.b64decode(blob)

    if not isinstance(blob, bytes):
        blob = blob.encode("utf-8")

    # RSA key size determines encrypted AES key length
    rsa_key_size_bytes = private_key.key_size // 8

    encrypted_key = blob[:rsa_key_size_bytes]
    nonce = blob[rsa_key_size_bytes : rsa_key_size_bytes + 12]
    ciphertext = blob[rsa_key_size_bytes + 12 :]

    # 1. Decrypt AES key
    aes_key = private_key.decrypt(
        encrypted_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    # 2. Decrypt message
    aesgcm = AESGCM(aes_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    return plaintext.decode("utf-8")


def encrypt_file(
    public_key: rsa.RSAPublicKey,
    input_bytes: bytes,
    output_filepath: str,
    chunk_size: int = 64 * 1024,
) -> None:
    """
    Split a file into chunks and encrypt each chunk using encrypt_string().
    """

    def write_chunk(chunk: bytes, fout):
        # Binary → base64 text
        chunk_b64 = base64.b64encode(chunk).decode("ascii")

        # Encrypt base64 text
        encrypted_b64 = encrypt_string(public_key, chunk_b64)

        # Write length-prefixed encrypted chunk
        fout.write(struct.pack(">I", len(encrypted_b64)))
        fout.write(encrypted_b64.encode("ascii"))

    i = 0
    with open(output_filepath, "wb") as fout:
        while True:
            chunk = input_bytes[i : i + chunk_size]
            if not chunk:
                break

            write_chunk(chunk, fout)
            i += chunk_size
            print(f"Encrypted chunk {i // chunk_size} written to {output_filepath}")

        fout.flush()


def decrypt_file(
    private_key: rsa.RSAPrivateKey,
    input_filepath: str,
    start_chunk: int = 0,
    end_chunk: Optional[int] = None,
) -> Iterator[bytes]:
    """
    Decrypt a file encrypted by encrypt_file().
    Yields binary chunks.
    Supports optional start_chunk and end_chunk (0-based, inclusive).
    """

    chunk_index = 0

    print(f"Decrypting file: {input_filepath}, chunks {start_chunk} to {end_chunk}")

    with open(input_filepath, "rb") as fin:
        while True:
            length_bytes = fin.read(4)
            if not length_bytes:
                break  # EOF

            (chunk_length,) = struct.unpack(">I", length_bytes)
            encrypted_chunk = fin.read(chunk_length)
            if len(encrypted_chunk) != chunk_length:
                raise ValueError("Unexpected end of file while reading encrypted chunk")

            # Skip chunks before start_chunk
            if chunk_index < start_chunk:
                chunk_index += 1
                continue

            # Stop after end_chunk
            if end_chunk is not None and chunk_index > end_chunk:
                break

            # Decrypt
            decrypted_b64 = decrypt_string(private_key, encrypted_chunk.decode("utf-8"))

            # Convert base64 back to binary
            decrypted_bytes = base64.b64decode(decrypted_b64)

            yield decrypted_bytes
            chunk_index += 1
