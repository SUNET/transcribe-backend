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
    aes_key: Optional[bytes] = None,
    aesgcm: Optional[AESGCM] = None,
) -> str:
    """
    Encrypt arbitrarily large strings using hybrid RSA + AES-GCM.

    Parameters:
        public_key (rsa.RSAPublicKey): The RSA public key for encrypting the AES key.
        plaintext (str): The plaintext string to encrypt.
        aes_key (Optional[bytes]): Existing AES key to reuse.
        aesgcm (Optional[AESGCM]): Existing AESGCM instance to reuse.

    Returns:
        str: The encrypted data, represented as a hex string (safe for DB text columns).
    """

    # 1. Generate symmetric key
    if aes_key is None:
        aes_key = AESGCM.generate_key(bit_length=256)

    if aesgcm is None:
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

    # 4. Concatenate everything and return as hex string
    result_bytes = encrypted_key + nonce + ciphertext
    return result_bytes.hex()  # hex is pure ASCII, no NULs


def decrypt_string(
    private_key: rsa.RSAPrivateKey,
    blob: str,
) -> str:
    """
    Decrypt data encrypted by encrypt_string().

    Parameters:
        private_key (rsa.RSAPrivateKey): The RSA private key for decrypting the AES key.
        blob (str): The encrypted data as a hex string.

    Returns:
        str: The decrypted plaintext string.
    """
    # Convert hex string back to raw bytes
    if isinstance(blob, str):
        blob_bytes = bytes.fromhex(blob)
    else:
        blob_bytes = blob

    # RSA key size determines encrypted AES key length
    rsa_key_size_bytes = private_key.key_size // 8

    encrypted_key = blob_bytes[:rsa_key_size_bytes]
    nonce = blob_bytes[rsa_key_size_bytes : rsa_key_size_bytes + 12]
    ciphertext = blob_bytes[rsa_key_size_bytes + 12 :]

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
    chunk_size: int = 1024 * 1024,  # 1MB chunks by default for fewer iterations
) -> None:
    """
    Split a buffer into chunks and encrypt each chunk using encrypt_string().
    """

    aes_key = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(aes_key)

    with open(output_filepath, "wb") as fout:
        length_pack = struct.pack  # local binding for speed
        encode_utf8 = str.encode

        input_len = len(input_bytes)
        i = 0
        while i < input_len:
            chunk = input_bytes[i : i + chunk_size]

            # Convert raw bytes to hex text (no NULs)
            chunk_hex = chunk.hex()

            # Encrypt hex text (reuses AES key and AESGCM instance)
            encrypted_text = encrypt_string(public_key, chunk_hex, aes_key, aesgcm)

            # UTF-8 encode the outer hex and write length-prefixed
            encoded = encode_utf8(encrypted_text, "utf-8")
            fout.write(length_pack(">I", len(encoded)))
            fout.write(encoded)

            i += chunk_size

        fout.flush()


def decrypt_data_from_file(
    private_key: rsa.RSAPrivateKey,
    input_filepath: str,
    start_chunk: int = 0,
    end_chunk: Optional[int] = None,
) -> Iterator[bytes]:
    """
    Decrypt a file encrypted by encrypt_data_to_file().
    Yields binary chunks.
    """

    chunk_index = 0
    unpack = struct.unpack
    decode_utf8 = bytes.decode

    with open(input_filepath, "rb") as fin:
        while True:
            length_bytes = fin.read(4)
            if not length_bytes:
                break  # EOF

            (chunk_length,) = unpack(">I", length_bytes)
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

            # Decrypt (outer is UTF-8 text, hex from encrypt_data_to_file)
            encrypted_text = decode_utf8(encrypted_chunk, "utf-8")
            decrypted_hex = decrypt_string(private_key, encrypted_text)

            # Convert inner hex back to original binary
            yield bytes.fromhex(decrypted_hex)

            chunk_index += 1
