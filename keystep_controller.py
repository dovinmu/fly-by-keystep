import json
import os
from pathlib import Path
import requests
import rtmidi
import signal
import subprocess
import sys
import threading
import time

from airplane import create_airplane
from utils import play_sound, freq_to_tuple, tuple_to_str, request_current_data

class KeystepController:
    def __init__(self, airplane_type=None):
        self.plane = create_airplane(airplane_type)
        # self.plane = Airbus320()
        # self.plane = MysterySpaceship()
        self.midi_in = rtmidi.MidiIn()
        self.knob_values = {0: 0, 1: 0, 2: 0, 3: 64}
        self.knobs_moved = {0: False, 1: False, 2: False, 3: False}
        self.knob_changes = [0,0,0,0]
        self.keys_being_pressed = set()
        self.last_key_touched = None
        self.current_displayed_sound = None
        self.setup_midi()

        self.rudder_position = 0
        self.pfd_setting = "ARC"  # 0: PLAN, 1: ARC, 2: ROSE VOR, 3: LS
        self.pfd_range = 10
        self.xpndr = "1200"
        self.baro_measurement = 0
        self.speed = 100

        self.current_mode = "XPNDR"
        print("fetching state from server")
        self.midi_lock = threading.Lock()
        self.last_printed_lines = 0
        self.message = ""

        self.fetch_state()

    def fetch_state(self):
        try:
            with self.midi_lock:
                response = request_current_data()
                if response.status_code == 200:
                    data = response.json()
                    print(json.dumps(data, indent=2))
                    self.plane.radio[1]["active"] = freq_to_tuple(data['COM1_ACTIVE'])
                    self.plane.radio[1]["standby"] = freq_to_tuple(data['COM1_STANDBY'])
                    self.plane.radio[2]["active"] = freq_to_tuple(data['COM2_ACTIVE'])
                    self.plane.radio[2]["standby"] = freq_to_tuple(data['COM2_STANDBY'])
                    self.plane.ap = self.load_plane_data(data)
                    self.message = "✅"
                else:
                    print(f"Failed to fetch initial state. Status code: {response.status_code}")
                    self.message = "error from server"
                print("\n"*10)
        except requests.RequestException as e:
            print(f"Error fetching initial state: {e}")
            self.message = "error fetching data"
            # Default values are already set in __init__

    @staticmethod
    def load_plane_data(data):
        try: # FBW A320nx
            return {
                "heading": data['FBW_A32NX_AP_HDG_INDICATOR'] if '-' not in data['FBW_A32NX_AP_HDG_INDICATOR'] else 150,
                "speed": data['FBW_A32NX_AP_SPD_INDICATOR'] if '-' not in data['FBW_A32NX_AP_SPD_INDICATOR'] else 100,
                "vs": data['FBW_A32NX_AP_VS_INDICATOR'],
                "alt": int(data['FBW_A32NX_AP_ALT_INDICATOR']/100)
            }
        except:
            return {
                "heading": 0,
                "speed": 100,
                "vs": 0,
                "alt": 100
            }
    
    @staticmethod
    def map_integer_knob(value):
        step = 128 // 19
        for i in range(19):
            if value <= (i + 1) * step:
                return 118 + i
        return 136  # For any remaining values
    
    @staticmethod
    def map_fractional_knob(value):
        # 0/1/2 => 0, 3/4/5 => 25, ..., 120/... => 975
        step = 128 // 40
        for i in range(40):
            if value <= (i + 1) * step:
                return i * 25
        return 975

    @staticmethod
    def map_rudder_knob(value):
        return - int((value/127) * 32767 - 16383)
    
    @staticmethod
    def map_pfd_range(value):
        # Map 0-127 to typical PFD ranges (e.g., 10, 20, 40, 80, 160, 320 NM)
        ranges = [10, 20, 40, 80, 160, 320]
        index = int((value / 127) * (len(ranges) - 1))
        return ranges[index]
    
    @staticmethod
    def map_pfd_setting(value):
        pfd_settings = ["LS", "VOR", "NAV", "ARC", "PLAN"]
        return pfd_settings[int((value / 127) * len(pfd_settings) - 1)]
    
    @staticmethod
    def map_xpndr_knob(value):
        return int((value / 127) * 99)
    
    @staticmethod
    def map_speed_knob(value):
        # each tick should be exactly 2 knots
        return int((value / 127) * 256) + 143
    
    @staticmethod
    def map_fl_knob(value):
        # Flight levels from 0 to 410 (41,000 ft) in 1000 ft increments
        max_fl = 41
        fl = int((value / 127) * max_fl) * 10
        return fl

    @staticmethod
    def map_vs_knob(value):
        # Vertical speed from -6000 to +6000 in 100 ft increments
        vs_range = 80  # Total number of 100 ft increments (-60 to +60)
        vs = int((value / 127) * vs_range - 40) * 100
        return max(-4000, min(4000, vs))  # Ensure we don't exceed the limits
    
    @staticmethod
    def map_heading_knob(value):
        # There are 72 possible headings (360 / 5)
        num_headings = 72
        # Map the 0-127 range to 0-71
        index = int((value / 127) * (num_headings - 1))
        # Calculate the heading
        heading = (index * 5) % 360
        return heading

    def update_knobs(self):
        if not any(self.knobs_moved.values()):
            return
        with self.midi_lock:
            # knobs 1 and 2: comms
            if 71 in self.keys_being_pressed:
                self.message = "prevented knob update"
                return
            if self.knobs_moved[0]:
                new_integer = self.map_integer_knob(self.knob_values[0])
                new_fractional = self.plane.radio[self.plane.active_radio]["active"][1]

                if 57 in self.keys_being_pressed:
                    sound_files = self.plane.get_announcements_list()
                    if len(sound_files) == 0:
                        self.current_displayed_sound = ""
                    else:
                        if len(sound_files) == 1:
                            idx = 0
                        else:
                            idx = new_integer % (len(sound_files))
                        self.current_displayed_sound = sound_files[idx]
                else:
                    if new_integer != self.plane.radio[self.plane.active_radio]["active"][0]:     
                        play_sound(volume=0.1)
                        self.adjust_radio_direct(new_integer, new_fractional)
            if self.knobs_moved[1]:
                new_integer = self.plane.radio[self.plane.active_radio]["active"][0]
                new_fractional = self.map_fractional_knob(self.knob_values[1])
                if new_fractional != self.plane.radio[self.plane.active_radio]["active"][1]:
                    play_sound(volume=0.1)
                    self.adjust_radio_direct(new_integer, new_fractional)
            
            # knob 3: SPD, ALT, various
            if self.knobs_moved[2]:
                if self.current_mode == "FLIGHT_PLAN":
                    # TODO: this is temp and should be abstracted to plane class when I refactor this function
                    if self.plane.plane_type == "A320":
                        new_pfd_setting = self.map_pfd_setting(self.knob_values[2])
                        if self.plane.send_request("MobiFlight.A320_Neo_MFD_NAV_MODE_1_{new_pfd_setting}"):
                            play_sound(volume=0.1)
                        self.message = f"setting: '{new_pfd_setting}'"
                    elif self.plane.plane_type == "C172":
                        self.plane.handle_lower_fms_knob_moved(self.knob_changes[2], self.knob_values[2])
                if self.current_mode == "XPNDR":
                    # print(self.knob_values[2])
                    scaled_value = self.map_xpndr_knob(self.knob_values[2])
                    new_value = f"{scaled_value:02d}{self.xpndr[2:]}"
                    play_sound(volume=0.1)
                    self.set_xpndr(new_value)
                if self.current_mode == "CRUISE":
                    new_spd = self.map_speed_knob(self.knob_values[2])
                    self.plane.set_speed(new_spd)
                if self.current_mode == "FL":
                    new_fl = self.map_fl_knob(self.knob_values[2])
                    self.plane.adjust_fl(new_fl)

            # knob 4: rudder, HDG, VS, various
            if self.knobs_moved[3]:
                if self.current_mode == "FLIGHT_PLAN":
                    if self.plane.plane_type == "A320":
                        new_pfd_range = self.map_pfd_range(self.knob_values[3])
                        if self.plane.send_request("MobiFlight.A320_neo_MFD_Range_1_{new_pfd_range}"):
                            play_sound(volume=0.1)
                        self.message = f"range: '{new_pfd_range}'"
                    elif self.plane.plane_type == "C172":
                        self.plane.handle_upper_fms_knob_moved(self.knob_changes[3], self.knob_values[3])
                if self.current_mode == "XPNDR":
                    # print(self.knob_values[3])
                    scaled_value = self.map_xpndr_knob(self.knob_values[3])
                    new_value = f"{self.xpndr[:2]}{scaled_value:02d}"
                    play_sound(volume=0.1)
                    self.set_xpndr(new_value)
                if self.current_mode == "TAXI":
                    new_rudder = self.map_rudder_knob(self.knob_values[3])
                    if new_rudder != self.rudder_position:
                        self.adjust_rudder(new_rudder)
                        # print(new_rudder, self.rudder_position)
                if self.current_mode == "CRUISE":
                    play_sound(volume=0.1)
                    new_hdg = self.map_heading_knob(self.knob_values[3])
                    self.plane.set_heading(new_hdg)
                if self.current_mode == "FL":
                    play_sound(volume=0.1)
                    new_vs = self.map_vs_knob(self.knob_values[3])
                    self.plane.adjust_vs(new_vs)
            self.knobs_moved = {0: False, 1: False, 2: False, 3: False}
            self.knob_changes = [0,0,0,0]

    def adjust_radio_direct(self, new_integer, new_fractional):
        # endpoint = f"{'COM2_' if self.active_com == 2 else 'COM_'}RADIO_SET"
        if self.plane.active_radio == 1:
            endpoint = 'COM_RADIO_SET'
        elif self.plane.active_radio == 2:
            endpoint = 'COM2_RADIO_SET'
        elif self.plane.active_radio == 3:
            endpoint = 'NAV1_RADIO_SET'
        elif self.plane.active_radio == 4:
            endpoint = 'NAV2_RADIO_SET'
        else:
            self.message = f"active_com set to invalid value {self.plane.active_radio}"
        if self.plane.send_request(endpoint, {"value_to_use": f"{new_integer}.{new_fractional:03d}"}):
            self.message = "📻"
        else:
            self.message = "📻🙁"
        self.plane.radio[self.plane.active_radio]['active'] = (new_integer, new_fractional)

    def adjust_rudder(self, new_rudder_val):
        if new_rudder_val < -16383 or new_rudder_val > 16384:
            print("cannot set rudder val to", new_rudder_val)
            return
        if self.plane.send_request("RUDDER_SET", {"value_to_use": self.rudder_position}):
            self.rudder_position = new_rudder_val
            # print(f"rudder: {self.rudder_position}")
        else:
            print("failed to set rudder")
        
    def adjust_qnh(self, change):
        endpoint = "KOHLSMAN_INC" if change > 0 else "KOHLSMAN_DEC"
        if self.plane.send_request(endpoint):
            # print(f"Adjusted QNH by {change:.2f}")
            play_sound()
        else:
            print("failed to update QNH")

    def set_xpndr(self, new_value):
        self.plane.send_request("XPNDR_SET", {"value_to_use": new_value})
        # print('set to', new_value)
        self.xpndr = new_value

    def set_active_radio(self, radio_number):
        # either Beyond ATC or SIMCONNECT doesn't respond to this endpoint
        # endpoint = "COM2_TRANSMIT_SELECT" if self.active_com == 2 else "COM1_TRANSMIT_SELECT"
        if self.plane.active_radio != radio_number:
            play_sound("toggle")
        self.plane.active_radio = radio_number
        # self.plane.send_request(endpoint, {"value_to_use": 0})

    def swap_active_standby(self):
        com = self.plane.active_radio
        endpoint = "COM_STBY_RADIO_SWAP" if com == 1 else "COM2_RADIO_SWAP"
        self.plane.send_request(endpoint)
        
        # Swap the frequencies in our local data structure
        self.plane.radio[com]["active"], self.plane.radio[com]["standby"] = self.plane.radio[com]["standby"], self.plane.radio[com]["active"]
        self.adjust_radio_direct(*self.plane.radio[com]["active"])

    def set_speed_mode(self, mode):
        if mode == "selected":
            self.plane.send_request("MobiFlight.FBW_A32NX_DEV_FCU_SPD_PULL")
        if mode == "managed":
            self.plane.send_request("MobiFlight.FBW_A32NX_DEV_FCU_SPD_PUSH")
        self.message = f"SPD: {mode}"

    def set_altitude_mode(self, mode):
        if mode == "selected":
            self.plane.send_request("MobiFlight.FBW_A32NX_DEV_FCU_ALT_PULL")
        if mode == "managed":
            self.plane.send_request("MobiFlight.FBW_A32NX_DEV_FCU_ALT_PUSH")
        self.message = f"ALT: {mode}"

    def set_heading_mode(self, mode):
        if mode == "selected":
            self.plane.send_request("MobiFlight.FBW_A32NX_DEV_FCU_HDG_PULL")
        if mode == "managed":
            self.plane.send_request("MobiFlight.FBW_A32NX_DEV_FCU_HDG_PUSH")
        self.message = f"ALT: {mode}"

    def set_vs_mode(self, mode):
        if mode == "selected":
            self.plane.send_request("MobiFlight.FBW_A32NX_DEV_FCU_VS_PULL")
        if mode == "managed":
            self.plane.send_request("MobiFlight.FBW_A32NX_DEV_FCU_VS_PUSH")
        self.message = f"VS: {mode}"

    def setup_midi(self):
        available_ports = self.midi_in.get_ports()
        if available_ports:
            self.midi_in.open_port(0)
            print(f"Listening on {available_ports[0]}")
            self.midi_in.set_callback(self.midi_callback)
        else:
            print("No MIDI ports available")
            # exit()

    def handle_knob(self, number, value):
        self.knobs_moved[number] = True

    def handle_key_press(self, note, velocity):
        if velocity > 0:  # Key press, not release
            self.last_key_touched = note

            if self.plane.handle_key_press(note, velocity):
                return

            # Radio: comms, nav, etc
            if note == 48:  # C (lowest key on default octave setting)
                self.swap_active_standby()
                play_sound("press")
            elif note == 50:  # D
                self.set_active_radio(1) # plays sound if changed
            elif note == 52:  # E
                self.set_active_radio(2) # plays sound if changed
            elif note == 53: # F
                self.set_active_radio(3)
            elif note == 55: # G
                self.set_active_radio(4)
            elif note == 57:
                play_sound("press")
                self.keys_being_pressed.add(57)
            elif note == 59:
                play_sound(fname="beep.mp3")
            elif note == 60:
                play_sound("press")
                self.plane.send_request("MobiFlight.A320_Neo_MFD_NAV_MODE_1_PLAN")
            elif note == 66:
                if self.current_mode == "FL":
                    play_sound("press")
                    self.plane.vs_button()
            elif note == 68: # overflow selector details
                if self.current_mode == "CRUISE":       
                    play_sound()
                    self.plane.send_request("AP_PANEL_HEADING_HOLD")
                if self.current_mode == "FL":
                    self.plane.send_request("AP_PANEL_ALTITUDE_HOLD")
            elif note == 70: # overflow selector details
                if self.current_mode == "CRUISE":       
                    play_sound()
                    self.plane.send_request("AP_NAV1_HOLD")
                if self.current_mode == "FLIGHT_PLAN":
                    self.plane.send_request("MobiFlight.AS1000_MFD_ENT_Push") # C172-specific
            elif note == 71:
                play_sound()
                self.keys_being_pressed.add(note)
            elif note == 72:
                if self.set_knobs_mode("FLIGHT_PLAN"):
                    play_sound("toggle")
            elif note == 73: # behavior depends on mode
                # pull if tapped, push if pressed
                if self.current_mode == "CRUISE":
                    self.set_speed_mode("selected")
                if self.current_mode == "FL":
                    self.set_altitude_mode("selected")
            elif note == 74:
                if self.set_knobs_mode("XPNDR"):
                    play_sound("toggle")
            elif note == 75: # behavior depends on mode
                if self.current_mode == "FLIGHT_PLAN":
                    self.plane.send_request("MobiFlight.AS1000_MFD_FMS_Upper_PUSH") # C172-specific
                # pull if tapped, push if pressed. pushed logic in handle_aftertouch()
                if self.current_mode == "CRUISE":
                    self.set_heading_mode("selected")
                if self.current_mode == "FL":
                    self.set_vs_mode("selected")
            elif note == 76:
                if self.set_knobs_mode("TAXI"):
                    play_sound("toggle")
            elif note == 77:
                if self.set_knobs_mode("CRUISE"):
                    play_sound("toggle")
            elif note == 78: # engage / disengage system. behavior depends on mode
                if self.current_mode == "FLIGHT_PLAN":
                    self.plane.send_request("MobiFlight.AS1000_MFD_CLR") # C172-specific
                    play_sound()
                if self.current_mode == "CRUISE":
                    self.plane.send_request("AUTOPILOT_ON")
                    play_sound()
                if self.current_mode == "FL":
                    play_sound()
                    self.plane.send_request("AP_PANEL_VS_HOLD")
            elif note == 79:
                if self.set_knobs_mode("FL"):
                    play_sound("toggle")
            elif note == 80: # -. behavior depends on mode
                if self.current_mode == "FLIGHT_PLAN":
                    play_sound()
                    self.plane.send_request("MobiFlight.AS1000_MFD_RANGE_INC")     
                if self.current_mode == "FL":
                    play_sound()
                    self.plane.send_request("AP_VS_VAR_DEC")
                if self.current_mode == "CRUISE":
                    self.plane.set_heading(-1)
            elif note == 82: # +. behavior depends on mode
                if self.current_mode == "FLIGHT_PLAN":
                    play_sound()
                    self.plane.send_request("MobiFlight.AS1000_MFD_RANGE_DEC") # yes, DEC zooms in 
                if self.current_mode == "FL":
                    play_sound()
                    self.plane.send_request("AP_VS_VAR_INC")
                if self.current_mode == "CRUISE":
                    self.plane.set_heading(1)
            elif note == 83:
                self.adjust_qnh(-1)
            elif note == 84:
                self.adjust_qnh(1)
            else:
                self.message = "unknown key: " + str(note)

    def handle_aftertouch(self, velocity):
        if velocity > 0:
            if self.last_key_touched == 57:
                play_sound(fname=self.current_displayed_sound)
            if self.last_key_touched == 72:
                self.plane.send_request("MobiFlight.AS1000_MFD_FPL_Push")
            if self.last_key_touched == 73:
                if self.current_mode == "CRUISE":
                    play_sound("click_mouse")
                    self.set_speed_mode("managed")
                if self.current_mode == "FL":
                    play_sound("click_mouse")
                    self.set_altitude_mode("managed")
            elif self.last_key_touched == 75:
                if self.current_mode == "CRUISE":
                    play_sound("click_mouse")
                    self.set_heading_mode("managed")
                if self.current_mode == "FL":
                    play_sound("click_mouse")
                    self.set_vs_mode("managed")
            elif self.last_key_touched == 78:
                if self.current_mode == "FLIGHT_PLAN":
                    play_sound("click_mouse")
                    self.plane.send_request("MobiFlight.AS1000_MFD_CLR_Long") # C172-specific
                if self.current_mode == "CRUISE":
                    play_sound("click_mouse")
                    self.plane.send_request("AUTOPILOT_OFF")
            self.last_key_touched = None

    def handle_key_release(self, key):
        self.keys_being_pressed.remove(key)
        if key == 57:
            self.current_displayed_sound = None
        if key == 71:
            play_sound()
    
    def set_knobs_mode(self, mode):
        if mode not in ("TAXI", "FLIGHT_PLAN", "XPNDR", "CRUISE", "FL"):
            # print(mode, "mode not supported")
            return False
        if self.current_mode == mode:
            return False
        self.current_mode = mode
        return True

    def midi_callback(self, message, time_stamp):
        with self.midi_lock:
            message, delta_time = message
            if message[0] & 0xF0 == 0xB0:  # CC message
                cc_number, cc_value = message[1], message[2]
                if cc_number in self.knob_values:
                    updated = cc_value - self.knob_values[cc_number]
                    self.knob_values[cc_number] = cc_value
                    self.knob_changes[cc_number] = updated
                    self.handle_knob(cc_number, cc_value)
            elif message[0] & 0xF0 == 0x90:  # Note On
                self.handle_key_press(message[1], message[2])
            elif message[0] == 208:  # Aftertouch
                self.handle_aftertouch(message[1])
            elif message[0] == 128: # end note
                self.handle_key_release(message[1])

    def print_state(self):
        RED = '\033[91m'
        YELLOW = '\033[33m'
        GREEN = '\033[92m'
        MAGENTA = '\033[35m'
        CYAN = '\033[36m'
        RESET = '\033[0m'

        # # Move cursor up by the number of lines we printed last time
        # if self.last_printed_lines > 0:
        #     sys.stdout.write(f"\033[{self.last_printed_lines}A")
        
        # Prepare the lines to print
        lines = [
            '\n',
            '-'*30,
            f"Mode: {CYAN}{self.current_mode}{RESET}",
            f"{GREEN if self.plane.active_radio == 1 else ''}COM1{RESET}: {MAGENTA}{tuple_to_str(self.plane.radio[1]['active'])}{RESET} <=> {tuple_to_str(self.plane.radio[1]['standby'])}",
            f"{GREEN if self.plane.active_radio == 2 else ''}COM2{RESET}: {YELLOW}{tuple_to_str(self.plane.radio[2]['active'])}{RESET} <=> {tuple_to_str(self.plane.radio[2]['standby'])}",
            # f"{GREEN if self.plane.active_radio == 3 else ''}NAV1{RESET}: {YELLOW}{tuple_to_str(self.plane.radio[3]['active'])}{RESET} <=> {tuple_to_str(self.plane.radio[3]['standby'])}",
            # f"{GREEN if self.plane.active_radio == 4 else ''}NAV2{RESET}: {YELLOW}{tuple_to_str(self.plane.radio[4]['active'])}{RESET} <=> {tuple_to_str(self.plane.radio[4]['standby'])}",
            # f"PFD Range: {MAGENTA}{self.pfd_range}{RESET} NM, Setting: {MAGENTA}{self.pfd_settings[self.pfd_setting]}{RESET}"
        ]

        if self.current_mode == "TAXI":
            lines += [f"Rudder: {YELLOW}{self.rudder_position}{RESET}"]
        if self.current_mode == "XPNDR":
            lines += [f"XPNDR: {self.xpndr}",]
        if 57 in self.keys_being_pressed:
            if not self.current_displayed_sound:
                lines += [f"🔊 (scroll 1st knob)"]
            else:
                lines += [f"🔊 {self.current_displayed_sound}", "(press to select)"]
        lines += [f"message: {self.message} | {self.plane.message}"]

        # Move cursor up by the number of lines we will be printing
        if len(lines) > 0:
            sys.stdout.write(f"\033[{len(lines)}A")

        # Print each line and clear to the end of line
        for line in lines:
            print(f"{line}\033[K")
        
        # Remember how many lines we printed
        self.last_printed_lines = len(lines)

        # Flush the output
        sys.stdout.flush()
    
    def run(self):
        heartbeat_interval = 0.025
        update_interval = 3 # Fetch state every n seconds
        counter = 0
        try:
            while True:
                time.sleep(heartbeat_interval)
                counter += 1
                self.update_knobs()
                self.plane.heartbeat()
                self.print_state()
                if counter >= update_interval * (1/heartbeat_interval):  # 10 * 0.1s = 1s
                    # self.fetch_state() # creates annoying sync issues, skip for now
                    counter = 0
                    self.message = f"{time.time()}"
                    self.plane.message = ""
        except KeyboardInterrupt:
            print("\nExiting...")
        finally:
            self.midi_in.close_port()
            del self.midi_in


if __name__ == "__main__":
    import sys
    import argparse
    parser = argparse.ArgumentParser(description="Run KeystepController for a specific airplane type.")
    parser.add_argument('airplane_type', type=str, help="Type of airplane (e.g., 'A320', 'B737')")
    args = parser.parse_args()

    controller = KeystepController(args.airplane_type)
    print("\n\n\n")
    if args.airplane_type == 'X':
        # controller.handle_key_press(78, 1)
        # time.sleep(5)
        # controller.handle_key_press(80, 1)
        # time.sleep(0.5)
        # controller.handle_key_press(80, 1)
        pass

    controller.run()

    # time.sleep(1)
    # print('testing int inc')
    # time.sleep(1)
    # controller.self.plane.send_request('COM_RADIO_WHOLE_INC')