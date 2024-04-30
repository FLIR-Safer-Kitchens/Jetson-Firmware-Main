"""Class for handling PureThermal UVC stream on Windows"""

from multiprocessing import Queue
import numpy as np
import platform
import logging
import sys
import os


class PureThermalWindows:
    """Uses FLIR's python SDK for Lepton to stream raw thermal video from a PureThermal board"""

    def __init__(self):
        # === Special imports ===
        import clr # requires "pythonnet" package
        
        # check whether python is running as 64bit or 32bit
        # to import the right .NET dll
        folder = ["x64"] if (platform.architecture()[0] == "64bit") else ["x86"]

        # Add driver directory to python path
        driver_dir = os.path.dirname(__file__)
        sys.path.append(os.path.join(driver_dir, "win_drivers/", *folder))

        # AddReference makes the following `From Lepton ...` line 
        # run by hooking the LeptonUVC dll into the python import mechanism
        clr.AddReference("LeptonUVC")
        from Lepton import CCI
        self.CCI = CCI

        # Imports for image capture
        clr.AddReference("ManagedIR16Filters") 
        from IR16Filters import IR16Capture, NewBytesFrameEvent
        IR16Capture = IR16Capture
        NewBytesFrameEvent = NewBytesFrameEvent
        # =========================

        # Configure logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Queue to buffer frame data
        PureThermalWindows.frame_queue = Queue(2)

        # Lepton capture object
        self.capture = IR16Capture()
        self.capture.SetupGraphWithBytesCallback(NewBytesFrameEvent(frame_callback))


    def start_stream(self):
        """Connects to PureThermal board and opens the raw-16 video stream"""

        # Search for lepton
        lepton_device = None
        devices = self.CCI.GetDevices()
        for dev in devices:
            if dev.Name.startswith("PureThermal"):
                self.logger.debug("Found lepton")
                lepton_device = dev
                break
        
        assert lepton_device != None, "Failed to find lepton"

        # Open lepton
        self.lep = lepton_device.Open()
        assert self.lep.sys.GetCameraUpTime() > 0, "Failed to open lepton"
        self.logger.debug("Lepton opened successfully")

        # Configure camera settings
        # Disable AGC
        self.lep.agc.SetEnableStateChecked(self.lep.agc.Enable.DISABLE)
        assert self.lep.agc.GetEnableStateChecked() == self.lep.agc.Enable.DISABLE

        # Enable Radiometry
        self.lep.rad.SetEnableStateChecked(self.lep.rad.Enable.ENABLE)
        assert self.lep.rad.GetEnableState() == self.lep.rad.Enable.ENABLE

        # Turn on TLinear
        self.lep.rad.SetTLinearEnableStateChecked(self.lep.rad.Enable.ENABLE)
        assert self.lep.rad.GetTLinearEnableState() == self.lep.rad.Enable.ENABLE

        # Set Gain to High
        self.lep.sys.SetGainMode(self.CCI.Sys.GainMode.HIGH)
        assert self.lep.sys.GetGainMode() == self.CCI.Sys.GainMode.HIGH

        # Begin/restart video capture
        self.capture.RunGraph()


    def stop_stream(self):
        """Closes the stream (if running)"""
        if hasattr(self, 'capture'):
            self.capture.StopGraph()


    def read(self):
        """
        Read a frame (if available) from the active stream
        
        Returns (tuple [bool, np.array]): First returns True if frame is valid,
        then the frame (None if invalid)
        """
        if self.frame_queue.empty():
            return False, None
        
        return True, self.frame_queue.get_nowait()


def frame_callback(short_array, width, height):
    """
    Callback for new frame
    Parameters:
    - sort_array (np.ndarry): Raw buffer of pixel values
    - width (int): Frame width
    - height (int): Frame height
    """

    # Specify the data type and shape
    incoming_data = np.fromiter(short_array, dtype="uint16")
    frame = incoming_data.reshape(height, width)
    
    # Add frame to queue
    if not PureThermalWindows.frame_queue.full():
        PureThermalWindows.frame_queue.put(frame)
