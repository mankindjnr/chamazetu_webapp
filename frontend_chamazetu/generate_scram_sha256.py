import scramp
import base64
import os


def generate_scram_sha_256_hash(username, password):
    # Create a random salt
    salt = base64.b64encode(os.urandom(16)).decode("utf-8")

    # SCRAM-SHA-256 mechanism
    scram_mechanism = scramp.ScramMechanism("SCRAM-SHA-256")

    # Generate the salted password
    salted_password = scram_mechanism.make_password(password, salt, iterations=4096)

    # SCRAM client
    client = scramp.ScramClient(mechanisms=["SCRAM-SHA-256"])
    client.set_user(username)
    client.set_password(salted_password)

    # Generate client first message bare
    client_first_message_bare = f"n={username},r={client._nonce}"

    # Authenticate
    auth_message = client._generate_auth_message(
        client_first_message_bare, salted_password, salt
    )

    # SCRAM-SHA-256 hash
    scram_hash = f"SCRAM-SHA-256${salt}${auth_message}"

    return scram_hash


# Replace with your username and password
username = "mankindjnr"
password = "tNNhwY1XOwwQPkhL"

scram_hash = generate_scram_sha_256_hash(username, password)
print(scram_hash)
