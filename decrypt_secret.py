import json
import base64
import sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

# Define constants
SECRET_FILE = "secret.json"
PUBLIC_KEY_FILE = "public_key.pem"
PRIVATE_KEY_FILE = "private_key.pem"

# Decrypt data using RSA private key
def decrypt_data(encrypted_data):
    encrypted_data = base64.b64decode(encrypted_data.encode())
    with open(PRIVATE_KEY_FILE, "rb") as priv_file:
        priv_key = serialization.load_pem_private_key(
            priv_file.read(),
            password=None
        )
    decrypted_data = priv_key.decrypt(
        encrypted_data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return decrypted_data.decode()

# Function to read and decrypt MSSQL credentials
def read_and_decrypt_credentials():
    try:
        with open(SECRET_FILE, "r") as file:
            encrypted_credentials = json.load(file)
        credentials = {k: decrypt_data(v) for k, v in encrypted_credentials.items()}
        return credentials
    except json.JSONDecodeError:
        print("Error: The secret file is corrupted or empty.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

# Main function to execute the tasks
def main():
    credentials = read_and_decrypt_credentials()
    print("Decrypted MSSQL Credentials:")
    for key, value in credentials.items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    main()
