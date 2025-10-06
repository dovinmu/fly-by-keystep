import os
import subprocess
import time
from utils import _send_request, play_sound, tuple_to_str, script_dir
from looping_mp3 import LoopingMP3Player

def create_airplane(airplane_type):
    if airplane_type.upper() in set(("C172", "CESSNA", "C4J")):
        return CessnaG1000()
    elif airplane_type.upper() == "A320":
        return Airbus320()
    elif airplane_type.upper() == "X":
        return MysterySpaceship()
    else:
        return Airplane()

class Airplane:
    def __init__(self):
        self.plane_type = "GENERIC"
        self.active_radio = 1  # 1 or 2 refers to which COM the knobs will change, 3 or 4 which NAV
        self.transmit_com = 1 # TODO
        self.radio = {
            1: { "active": (118,0), "standby": (118,0) },
            2: { "active": (118,0), "standby": (118,0) },
            3: { "active": (118,0), "standby": (118,0) },
            4: { "active": (118,0), "standby": (118,0) }
        }
        self.current_say_process = None
        self.ap = {
            "heading": 180,
            "speed": 100,
            "alt": 1,
            "vs": 0
        }
        self.message = ''
    
    def update_knobs(self, knobs_moved, knob_values, keys_being_pressed):
        pass

    def handle_key_press(self, note, velocity):
        # probably shouldn't do anything more
        self.message = note
        return False
    
    def say(self, text):
        # Terminate the previous say command if it's still running
        if self.current_say_process and self.current_say_process.poll() is None:
            self.current_say_process.terminate()
            try:
                self.current_say_process.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                self.current_say_process.kill()

        voice = "Moira (Enhanced)"
        self.current_say_process = subprocess.Popen(["say", "-v", str(voice), str(text), '-r', str(180)])
    
    def send_request(self, endpoint, body=None):
        return _send_request(endpoint, body)

    def get_announcements_list(self):
        return [fname for fname in os.listdir(script_dir/'sfx') if '.mp3' in fname]

    def heartbeat(self):
        pass    
    def adjust_fl(self, new_fl):
        pass
    def set_heading(self, new_heading):
        pass
    def set_speed(self, new_spd):
        pass
    def adjust_vs(self, new_vs):
        pass
    def vs_button(self):
        self.message = "VS button INOP"

class CessnaG1000(Airplane):
    def __init__(self):
        super().__init__()
        self.plane_type = "C172"
        self.message = "Cessna with Garmin 1000 initialized"
    
    def adjust_fl(self, new_fl):
        amount = int((new_fl - self.ap['alt']) / 10)
        if amount > 0:
            endpoint = "AP_ALT_VAR_INC"
            delta = 10
        else: 
            endpoint = "AP_ALT_VAR_DEC"
            delta = -10
        for _ in range(min(abs(amount), 10)):
            self.send_request(endpoint)
            self.ap['alt'] += delta
        self.message = f"ALT: {self.ap['alt']} amt {amount} new {new_fl}"

    def set_heading(self, new_heading):
        self.message = f"setting {new_heading}"
        if self.send_request("HEADING_BUG_SET", {"value_to_use": new_heading}):
            self.message = f"set {new_heading}"

    def adjust_heading(self, heading_change):
        self.message = f"INOP: adjusting heading by {heading_change}"

    def set_speed(self, new_spd):
        self.message = "speed not implemented on C172"
        return
    
    def adjust_vs(self, new_vs):
        amount = int((new_vs - self.ap['vs']) / 100)
        if amount > 0:
            endpoint = "AP_VS_VAR_INC"
            delta = 100
        else:
            endpoint = "AP_VS_VAR_DEC"
            delta = -100
        for _ in range(min(abs(amount), 10)):
            self.send_request(endpoint)
            self.ap['vs'] += delta
        self.message = f"VS: {self.ap['vs']} amt {amount} new {new_vs}"

    def vs_button(self):
        # self.message = "VS button INOP"
        self.send_request("AP_VS_HOLD")

    def handle_lower_fms_knob_moved(self, knob_change, knob_value):
        if knob_value % 5 == 0:
            if knob_change > 0:
                self.send_request("MobiFlight.AS1000_MFD_FMS_Lower_INC")
                self.message = f"FMS+ {knob_change} {knob_value // 2}"
            elif knob_change < 0:
                self.send_request("MobiFlight.AS1000_MFD_FMS_Lower_DEC")
                self.message = f"FMS- {knob_change} {knob_value // 2}"

    def handle_upper_fms_knob_moved(self, knob_change, knob_value):
        if knob_value % 2:
            if knob_change > 0:
                self.send_request("MobiFlight.AS1000_MFD_FMS_Upper_INC")
            elif knob_change < 0:
                self.send_request("MobiFlight.AS1000_MFD_FMS_Upper_DEC")

class Airbus320(Airplane):
    def __init__(self):
        super().__init__()
        self.plane_type = "A320"
        self.message = "Airbus320 initialized"

    def set_heading(self, new_hdg):
        try:
            amount = int(new_hdg - self.ap['heading'])
        except:
            amount = int(new_hdg)
        if amount > 0:
            endpoint = "MobiFlight.FBW_A32NX_DEV_FCU_HDG_TRK_INC"
            delta = 1
        else: 
            endpoint = "MobiFlight.FBW_A32NX_DEV_FCU_HDG_TRK_DEC"
            delta = -1
        for _ in range(min(2, abs(amount))):
            self.plane.send_request(endpoint)
            self.ap['heading'] += delta
        self.message = f"HDG: {self.ap['heading']} amt {amount} new {new_hdg}"
        # self.fetch_state()

    def set_speed(self, new_spd):
        try:
            amount = int(new_spd) - int(self.ap['speed'])
        except:
            amount = int(new_spd) - 100
        if amount > 0:
            endpoint = "MobiFlight.FBW_A32NX_DEV_FCU_SPD_INC"
            delta = 1
        else: 
            endpoint = "MobiFlight.FBW_A32NX_DEV_FCU_SPD_DEC"
            delta = -1
        for _ in range(min(2, abs(amount))):
            self.send_request(endpoint)
            self.ap['speed'] += delta
        self.message = f"SPD: {self.ap['speed']} amt {amount} new {new_spd}"

    def adjust_fl(self, new_fl):
        amount = int((new_fl - self.ap['alt']) / 10)
        if amount > 0:
            endpoint = "MobiFlight.FBW_A32NX_DEV_FCU_ALT_INC"
            delta = 10
        else: 
            endpoint = "MobiFlight.FBW_A32NX_DEV_FCU_ALT_DEC"
            delta = -10
        for _ in range(min(abs(amount), 10)):
            self.send_request(endpoint)
            self.ap['alt'] += delta
        self.message = f"ALT: {self.ap['alt']} amt {amount} new {new_fl}"

    def adjust_vs(self, new_vs):
        amount = int((new_vs - self.ap['vs']) / 100)
        if amount > 0:
            endpoint = "MobiFlight.FBW_A32NX_DEV_FCU_VS_INC"
            delta = 100
        else:
            endpoint = "MobiFlight.FBW_A32NX_DEV_FCU_VS_DEC"
            delta = -100
        for _ in range(min(abs(amount), 10)):
            self.send_request(endpoint)
            self.ap['vs'] += delta
        self.message = f"VS: {self.ap['vs']} amt {amount} new {new_vs}"

class MysterySpaceship(Airplane):
    def __init__(self):
        super().__init__()
        self.plane_type = "X"
        self.message = "MysterySpaceship initialized"
        self.sound_cooldowns = { }
        self.oxygen_levels = 100
        print("initializing mp3 player")
        self.vibe_1 = LoopingMP3Player('music/myNoise_HealingWater.mp3')
        self.vibe_2 = LoopingMP3Player('music/myNoise_AzureTrails.mp3')
        self.vibe_3 = LoopingMP3Player('music/myNoise_SpaceExploration.mp3')
        self.vibe_4 = LoopingMP3Player('music/myNoise_VoltageBytes.mp3')

        self.vibe_1.set_volume(0)
        self.vibe_2.set_volume(0)
        self.vibe_3.set_volume(0)
        self.vibe_4.set_volume(0)

        self.vibe_1.play()
        self.vibe_2.play()
        self.vibe_3.play()
        self.vibe_4.play()

        print("hello")


    def update_knobs(self, knobs_moved, knob_values, keys_being_pressed):
        if super().update_knobs(knobs_moved, knob_values, keys_being_pressed):
            return True
        
        # map from knob val of 0 - 128 to 0.0 - 1.0
        if knobs_moved[0]:
            self.vibe_1.set_volume(knob_values[0]/128)
        if knobs_moved[1]:
            self.vibe_2.set_volume(knob_values[1]/128)
        if knobs_moved[2]:
            self.vibe_3.set_volume(knob_values[2]/128)
        if knobs_moved[3]:
            self.vibe_4.set_volume(knob_values[3]/128)
        
        return True

    def send_request(self, endpoint, body=None):
        return True
    
    def get_announcements_list(self):
        return [fname.replace('mystery_', '') for fname in os.listdir(script_dir/'sfx') if 'mystery' in fname] + ['beep.mp3']

    def heartbeat(self):
        if tuple_to_str(self.radio[self.active_radio]['active']) == "118.100":
            sound_name = "beep.mp3"
            if sound_name not in self.sound_cooldowns or time.time() - self.sound_cooldowns[sound_name] > 5:
                play_sound(fname="beep.mp3")
                self.message = "played sound"
                self.sound_cooldowns['beep.mp3'] = time.time() + 5
        else:
            self.sound_cooldowns = { }


    def set_oxygen_levels(self, delta):
        self.oxygen_levels += delta
        if self.oxygen_levels > 120:
            time.sleep(2)
            self.say("Warning: oxygen levels too high. Decreasing to nominal.")
            self.oxygen_levels = 100
        if self.oxygen_levels < 80:
            time.sleep(2)
            self.say("Warning: oxygen levels too low. Increasing to nominal.")
            self.oxygen_levels = 100

    def handle_key_press(self, note, velocity):
        # return True to stop the Keystep's handle_key_press from executing
        if super().handle_key_press(note, velocity):
            return True

        if note < 68:
            return False

        if note == 68:
            # self.say("Cannot set heading in orbit mode.")
            pass
        elif note == 70:
            # self.say("Galactic positioning system locked")
            pass
        elif note == 77:
            # self.say("Cruise mode already activated")
            pass
        elif note == 78:
            # self.say("WARNING: Autopilot disengaged")
            pass
        elif note == 80:
            # self.say("decreasing oxygen levels")
            # self.set_oxygen_levels(-10)
            pass
        elif note == 82:
            # self.say("increasing oxygen levels")
            # self.set_oxygen_levels(-10)
            pass
        elif note == 83:
            # play_sound(fname='access-denied.mp3')
            pass
        elif note == 84:
            # play_sound(fname='access-denied.mp3')
            pass

        # don't let the default keystep logic do anything
        return True

