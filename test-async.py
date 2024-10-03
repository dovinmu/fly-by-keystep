import rtmidi
import time

class KeystepController:
    def __init__(self):
        self.midi_in = rtmidi.MidiIn()
        self.knob_values = {0: 0, 1: 0, 2: 0, 3: 0}
        self.com_active = {
            1: (118,0),
            2: (118,0)
        }
        self.active_com = 1
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
    
    def midi_callback(self, message, time_stamp):
        message, delta_time = message
        if message[0] & 0xF0 == 0xB0:  # CC message
            cc_number, cc_value = message[1], message[2]
            if cc_number in self.knob_values:
                self.handle_knob(cc_number, cc_value)
        elif message[0] & 0xF0 == 0x90:  # Note On
            print('Note pressed')
        # print(self.knob_values, end='\r')
        print(self.knob_values)

    def handle_knob(self, knob, value):
        self.knob_values[knob] = value
        # print(f"Knob {knob} turned to {value}")

    def update_comms(self):
        # print(f"Knob position: {self.knob_values}, Active COM: {self.com_active[self.active_com]}")
        current_integer = self.map_integer_knob(self.knob_values[0])
        current_fractional = self.map_fractional_knob(self.knob_values[1])

        # check if active integer comm needs to be updated
        if current_integer != self.com_active[self.active_com][0]:
            # self.adjust_integer_direct(current_integer)
            print("adjust integer")

        # check if active fractional comm needs to be updated
        if current_fractional != self.com_active[self.active_com][1]:
            # self.adjust_fractional_direct(current_fractional)
            print("adjust fractional")


    def run(self):
        available_ports = self.midi_in.get_ports()

        if available_ports:
            self.midi_in.open_port(0)
            print(f"Listening on {available_ports[0]}")
            self.midi_in.set_callback(self.midi_callback)
            
            print("Turn some knobs on your KeyStep 37...")
            try:
                while True:
                    time.sleep(0.1)
                    self.update_comms()
            except KeyboardInterrupt:
                print("\nExiting...")
            finally:
                self.midi_in.close_port()
                del self.midi_in
        else:
            print("No MIDI ports available")

if __name__ == "__main__":
    controller = KeystepController()
    controller.run()
