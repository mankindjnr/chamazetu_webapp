from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64


def load_public_key():
    try:
        with open(
            "../../public_key.pem", "rb"
        ) as cert_file:  # Or "ProductionCertificate.cer"
            public_key = serialization.load_pem_public_key(
                cert_file.read(), backend=default_backend()
            )
        print("Public key loaded successfully")
        return public_key
    except Exception as e:
        print(f"Failed to load public key: {str(e)}")
        return None


def encrypt_security_credential(plaintext_password: str) -> str:
    public_key = load_public_key()
    if public_key is None:
        raise Exception("Failed to load public key.")

    # Encrypt the password
    encrypted_password = public_key.encrypt(
        plaintext_password.encode(),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    # Return the base64 encoded encrypted string
    return base64.b64encode(encrypted_password).decode("utf-8")
