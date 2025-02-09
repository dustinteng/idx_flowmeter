#!/usr/bin/env python3
import os
import json
import pigpio  # GPIO control
import time
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from network import random_mac, get_current_mac, get_current_ssid, get_available_networks, get_ap_status, update_hostapd_config

# Initialize Flask app
app = Flask(__name__)
app.secret_key = '3333'  # Change to a secure secret key in production

# Set a password for WiFi authentication
WIFI_PASSWORD = "3333"

# Define a configuration file to store flowmeter settings
FLOWMETER_CONFIG_FILE = "flowmeter_config.json"

# GPIO Pin for Flowmeter Sensor (change based on your wiring)
FLOWMETER_GPIO = 17  # Example GPIO pin

# Flowmeter pulse count and conversion factor
PULSE_COUNT = 0
PULSE_TO_LITER = 0.0025  # Adjust based on flowmeter specs

# Initialize pigpio
pi = pigpio.pi()
if not pi.connected:
    print("Error: Cannot connect to pigpio. Is pigpiod running?")
    exit(1)

def flowmeter_callback(gpio, level, tick):
    """Callback function for counting flowmeter pulses."""
    global PULSE_COUNT
    if level == 1:  # Count only rising edge pulses
        PULSE_COUNT += 1

# Attach callback to the GPIO pin
pi.set_mode(FLOWMETER_GPIO, pigpio.INPUT)
pi.set_pull_up_down(FLOWMETER_GPIO, pigpio.PUD_DOWN)
pi.callback(FLOWMETER_GPIO, pigpio.RISING_EDGE, flowmeter_callback)

def get_liters_flowed():
    """Convert pulses to liters flowed."""
    return round(PULSE_COUNT * PULSE_TO_LITER, 3)

def reset_flowmeter():
    """Reset the pulse count."""
    global PULSE_COUNT
    PULSE_COUNT = 0

def load_flowmeter_config():
    """Load the flowmeter configuration from file."""
    default_config = {"density": "", "magnet_offset": ""}
    if os.path.exists(FLOWMETER_CONFIG_FILE):
        try:
            with open(FLOWMETER_CONFIG_FILE, "r") as f:
                config = json.load(f)
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                return config
        except Exception as e:
            print("Error loading flowmeter config:", e)
    return default_config

def save_flowmeter_config(config):
    """Save the flowmeter configuration to file."""
    try:
        with open(FLOWMETER_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print("Error saving flowmeter config:", e)

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main dashboard page."""
    config = load_flowmeter_config()

    if request.method == 'POST':
        # If reset button is pressed, reset the flowmeter counter
        if 'reset_flow' in request.form:
            reset_flowmeter()
        else:
            # Otherwise update the flowmeter settings (density & magnet_offset)
            density = request.form.get('density', '')
            magnet_offset = request.form.get('magnet_offset', '')
            config['density'] = density
            config['magnet_offset'] = magnet_offset
            save_flowmeter_config(config)
        return redirect(url_for('index'))

    current_mac = get_current_mac()
    current_ssid = get_current_ssid()
    available_networks = get_available_networks()
    ap_status, ap_ssid = get_ap_status()
    
    return render_template("index.html", config=config,
                           current_mac=current_mac, current_ssid=current_ssid,
                           available_networks=available_networks,
                           ap_status=ap_status, ap_ssid=ap_ssid,
                           liters=get_liters_flowed())

@app.route('/wifi-auth', methods=['GET', 'POST'])
def wifi_auth():
    """Password authentication page for accessing WiFi settings."""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == WIFI_PASSWORD:
            session['wifi_authenticated'] = True
            return redirect(url_for('wifi_settings'))
        else:
            error = "Incorrect password. Try again."
            return render_template("wifi_auth.html", error=error)
    return render_template("wifi_auth.html", error=None)

@app.route('/wifi-settings', methods=['GET', 'POST'])
def wifi_settings():
    """WiFi Settings Page (requires authentication)."""
    if 'wifi_authenticated' not in session or not session['wifi_authenticated']:
        return redirect(url_for('wifi_auth'))
    
    if request.method == 'POST':
        new_ssid = request.form.get('ap_ssid', '').strip()
        new_password = request.form.get('ap_password', '').strip()
        if new_ssid and new_password:
            success = update_hostapd_config(new_ssid, new_password)
            print("WiFi updated." if success else "WiFi update failed.")
        else:
            print("SSID and password cannot be empty.")
        return redirect(url_for('wifi_settings'))

    return render_template("wifi_settings.html",
                           current_mac=get_current_mac(),
                           current_ssid=get_current_ssid(),
                           available_networks=get_available_networks(),
                           ap_status=get_ap_status()[0],
                           ap_ssid=get_ap_status()[1])

@app.route('/update_ap', methods=['POST'])
def update_ap():
    """Update WiFi settings (alternative endpoint)."""
    new_ssid = request.form.get('ap_ssid', '').strip()
    new_password = request.form.get('ap_password', '').strip()
    if new_ssid and new_password:
        success = update_hostapd_config(new_ssid, new_password)
        print("AP settings updated successfully." if success else "Failed to update AP settings.")
    else:
        print("SSID and password cannot be empty.")
    return redirect(url_for('index'))

@app.route('/network_info', methods=['GET'])
def network_info():
    """Return network info as JSON."""
    return jsonify({
        "current_mac": get_current_mac(),
        "current_ssid": get_current_ssid(),
        "available_networks": get_available_networks(),
        "ap_status": get_ap_status()[0],
        "ap_ssid": get_ap_status()[1]
    })

@app.route('/get_liters', methods=['GET'])
def get_liters():
    """Return current liters flowed as JSON."""
    return jsonify({"liters": get_liters_flowed()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3333)
