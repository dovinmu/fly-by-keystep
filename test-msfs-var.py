import requests

server_url = "http://10.0.0.15:4000"
    
def test_light_potentiometer():
    # Try to read the current value
    read_endpoint = "LIGHT_POTENTIOMETER_88"
    read_response = send_request(read_endpoint, method="GET")
    
    if read_response:
        current_value = read_response.get('value', None)
        print(f"Current PFD Brightness (Captain): {current_value}")
        
        # Try to set a new value (50% brightness)
        write_endpoint = "LIGHT_POTENTIOMETER_88_SET"
        new_value = 50
        write_response = send_request(write_endpoint, {"value_to_use": new_value})
        
        if write_response:
            print(f"Set PFD Brightness to {new_value}")
            
            # Read again to confirm change
            read_response = send_request(read_endpoint, method="GET")
            if read_response:
                updated_value = read_response.get('value', None)
                print(f"Updated PFD Brightness (Captain): {updated_value}")
        else:
            print("Failed to set PFD Brightness")
    else:
        print("Failed to read PFD Brightness")

# Modify send_request method to handle GET requests
def send_request(endpoint, body=None, method="POST"):
    url = f"{server_url}/event/{endpoint}/trigger"
    try:
        if method == "GET":
            response = requests.get(url, timeout=3)
        elif body:
            response = requests.post(url, json=body, timeout=3)
        else:
            response = requests.post(url, timeout=3)
        
        if response.status_code == 200:
            print(f"Successfully sent {method} request to {endpoint}")
            return response.json()
        else:
            print(f"Failed to send {method} request to {endpoint}. Status code: {response.status_code}")
            print(response.json())
    except requests.Timeout:
        print(f"Request to {endpoint} timed out after 3 seconds.")
    except requests.RequestException as e:
        print(f"Error sending request to {endpoint}: {e}")
    return None

test_light_potentiometer()