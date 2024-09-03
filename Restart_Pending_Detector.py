import socket
import os
import hashlib
import uuid
import winreg
from datetime import datetime

# Define the log file name
log_file = "Restart_Pending_Detector.log"

# Function to update or append content in the log file
def update_log(content_type, content):
    updated = False
    new_lines = []
    
    # Read the existing log file
    if os.path.exists(log_file):
        with open(log_file, "r") as log:
            lines = log.readlines()
        
        # Update existing content or collect lines to write
        for line in lines:
            if not line.startswith(content_type):
                new_lines.append(line)
            else:
                # Update the existing content if found
                new_lines.append(f"{content_type}: {content}\n")
                updated = True
    
    # If not updated, append the new content
    if not updated:
        new_lines.append(f"{content_type}: {content}\n")
    
    # Write updated content back to the log file
    with open(log_file, "w") as log:
        log.writelines(new_lines)
    
    print(f"Updated log with {content_type}: {content}")

# Get the system name
system_name = socket.gethostname()

# Get the system IP address
def get_ip_address():
    return socket.gethostbyname(socket.gethostname())

# Generate a unique identifier that remains the same unless the OS is reinstalled
def generate_unique_guid():
    try:
        # Windows: Get MachineGuid from the registry
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Cryptography')
        machine_guid, _ = winreg.QueryValueEx(key, 'MachineGuid')
        winreg.CloseKey(key)

        unique_guid = hashlib.sha256(machine_guid.encode()).hexdigest()
    except Exception as e:
        unique_guid = str(uuid.uuid4())  # Fallback to a random UUID
        print(f"Failed to generate consistent GUID, fallback to random UUID: {e}")

    return unique_guid

# Check for restart pending conditions in the Windows Registry
def check_restart_pending():
    keys_to_check = [
        r'SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending',
        r'SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired',
        r'SYSTEM\CurrentControlSet\Control\Session Manager\PendingFileRenameOperations'
    ]
    
    restart_required = False
    
    for key in keys_to_check:
        try:
            reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key)
            winreg.CloseKey(reg_key)
            restart_required = True
            break
        except FileNotFoundError:
            continue
    
    return "Restart Required" if restart_required else "Restart Not-Required"

# Collect all data
ip_address = get_ip_address()
unique_guid = generate_unique_guid()
restart_status = check_restart_pending()
execution_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Update the log file with the latest information
update_log("System Name", system_name)
update_log("System IP Address", ip_address)
update_log("Unique GUID", unique_guid)
update_log("Restart Status", restart_status)
update_log("Last Checked", execution_time)
