import utils.crypto


def test_keypair_generation():
    private_key, public_key = utils.crypto.generate_rsa_keypair()
    assert private_key is not None
    assert public_key is not None


def test_private_key_serialization_deserialization():
    private_key, _ = utils.crypto.generate_rsa_keypair()

    password = b"testpassword"

    pem = utils.crypto.serialize_private_key_to_pem(private_key, password)
    loaded_private_key = utils.crypto.deserialize_private_key_from_pem(pem, password)

    assert private_key.private_numbers() == loaded_private_key.private_numbers()


def test_public_key_serialization_deserialization():
    _, public_key = utils.crypto.generate_rsa_keypair()

    pem = utils.crypto.serialize_public_key_to_pem(public_key)
    loaded_public_key = utils.crypto.deserialize_public_key_from_pem(pem)

    assert public_key.public_numbers() == loaded_public_key.public_numbers()


def test_validate_private_key_password():
    private_key, _ = utils.crypto.generate_rsa_keypair()
    password = b"securepassword"

    pem = utils.crypto.serialize_private_key_to_pem(private_key, password)

    assert utils.crypto.validate_private_key_password(pem, password) is True

    # Catch valuerror for wrong password
    try:
        utils.crypto.validate_private_key_password(pem, b"wrongpassword")
        assert False, "Expected ValueError for wrong password"
    except ValueError:
        pass


def test_string_encryption_decryption_str():
    private_key, public_key = utils.crypto.generate_rsa_keypair()

    original_message = "This is a secret message."

    encrypted_message = utils.crypto.encrypt_string(public_key, original_message)
    decrypted_message = utils.crypto.decrypt_string(private_key, encrypted_message)

    assert original_message == decrypted_message


def test_string_encryption_decryption_bytes():
    private_key, public_key = utils.crypto.generate_rsa_keypair()

    original_message = b"This is a secret message."

    encrypted_message = utils.crypto.encrypt_string(public_key, original_message)
    decrypted_message = utils.crypto.decrypt_string(private_key, encrypted_message)

    assert original_message == bytes(decrypted_message, "utf-8")
