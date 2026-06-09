import asyncio
from evdev import InputDevice, UInput, ecodes

# 1. REPLACE THESE WITH YOUR ACTUAL EVENT PATHS FOUND IN STEP 2
DECK_PATH = '/dev/input/event21'     # Example Steam Deck built-in path
EXTERNAL_PATH = '/dev/input/event25' # Example external controller path

def create_virtual_gamepad():
    """Defines the capabilities of the merged virtual controller (Xbox Layout)."""
    # Capabilities layout dictionary
    cap = {
        ecodes.EV_KEY: [
            ecodes.BTN_A, ecodes.BTN_B, ecodes.BTN_X, ecodes.BTN_Y,
            ecodes.BTN_TL, ecodes.BTN_TR, ecodes.BTN_SELECT, ecodes.BTN_START,
            ecodes.BTN_THUMBL, ecodes.BTN_THUMBR
        ],
        ecodes.EV_ABS: [
            (ecodes.ABS_X, (0, 255, 0, 0)),     # Left Stick X
            (ecodes.ABS_Y, (0, 255, 0, 0)),     # Left Stick Y
            (ecodes.ABS_RX, (0, 255, 0, 0)),    # Right Stick X
            (ecodes.ABS_RY, (0, 255, 0, 0)),    # Right Stick Y
            (ecodes.ABS_Z, (0, 255, 0, 0)),     # Left Trigger
            (ecodes.ABS_RZ, (0, 255, 0, 0)),    # Right Trigger
            (ecodes.ABS_HAT0X, (-1, 1, 0, 0)),  # D-Pad X
            (ecodes.ABS_HAT0Y, (-1, 1, 0, 0))   # D-Pad Y
        ]
    }
    # Create the virtual device
    return UInput(cap, name="Merged-Virtual-Gamepad", vendor=0x045e, product=0x028e)

async def handle_events(device, v_gamepad):
    """Listens to an input device and clones inputs to the virtual gamepad."""
    async for event in device.async_read_loop():
        # Filter out synchronization events to map clean raw inputs
        if event.type != ecodes.EV_SYN:
            v_gamepad.write(event.type, event.code, event.value)
            v_gamepad.syn()

async def main():
    try:
        deck = InputDevice(DECK_PATH)
        external = InputDevice(EXTERNAL_PATH)
        v_gamepad = create_virtual_gamepad()
        
        print(f"Successfully hooked: {deck.name} & {external.name}")
        print("Virtual Merged Gamepad is active. Press Ctrl+C to exit.")
        
        # Concurrently listen to both devices at the same time
        await asyncio.gather(
            handle_events(deck, v_gamepad),
            handle_events(external, v_gamepad)
        )
    except PermissionError:
        print("Error: You must run this script with 'sudo' privileges.")
    except FileNotFoundError:
        print("Error: One of the specified controller event paths was not found.")

if __name__ == "__main__":
    asyncio.run(main())
