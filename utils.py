import os
from pathlib import Path
import requests
import subprocess

script_dir = Path(os.path.dirname(os.path.abspath(__file__)))

MCA_SERVER = "http://10.0.0.15:4000"
def _send_request(endpoint, body=None):
    url = f"{MCA_SERVER}/event/{endpoint}/trigger"
    try:
        if body:
            response = requests.post(url, json=body)
        else:
            response = requests.post(url)
        
        if response.status_code == 200:
            # print(f" - {endpoint}")
            return True
        else:
            print(f"Failed to send request to {endpoint}. Status code: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"Error sending request to {endpoint}: {e}")
        return False

def request_current_data():
    # not try/excepting because downstream methods should handle that (or let program error)
    response = requests.get(f"{MCA_SERVER}/ui", timeout=3)
    return response

def write_to_log(str):
    with open('_err.log', 'w') as f:
        f.write(str)
    os.rename('_err.log', 'err.log')

def play_sound(sound_iface_name="default", volume=1.0, fname=None):
    sounds_lookup = {
        "default": "click_swip",
        "toggle": "click_swap",
        "press": "click_mouse"
    }
    if not fname:
        fname = sounds_lookup[sound_iface_name] if sound_iface_name in sounds_lookup else sounds_lookup["default"]
        if '.' not in fname:
            fname += ".wav"
    sound_path = os.path.join(script_dir, 'sfx', f"{fname}")
    subprocess.Popen(["afplay", "-v", str(volume), sound_path])

def freq_to_tuple(freq):
    integer_part = int(float(freq))
    fractional_part = int(round((float(freq) - integer_part) * 1000))
    return (integer_part, fractional_part)

def tuple_to_str(freq_tuple):
    return f"{freq_tuple[0]}.{freq_tuple[1]:03d}"