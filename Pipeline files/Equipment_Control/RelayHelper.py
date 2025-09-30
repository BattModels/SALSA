
import hid
import time
import serial

path = b'\\\\?\\HID#VID_16C0&PID_05DF#8&20d8742f&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}' # 24-V relay path
device_path =  b'\\\\?\\HID#VID_16C0&PID_05DF#8&be40740&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}' # 12-V relay path
device_path2 = b'\\\\?\\HID#VID_16C0&PID_05DF#6&2e11b7e6&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}' # Unused


def terminate():
    device = hid.device()
    device.open_path(device_path)


    for i in range(1, 9):
        cmd = [0x00, 0xFD, i]
        device.send_feature_report(cmd)
    '''
    device = hid.device()
    device.open_path(device_path)


    for i in range(1, 9):
        cmd = [0x00, 0xFD, i]
        device.send_feature_report(cmd)
    '''

if __name__ == '__main__':
    for device in hid.enumerate():
        print(f"Device Info:\n{'-'*40}")
        for key, value in device.items():
            print(f"{key}: {value}")
        print("\n")

    device = hid.device()
    device.open_path(path)
    for i in range(1):
        cmd = [0x00, 0xFD, 5] 
        device.send_feature_report(cmd)
        cmd = [0x00, 0xFD, 6]
        device.send_feature_report(cmd)
        # time.sleep(0.5)

    




'''
if __name__ == '__main__':
    device = hid.device()
    device.open_path(path)
    cmd = [0x00, 0xFF, 1]
    device.send_feature_report(cmd)
    cmd = [0x00, 0xFF, 2]
    device.send_feature_report(cmd)
    '''