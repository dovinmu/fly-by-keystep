import rtmidi
import time

# def midi_callback(message, time_stamp):
#     print(f"{message}")

def handle_key_press(note, vel):
    print(note, vel)

def handle_aftertouch(vel):
    print("~", vel, "~")

def midi_callback(message, time_stamp):
    print(message)
    message, delta_time = message
    if message[0] == 208:  # Aftertouch
        handle_aftertouch(message[1])
    elif message[0] & 0xF0 == 0x90:  # Note On
        handle_key_press(message[1], message[2])
    elif message[0] == 128:
        print("end", message[1])
    else:
        print(message[0])

midi_in = rtmidi.MidiIn()
available_ports = midi_in.get_ports()

if available_ports:
    midi_in.open_port(0)
    print(f"Listening on {available_ports[0]}")
    midi_in.set_callback(midi_callback)
    
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
