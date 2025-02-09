#!/usr/bin/env python3
"""
network.py

This module provides helper functions for handling network configuration,
including generating random MAC addresses, retrieving current MAC and Wi-Fi
information, listing available networks, checking the AP status, and updating
the hostapd configuration.
"""

import os
import random
import subprocess
import re

# Constant for hostapd configuration file (adjust the path as needed)
HOSTAPD_CONF = '/etc/hostapd/hostapd.conf'


def random_mac():
    """
    Generate a semi-random locally administered MAC address.

    Returns:
        str: A MAC address in the format xx:xx:xx:xx:xx:xx.
    """
    mac = [
        0x02, 0x00, 0x00,  # Locally administered MAC prefix
        random.randint(0x00, 0x7f),
        random.randint(0x00, 0xff),
        random.randint(0x00, 0xff)
    ]
    return ':'.join(f"{byte:02x}" for byte in mac)


def get_current_mac(interface='wlan0'):
    """
    Retrieve the current MAC address of the specified network interface.

    Args:
        interface (str): The network interface (default 'wlan0').

    Returns:
        str: The MAC address or "Unknown" if not found.
    """
    try:
        result = subprocess.check_output(['ip', 'link', 'show', interface], text=True)
        match = re.search(r"link/ether ([0-9a-f:]{17})", result)
        if match:
            return match.group(1)
        else:
            print(f"Could not parse MAC address for interface {interface}.")
    except subprocess.CalledProcessError as e:
        print(f"Error running 'ip' command: {e}")
    except Exception as e:
        print(f"Error retrieving current MAC: {e}")
    return "Unknown"


def get_current_ssid():
    """
    Get the currently connected Wi-Fi SSID using nmcli.

    Returns:
        str: The SSID of the currently connected Wi-Fi network, or "Unknown".
    """
    try:
        result = subprocess.check_output(['nmcli', '-t', '-f', 'ACTIVE,SSID', 'dev', 'wifi'], text=True)
        for line in result.splitlines():
            if line.startswith('yes:'):
                parts = line.split(':', 1)
                if len(parts) > 1:
                    return parts[1]
    except subprocess.CalledProcessError as e:
        print(f"Error getting current SSID: {e}")
    return "Unknown"


def get_available_networks():
    """
    Retrieve a list of available Wi-Fi SSIDs using nmcli.

    Returns:
        list: A sorted list of unique SSIDs.
    """
    try:
        result = subprocess.check_output(['nmcli', '-t', '-f', 'SSID', 'dev', 'wifi'], text=True)
        ssids = list(filter(None, result.splitlines()))
        return sorted(set(ssids))
    except subprocess.CalledProcessError as e:
        print(f"Error getting available networks: {e}")
    return []


def get_ap_status():
    """
    Check if the 'wlan0_ap' interface is active and retrieve the SSID from hostapd.conf.

    Returns:
        tuple: (status (bool), ssid (str))
    """
    try:
        result = subprocess.check_output(['ip', 'addr', 'show', 'wlan0_ap'], text=True)
        if 'state UP' in result:
            ssid = ''
            try:
                with open(HOSTAPD_CONF, 'r') as f:
                    for line in f:
                        if line.startswith('ssid='):
                            ssid = line.split('=')[1].strip()
                            break
            except Exception as e:
                print(f"Error reading hostapd config: {e}")
            return True, ssid
        return False, ''
    except subprocess.CalledProcessError as e:
        print(f"Error checking wlan0_ap status: {e}")
        return False, ''


def update_hostapd_config(new_ssid, new_password):
    """
    Update the hostapd configuration with a new SSID and password, then restart hostapd.

    Args:
        new_ssid (str): New SSID.
        new_password (str): New Wi-Fi password.

    Returns:
        bool: True if the configuration update and service restart succeeded; False otherwise.
    """
    temp_file = '/tmp/hostapd_temp.conf'
    try:
        with open(HOSTAPD_CONF, 'r') as f:
            lines = f.readlines()

        updated_lines = []
        for line in lines:
            if line.startswith('ssid='):
                updated_lines.append(f'ssid={new_ssid}\n')
            elif line.startswith('wpa_passphrase='):
                updated_lines.append(f'wpa_passphrase={new_password}\n')
            else:
                updated_lines.append(line)

        with open(temp_file, 'w') as f:
            f.writelines(updated_lines)

        # Replace the hostapd configuration file
        result = subprocess.run(['sudo', 'mv', temp_file, HOSTAPD_CONF], check=False)
        if result.returncode != 0:
            print("Failed to replace the hostapd.conf file.")
            return False

        # Verify that the changes were written
        with open(HOSTAPD_CONF, 'r') as f:
            updated_content = f.read()
            if f"ssid={new_ssid}" not in updated_content or f"wpa_passphrase={new_password}" not in updated_content:
                print("Error: Changes were not successfully written to hostapd.conf.")
                return False

        # Restart hostapd to apply the changes
        subprocess.run(['sudo', 'systemctl', 'restart', 'hostapd'], check=True)
        print(f"Successfully updated {HOSTAPD_CONF} with SSID '{new_ssid}' and restarted hostapd.")
        return True

    except FileNotFoundError:
        print(f"Error: {HOSTAPD_CONF} not found.")
    except PermissionError:
        print(f"Error: Permission denied when writing to {HOSTAPD_CONF}.")
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    return False


if __name__ == '__main__':
    # Simple tests for the module functions
    print("Random MAC:", random_mac())
    current_mac = get_current_mac()
    print("Current MAC (wlan0):", current_mac)
    print("Current SSID:", get_current_ssid())
    print("Available Networks:", get_available_networks())
    ap_status, ap_ssid = get_ap_status()
    print("AP Status:", ap_status, "SSID:", ap_ssid)
