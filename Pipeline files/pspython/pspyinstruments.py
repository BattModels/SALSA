from enum import Enum
import traceback
from time import sleep
import queue
import pspython.pspydata as pspydata
import asyncio

import System
import PalmSens
from PalmSens.Windows.Devices import FTDIDevice, USBCDCDevice, BluetoothDevice
from PalmSens.Comm import CommManager

def discover_instruments(**kwargs):
        discover_ftdi = kwargs.get('ftdi', True)
        discover_usbcdc = kwargs.get('usbcdc', True)
        discover_bluetooth = kwargs.get('bluetooth', False)
        available_instruments = []

        if discover_ftdi:
            ftdi_instruments = FTDIDevice.DiscoverAllDevices("")
            for ftdi_instrument in ftdi_instruments[0]:
                instrument = Instrument(ftdi_instrument.ToString(), 'ftdi', ftdi_instrument)
                available_instruments.append(instrument)

        if discover_usbcdc:
            usbcdc_instruments = USBCDCDevice.DiscoverDevices("")
            for usbcdc_instrument in usbcdc_instruments[0]:                                
                instrument = Instrument(usbcdc_instrument.ToString(), 'usbcdc', usbcdc_instrument)
                available_instruments.append(instrument)

        return available_instruments
    

class Instrument:
    def __init__(self, name, conn, device):
        self.name = name
        self.connection = conn
        self.device = device


class InstrumentManager:
    def __init__(self, **kwargs):
        self.new_data_callback = kwargs.get('new_data_callback', None)
        self.__comm = None
        self.__measuring = False
        self.__measuring_started = False
        self.__active_measurement = None
        self.__active_curve = None
        self.__active_EISdata = None
        self.__active_eis_data = None
        self.__index_last_sent_point = 0
        self.__queue = queue.Queue()

    def connect(self, instrument):
        if self.__comm is not None:
            print('An instance of the InstrumentManager can only be connected to one instrument at a time')
            return 0
        try:
            __instrument = instrument.device
            __instrument.Open()
            self.__comm = CommManager(__instrument)
            return 1
        except Exception as e:
            #traceback.print_exc()
            try:
                __instrument.Close()
            except:
                pass
            return str(e)

    def measure(self, method):
        if self.__comm is None:
            return 'Not connected to an instrument'

        try:
            # subscribe to events indicating the start and end of the measurement
            self.__comm.BeginMeasurement += self.__measurement_started_callback
            self.__comm.EndMeasurement += self.__measurement_ended_callback            
            self.__comm.BeginReceiveEISData += self.__receiving_eis_data_callback
            self.__comm.BeginReceiveCurve += self.__receiving_curve_callback

            # obtain lock on library (required when communicating with instrument)
            self.__comm.ClientConnection.Semaphore.Wait()

            # send and execute the method on the instrument
            self.__comm.Measure(method)
            self.__measuring = True

            # release lock on library (required when communicating with instrument)
            self.__comm.ClientConnection.Semaphore.Release()

            while self.__measuring:
                qsize = self.__queue.qsize()
                for i in range(qsize):
                    callback = self.__queue.get()                    
                    callback()
                    self.__queue.task_done()
                sleep(.001)

            measurement = self.__active_measurement
            self.__active_measurement = None
            return pspydata.convert_to_measurement(measurement)

        except Exception as e:
            #traceback.print_exc()

            if self.__comm.ClientConnection.Semaphore.CurrentCount == 0:
                # release lock on library (required when communicating with instrument)
                self.__comm.ClientConnection.Semaphore.Release()

            self.__active_measurement = None
            self.__comm.BeginMeasurement -= self.__measurement_started_callback
            self.__comm.EndMeasurement -= self.__measurement_ended_callback
            self.__comm.BeginReceiveEISData -= self.__receiving_eis_data_callback
            self.__comm.BeginReceiveCurve -= self.__receiving_curve_callback
            self.__measuring = False
            return str(e)

    async def wait_digital_trigger(self, wait_for_high):
        if self.__comm is None:
            return 'Not connected to an instrument'

        try: 
            # obtain lock on library (required when communicating with instrument)
            self.__comm.ClientConnection.Semaphore.Wait()

            while True:
                if self.__comm.DigitalLineD0 == wait_for_high:
                    break
                await asyncio.sleep(.05)

            self.__comm.ClientConnection.Semaphore.Release()

        except Exception as e:
            #traceback.print_exc()        

            if self.__comm.ClientConnection.Semaphore.CurrentCount == 0:
                # release lock on library (required when communicating with instrument)
                self.__comm.ClientConnection.Semaphore.Release()
            return str(e)
        return

    async def measure_async(self, method, **kwargs):
        return_dotnet_object = kwargs.get('return_dotnet_object', False)

        if self.__comm is None:
            return 'Not connected to an instrument'

        try:
            # subscribe to events indicating the start and end of the measurement
            self.__comm.BeginMeasurement += self.__measurement_started_callback
            self.__comm.EndMeasurement += self.__measurement_ended_callback            
            self.__comm.BeginReceiveEISData += self.__receiving_eis_data_callback
            self.__comm.BeginReceiveCurve += self.__receiving_curve_callback

            # obtain lock on library (required when communicating with instrument)
            self.__comm.ClientConnection.Semaphore.Wait()

            # send and execute the method on the instrument
            self.__comm.Measure(method)
            self.__measuring = True

            # release lock on library (required when communicating with instrument)
            self.__comm.ClientConnection.Semaphore.Release()

            while self.__measuring:
                qsize = self.__queue.qsize()
                for i in range(qsize):
                    callback = self.__queue.get()                    
                    callback()
                    self.__queue.task_done()
                await asyncio.sleep(.001)

            measurement = self.__active_measurement
            self.__active_measurement = None
            return pspydata.convert_to_measurement(measurement, return_dotnet_object=return_dotnet_object)

        except Exception as e:
            #traceback.print_exc()

            if self.__comm.ClientConnection.Semaphore.CurrentCount == 0:
                # release lock on library (required when communicating with instrument)
                self.__comm.ClientConnection.Semaphore.Release()

            self.__active_measurement = None
            self.__comm.BeginMeasurement -= self.__measurement_started_callback
            self.__comm.EndMeasurement -= self.__measurement_ended_callback
            self.__comm.BeginReceiveEISData -= self.__receiving_eis_data_callback
            self.__comm.BeginReceiveCurve -= self.__receiving_curve_callback
            self.__measuring = False
            self.__measuring_started = False
            return str(e)

    async def start_measure_async(self, method):
        if self.__comm is None:
            return 'Not connected to an instrument'

        try:
            self.__measuring_started = False

            # subscribe to events indicating the start and end of the measurement
            self.__comm.BeginMeasurement += self.__measurement_started_callback            
            self.__comm.BeginReceiveEISData += self.__start_receiving_eis_data_callback
            self.__comm.BeginReceiveCurve += self.__receiving_curve_callback  

            # obtain lock on library (required when communicating with instrument)
            self.__comm.ClientConnection.Semaphore.Wait()

            # send and execute the method on the instrument
            self.__comm.Measure(method)
            self.__measuring = True

            # release lock on library (required when communicating with instrument)
            self.__comm.ClientConnection.Semaphore.Release()

            while self.__measurement_started is False:
                qsize = self.__queue.qsize()
                for i in range(qsize):
                    callback = self.__queue.get()                    
                    callback()
                    self.__queue.task_done()
                await asyncio.sleep(.001)

            return True

        except Exception as e:
            #traceback.print_exc()

            if self.__comm.ClientConnection.Semaphore.CurrentCount == 0:
                # release lock on library (required when communicating with instrument)
                self.__comm.ClientConnection.Semaphore.Release()

            self.__active_measurement = None
            self.__active_curve = None
            self.__active_EISdata = None
            self.__comm.BeginMeasurement -= self.__measurement_started_callback
            self.__comm.BeginReceiveEISData -= self.__receiving_eis_data_callback
            self.__comm.BeginReceiveCurve -= self.__receiving_curve_callback
            self.__measuring = False
            self.__measuring_started = False
            return False

    async def get_active_measurement(self):
        # subscribe to events indicating the start and end of the measurement
        self.__comm.EndMeasurement += self.__measurement_ended_callback                
        self.__comm.BeginReceiveEISData += self.__receiving_eis_data_callback
        self.__comm.BeginReceiveCurve += self.__receiving_curve_callback  

        if self.__active_curve is not None:
            self.__active_curve.NewDataAdded += self.__curve_new_data_callback
            self.__active_curve.Finished += self.__curve_finished_callback    
        elif self.__active_EISdata is not None:
            self.__active_EISdata.NewDataAdded += self.__eis_data_new_data_callback
            self.__active_EISdata.Finished += self.__eis_data_finished_callback
        
        try:
            while self.__measuring:
                qsize = self.__queue.qsize()
                for i in range(qsize):
                    callback = self.__queue.get()                    
                    callback()
                    self.__queue.task_done()
                await asyncio.sleep(.001)

            measurement = self.__active_measurement
            self.__active_measurement = None
            self.__active_curve = None
            self.__active_EISdata = None
            return pspydata.convert_to_measurement(measurement)

        except Exception as e:
            #traceback.print_exc()

            if self.__comm.ClientConnection.Semaphore.CurrentCount == 0:
                # release lock on library (required when communicating with instrument)
                self.__comm.ClientConnection.Semaphore.Release()

            self.__active_measurement = None
            self.__active_curve = None
            self.__active_EISdata = None
            self.__comm.EndMeasurement -= self.__measurement_ended_callback
            self.__comm.BeginReceiveEISData -= self.__receiving_eis_data_callback
            self.__comm.BeginReceiveCurve -= self.__receiving_curve_callback
            self.__measuring = False
            self.__measuring_started = False
            return str(e)

    def abort(self):
        if self.__comm is None:
            return 'Not connected to an instrument'

        if __measuring is False:
            return 'Noy measuring'
            
        __comm.Abort()

    def __measurement_started_callback(self, sender, measurement):
        self.__queue.put(lambda: self.__measurement_started(sender, measurement))
        return

    def __measurement_started(self, sender, measurement):
        self.__active_measurement = measurement
        self.__comm.BeginMeasurement -= self.__measurement_started_callback
        return

    def __receiving_eis_data_callback(self, sender, eisdata):
        self.__queue.put(lambda: self.__receiving_eis_data(eisdata))
        return

    def __receiving_eis_data(self, eisdata):
        eisdata.NewDataAdded += self.__eis_data_new_data_callback
        eisdata.Finished += self.__eis_data_finished_callback
        return

    def __start_receiving_eis_data_callback(self, sender, eisdata):
        self.__queue.put(lambda: self.__start_receiving_eis_data(eisdata))
        return

    def __start_receiving_eis_data(self, eisdata):
        self.__active_EISdata = eisdata
        self.__measuring_started = True
        return

    def __eis_data_new_data_callback(self, eisdata, args):        
        if self.new_data_callback is None:
            return
        start = args.Index
        count = 1
        self.__queue.put(lambda: self.__eis_data_update(eisdata, start, count))
        return

    def __eis_data_update(self, eisdata, start, count):
        self.__index_last_sent_point = start + count - 1
        arrays = eisdata.EISDataSet.GetDataArrays()
        if self.new_data_callback is not None:
            for i in range(start, start + count):
                data = {}
                data['index'] = i + 1
                for array in arrays:
                    array_type = pspydata.ArrayType(array.ArrayType)
                    if (array_type == pspydata.ArrayType.Frequency):
                        data['frequency'] = pspydata._get_values_from_NETArray(array, start=i, count=1)
                    elif (array_type == pspydata.ArrayType.ZRe):
                        data['zre'] = pspydata._get_values_from_NETArray(array, start=i, count=1)
                    elif (array_type == pspydata.ArrayType.ZIm):
                        data['zim'] = pspydata._get_values_from_NETArray(array, start=i, count=1)
                self.new_data_callback(data)
        return

    def __eis_data_finished_callback(self, eisdata, args):
        self.__queue.put(lambda: self.__eis_data_finished(eisdata))
        return

    def __eis_data_finished(self, eisdata):        
        eisdata.NewDataAdded -= self.__eis_data_new_data_callback
        eisdata.Finished -= self.__eis_data_finished_callback
        if eisdata.NPoints - self.__index_last_sent_point > 2:
            self.__eis_data_update(eisdata,
                                   self.__index_last_sent_point + 1, eisdata.NPoints - self.__index_last_sent_point)
        return

    def __receiving_curve_callback(self, sender, e):
        self.__queue.put(lambda: self.__receiving_curve(e.GetCurve()))
        return

    def __receiving_curve(self, curve):
        curve.NewDataAdded += self.__curve_new_data_callback
        curve.Finished += self.__curve_finished_callback
        return

    def __start_receiving_curve_callback(self, sender, e):
        self.__queue.put(lambda: self.__start_receiving_curve(e.GetCurve()))
        return

    def __start_receiving_curve(self, curve):
        self.__active_curve = curve
        self.__measuring_started = True
        return

    def __curve_new_data_callback(self, curve, args):
        if self.new_data_callback is None:
            return
        start = args.StartIndex
        count = curve.NPoints - start
        self.__queue.put(lambda: self.__curve_update(curve, start, count))
        return

    def __curve_update(self, curve, start, count):
        self.__index_last_sent_point = start + count - 1
        if self.new_data_callback is not None:
            for i in range(start, start + count):
                data = {}
                data['index'] = i + 1
                data['x'] = pspydata._get_values_from_NETArray(curve.XAxisDataArray, start=i, count=1)
                data['x_unit'] = curve.XUnit.ToString()
                data['x_type'] = pspydata.ArrayType(curve.XAxisDataArray.ArrayType).name
                data['y'] = pspydata._get_values_from_NETArray(curve.YAxisDataArray, start=i, count=1)
                data['y_unit'] = curve.YUnit.ToString()
                data['y_type'] = pspydata.ArrayType(curve.YAxisDataArray.ArrayType).name
                self.new_data_callback(data)
        return


    def __curve_finished_callback(self, curve, args):
        self.__queue.put(lambda: self.__curve_finished(curve))
        return   

    def __curve_finished(self, curve):
        curve.NewDataAdded -= self.__curve_new_data_callback
        curve.Finished -= self.__curve_finished_callback
        return  

    def __measurement_ended_callback(self, sender, args):
        self.__queue.put(lambda: self.__measurement_ended())
        return

    def __measurement_ended(self):
        self.__measuring = False
        self.__comm.EndMeasurement -= self.__measurement_ended_callback
        self.__comm.BeginReceiveCurve -= self.__receiving_curve_callback
        self.__comm.BeginReceiveEISData -= self.__receiving_eis_data_callback
        return

    def disconnect(self):
        if self.__comm is None:
            return 0
        try:
            self.__comm.Disconnect()
            self.__comm = None
            self.__measuring = False
            return 1
        except Exception as e:
            #traceback.print_exc()
            return str(e)


# just a test
if __name__ == '__main__':
    manager = InstrumentManager()
    instruments = manager.discover_instruments()
    success = manager.connect(instrument=instruments[0])
    success = manager.disconnect()
    test = 'test'
