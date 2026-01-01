import os

import base64

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from typing import Optional, Tuple


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


def validate_password(
    private_key_pem: bytes,
    password: bytes,
) -> bool:
    """
    Validate if the provided password can decrypt the private key.
    Returns True if the password is correct, False otherwise.
    """

    try:
        if deserialize_private_key(private_key_pem, password.encode("utf-8")):
            return True
    except Exception as e:
        print(e)
        return False


if __name__ == "__main__":
    # Example usage
    private_key, public_key = generate_rsa_keypair()
    password = b"my_secure_password"

    serialized_private = serialize_private_key(private_key, password)
    serialized_public = serialize_public_key(public_key)
    deserialized_private = deserialize_private_key(serialized_private, password)
    deserialized_public = deserialize_public_key(serialized_public)

    message = """1\n00:00:00,000 --> 00:00:05,600\nRedan innan man vaknar på\nmorgonen känner man att här...\n\n2\n00:00:05,600 --> 00:00:11,760\nkommer ännu en dag fylld av\nmotgångar. Jag vet inte om jag orkar.\n\n3\n00:00:11,760 --> 00:00:17,360\nSå där känner alla av och till.\nDet finns faktiskt ett bra knep\n\n4\n00:00:17,360 --> 00:00:23,240\nför att slippa just det där\neländet och få tillbaka motivationen.\n\n5\n00:00:23,240 --> 00:00:26,240\nSka jag berätta? Ja, gärna.\n\n6\n00:00:26,240 --> 00:00:30,000\nDu börjar på morgonen\noch tar en stadig whisky.\n\n7\n00:00:30,000 --> 00:00:33,000\nSen klarar du dig fram till tiotiden.\n\n8\n00:00:33,000 --> 00:00:35,960\nDu måste ha\nhalstabletter. Det får inte lukta.\n\n9\n00:00:35,960 --> 00:00:39,800\nSen kan du köra en\nFenebranka. Det är jättebra.\n\n10\n00:00:39,800 --> 00:00:42,640\nDå klarar du dig fram till lunch.\n\n11\n00:00:42,640 --> 00:00:47,800\nOch på lunchen är det inte\nsärskilt svårt att få en starköl\n\n12\n00:00:47,800 --> 00:00:52,040\natt se ut som en lättöl. Då\ntar du en tre, fyra lättöl.\n\n13\n00:00:52,040 --> 00:00:55,000\nMan kan inte gå omkring på\njobbet och vara packad hela dagarna.\n\n14\n00:00:55,000 --> 00:01:00,000\nDet är bättre än att gå\nomkring och må dåligt hela tiden.\n\n15\n00:01:00,000 --> 00:01:04,560\nSen på eftermiddagen vid tretiden\nkan du gå tillbaka till whisky igen.\n\n16\n00:01:04,560 --> 00:01:08,800\nDet går bra. Och rätt vad\ndet är, så är klockan fem.\n\n17\n00:01:08,800 --> 00:01:13,760\nOch du har inte märkt\nett dugg. Det funkar. Skål.\n\n"""

    ciphertext = encrypt_string(deserialized_public, message)
    decrypted_message = decrypt_string(deserialized_private, ciphertext)

    assert message == decrypted_message

    print("Encryption and decryption successful!")
