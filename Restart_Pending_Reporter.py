import os
import json
import base64
import pyodbc
import subprocess
import logging
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

# Define constants
SECRET_FILE = "secret.json"
PUBLIC_KEY_FILE = "public_key.pem"
PRIVATE_KEY_FILE = "private_key.pem"
DATABASE_NAME = "RestartPendingDetector"
LOG_FILE = "Restart_Pending_Detector.log"

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Generate RSA keys and save them to files
def generate_rsa_keys():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()

    # Save the public key
    with open(PUBLIC_KEY_FILE, "wb") as pub_file:
        pub_file.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))

    # Save the private key
    with open(PRIVATE_KEY_FILE, "wb") as priv_file:
        priv_file.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

# Encrypt data using RSA public key
def encrypt_data(data):
    with open(PUBLIC_KEY_FILE, "rb") as pub_file:
        pub_key = serialization.load_pem_public_key(pub_file.read())
    encrypted_data = pub_key.encrypt(
        data.encode(),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return base64.b64encode(encrypted_data).decode()

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

# Function to get and save MSSQL credentials
def get_and_save_credentials():
    if not os.path.exists(SECRET_FILE):
        # Generate RSA keys if they do not exist
        if not os.path.exists(PUBLIC_KEY_FILE) or not os.path.exists(PRIVATE_KEY_FILE):
            generate_rsa_keys()

        credentials = {
            "server": input("Enter MSSQL server name or IP: "),
            "port": input("Enter MSSQL server port: "),
            "username": input("Enter MSSQL username: "),
            "password": input("Enter MSSQL password: ")
        }
        encrypted_credentials = {k: encrypt_data(v) for k, v in credentials.items()}
        with open(SECRET_FILE, "w") as file:
            json.dump(encrypted_credentials, file)
        print("Credentials saved successfully.")
    else:
        print("Credentials already exist. Skipping input.")

# Function to read and decrypt MSSQL credentials
def read_credentials():
    try:
        with open(SECRET_FILE, "r") as file:
            encrypted_credentials = json.load(file)
        credentials = {k: decrypt_data(v) for k, v in encrypted_credentials.items()}
        return credentials
    except json.JSONDecodeError:
        logging.error("The secret file is corrupted or empty. Please delete the secret file and run the script again.")
        exit(1)

# Function to read the log file
def read_restart_pending_log():
    log_data = {}
    if os.path.exists("Restart_Pending_Detector.log"):
        with open("Restart_Pending_Detector.log", "r") as log_file:
            for line in log_file:
                if "System Name" in line:
                    log_data["system_name"] = line.split(": ")[1].strip()
                elif "System IP Address" in line:
                    log_data["ip_address"] = line.split(": ")[1].strip()
                elif "Unique GUID" in line:
                    log_data["unique_guid"] = line.split(": ")[1].strip()
                elif "Restart Status" in line:
                    log_data["restart_status"] = line.split(": ")[1].strip()
                elif "Last Checked" in line:
                    log_data["last_checked"] = line.split(": ")[1].strip()
    else:
        logging.error("Log file does not exist.")
        exit(1)
    return log_data

# Function to connect to MSSQL and update or insert data
def update_restart_pending_status():
    credentials = read_credentials()
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={credentials['server']},{credentials['port']};"
        f"DATABASE={DATABASE_NAME};"
        f"UID={credentials['username']};"
        f"PWD={credentials['password']};"
    )

    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        log_data = read_restart_pending_log()

        # Check if the GUID already exists in the table
        cursor.execute("SELECT * FROM RestartPendingDetector WHERE unique_guid = ?", log_data["unique_guid"])
        row = cursor.fetchone()

        if row:
            # Update existing row
            cursor.execute("""
                UPDATE RestartPendingDetector
                SET system_name = ?, ip_address = ?, restart_status = ?, last_checked = ?, last_reported = ?
                WHERE unique_guid = ?
            """, log_data["system_name"], log_data["ip_address"], log_data["restart_status"], log_data["last_checked"], log_data["last_checked"], log_data["unique_guid"])
            print("Updated existing row.")
        else:
            # Insert new row
            cursor.execute("""
                INSERT INTO RestartPendingDetector (unique_guid, system_name, ip_address, restart_status, last_checked, last_reported)
                VALUES (?, ?, ?, ?, ?, ?)
            """, log_data["unique_guid"], log_data["system_name"], log_data["ip_address"], log_data["restart_status"], log_data["last_checked"], log_data["last_checked"])
            print("Inserted new row.")

        conn.commit()

        # Write the last reported time
        cursor.execute("SELECT GETDATE()")
        last_reported = cursor.fetchone()[0]
        cursor.execute("UPDATE RestartPendingDetector SET last_reported = ? WHERE unique_guid = ?", last_reported, log_data["unique_guid"])
        conn.commit()

        cursor.close()
        conn.close()

        # Optionally, you can print the last reported time if needed
        print(f"Last Reported Time: {last_reported.strftime('%Y-%m-%d %H:%M:%S')}")

    except pyodbc.Error as e:
        logging.error(f"Database Error: {e}")

# Function to execute external executable
def run_executable():
    try:
        result = subprocess.run(["Restart_Pending_Detector.exe"], check=True, capture_output=True, text=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing Restart_Pending_Detector.exe: {e}")
        logging.error(f"STDOUT: {e.stdout}")
        logging.error(f"STDERR: {e.stderr}")
        exit(1)

# Main function to execute the tasks
def main():
    try:
        run_executable()
        get_and_save_credentials()
        update_restart_pending_status()
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
