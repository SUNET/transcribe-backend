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

    Parameters:
        key_size (Optional[int]): Size of the RSA key in bits. Default is 4096.

    Returns:
        Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]: The generated RSA private and public keys.
    """

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,  # Commonly used public exponent
        key_size=key_size,
    )

    # Derive public key
    public_key = private_key.public_key()

    return private_key, public_key


def serialize_private_key_to_pem(
    private_key: rsa.RSAPrivateKey,
    password: bytes,
) -> bytes:
    """
    Serialize the private key to PEM format.
    If a password is provided, the key will be encrypted.

    Parameters:
        private_key (rsa.RSAPrivateKey): The RSA private key to serialize.
        password (bytes): The password to encrypt the private key.

    Returns:
        bytes: The PEM-formatted private key.
    """

    # Set up encryption algorithm, BestAvailableEncryption will always
    # default to AES-256-CBC.
    encryption_algorithm = serialization.BestAvailableEncryption(password)

    # Serialize private key to PEM
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=encryption_algorithm,
    )

    return pem


def serialize_public_key_to_pem(
    public_key: rsa.RSAPublicKey,
) -> bytes:
    """
    Serialize the public key to PEM format.

    Parameters:
        public_key (rsa.RSAPublicKey): The RSA public key to serialize.

    Returns:
        bytes: The PEM-formatted public key.
    """

    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return pem


def deserialize_private_key_from_pem(
    pem_data: bytes,
    password: bytes,
) -> rsa.RSAPrivateKey:
    """
    Deserialize a PEM-formatted private key.
    If the key is encrypted, provide the password.

    Parameters:
        pem_data (bytes): The PEM-formatted private key data.
        password (bytes): The password to decrypt the private key.

    Returns:
        rsa.RSAPrivateKey: The deserialized RSA private key.
    """

    # Convert to bytes if necessary
    if not isinstance(password, bytes):
        password = password.encode("utf-8")
    if not isinstance(pem_data, bytes):
        pem_data = pem_data.encode("utf-8")

    private_key = serialization.load_pem_private_key(
        pem_data,
        password=password,
    )

    return private_key


def deserialize_public_key_from_pem(
    pem_data: bytes,
) -> rsa.RSAPublicKey:
    """
    Deserialize a PEM-formatted public key.

    Parameters:
        pem_data (bytes): The PEM-formatted public key data.

    Returns:
        rsa.RSAPublicKey: The deserialized RSA public key.
    """
    public_key = serialization.load_pem_public_key(
        pem_data,
    )

    return public_key


def validate_private_key_password(
    private_key_pem: bytes,
    password: bytes,
) -> bool:
    """
    Validate if the provided password can decrypt the private key.

    Parameters:
        private_key_pem (bytes): The PEM-formatted private key data.
        password (bytes): The password to validate.

    Returns:
        bool: True if the password is correct, False otherwise.
    """

    if not isinstance(password, bytes):
        password = password.encode("utf-8")

    if not isinstance(private_key_pem, bytes):
        private_key_pem = private_key_pem.encode("utf-8")

    if deserialize_private_key_from_pem(private_key_pem, password):
        return True

    return False


def encrypt_string(
    public_key: rsa.RSAPublicKey,
    plaintext: str,
) -> bytes:
    """
    Encrypt arbitrarily large strings using hybrid RSA + AES-GCM.

    Parameters:
        public_key (rsa.RSAPublicKey): The RSA public key for encrypting the AES key.
        plaintext (str): The plaintext string to encrypt.

    Returns:
        bytes: The encrypted data, base64-encoded.
    """

    # 1. Generate symmetric key
    aes_key = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)  # 96-bit nonce (recommended)

    # Convert to bytes if necessary
    if isinstance(plaintext, str):
        plaintext_bytes = plaintext.encode("utf-8")
    else:
        plaintext_bytes = plaintext

    # 2. Encrypt message with AES
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

    Parameters:
        private_key (rsa.RSAPrivateKey): The RSA private key for decrypting the AES key.
        blob (str): The encrypted data, base64-encoded.

    Returns:
        str: The decrypted plaintext string.
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


def encrypt_data_to_file(
    public_key: rsa.RSAPublicKey,
    input_bytes: bytes,
    output_filepath: str,
    chunk_size: int = 64 * 1024,
) -> None:
    """
    Split a file into chunks and encrypt each chunk using encrypt_string().

    Parameters:
        public_key (rsa.RSAPublicKey): The RSA public key for encrypting the data.
        input_bytes (bytes): The binary data to encrypt.
        output_filepath (str): The output file path to write the encrypted data.
        chunk_size (int): The size of each chunk in bytes. Default is 64KB.

    Returns:
        None
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

        fout.flush()


def decrypt_data_from_file(
    private_key: rsa.RSAPrivateKey,
    input_filepath: str,
    start_chunk: int = 0,
    end_chunk: Optional[int] = None,
) -> Iterator[bytes]:
    """
    Decrypt a file encrypted by encrypt_file().
    Yields binary chunks.
    Supports optional start_chunk and end_chunk (0-based, inclusive).

    Parameters:
        private_key (rsa.RSAPrivateKey): The RSA private key for decrypting the data.
        input_filepath (str): The input file path to read the encrypted data.
        start_chunk (int): The starting chunk index (0-based). Default is 0.
        end_chunk (Optional[int]): The ending chunk index (0-based, inclusive). Default is None (no limit).

    Returns:
        Iterator[bytes]: An iterator yielding decrypted binary chunks.

    Raises:
        ValueError: If the file format is invalid or unexpected end of file occurs.
    """

    chunk_index = 0

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
