import rtmidi
import time

knob_values = {0: 0, 1: 0, 2: 0, 3: 0}

def midi_callback(message, time_stamp):
    message, delta_time = message
    if message[0] & 0xF0 == 0xB0:  # CC message
        cc_number, cc_value = message[1], message[2]
        # if cc_number in knob_values:
        #     knob_values[cc_number] = cc_value
        knob_values[cc_number] = cc_value
    elif message[0] & 0xF0 == 0x90:  # Note On
        print('nope')
    print(knob_values)

midi_in = rtmidi.MidiIn()
available_ports = midi_in.get_ports()

if available_ports:
    midi_in.open_port(0)
    print(f"Listening on {available_ports[0]}")
    midi_in.set_callback(midi_callback)
    
    print("Turn some knobs on your KeyStep 37...")
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        midi_in.close_port()
        del midi_in
else:
    print("No MIDI ports available")
