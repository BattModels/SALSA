import subprocess
import hid
import time

def reset_device_by_hwid(hwid):
    """
    Reset a device by hardware ID using devcon.
    Requires devcon.exe installed and in PATH.
    """
    try:
        # Disable the device
        subprocess.run(["devcon", "disable", hwid], check=True, capture_output=True)
        print(f"[INFO] Disabled device {hwid}")
        time.sleep(3)
        # Re-enable the device
        subprocess.run(["devcon", "enable", hwid], check=True, capture_output=True)
        print(f"[INFO] Enabled device {hwid}")

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] devcon failed: {e.stderr.decode()}")

# Example usage (replace with your COM port or HID hardware ID)
reset_device_by_hwid(b'\\\\?\\HID#VID_16C0&PID_05DF#8&20d8742f&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}')
device = hid.device()
time.sleep(3)
device.open_path(b'\\\\?\\HID#VID_16C0&PID_05DF#8&20d8742f&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}')
