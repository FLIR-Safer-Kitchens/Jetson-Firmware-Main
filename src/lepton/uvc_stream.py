"""Stream video from the PureThermal Lepton driver using libuvc"""

from .uvc_structs import *
from queue import Queue
from constants import *
import numpy as np
import logging


class QueueStruct(Structure):
    """ctypes structure to wrap a Python queue object"""
    _fields_ = [("queue", py_object)]


class PureThermalUVC:
    """
    Uses the GroupGets libuvc library to stream raw thermal video from a PureThermal board

    See https://github.com/groupgets/purethermal1-uvc-capture
    """

    def __init__(self, libuvc_dll):
        # Configure logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Load libuvc library
        self.libuvc = cdll.LoadLibrary(libuvc_dll)

        # Queue to buffer frame data
        self.frame_queue = Queue(2)

        # Ctypes wrapper for frame queue
        self.frame_queue_struct = QueueStruct(self.frame_queue)

        # Create pointer for stream control object
        self.ctrl = uvc_stream_ctrl()


    def start_stream(self):
        """Connects to PureThermal board and opens the raw-16 video stream"""

        # Check for open stream
        if any([hasattr(self, ptr) for ptr in ('ctx', 'dev', 'devh')]):
            self.logger.warning("A stream is already open, call stop_stream() first")
            return

        # Clear old frames
        while not self.frame_queue.empty():
            self.frame_queue.get_nowait()

        # Initialize the libuvc context
        temp = POINTER(uvc_context)()
        res = self.libuvc.uvc_init(
            byref(temp), # The location where the context reference should be stored.
            0            # USB context to use, NULL uses default context
        )
        assert res == 0, f"uvc_init error: {res} {uvc_err_msg(res)}"
        self.ctx = temp
            
        # Find Lepton
        temp = POINTER(uvc_device)()
        res = self.libuvc.uvc_find_device(
            self.ctx,    # UVC context in which to search for the camera
            byref(temp), # Reference to the camera, or NULL if not found
            PT_USB_VID,  # Vendor ID number
            PT_USB_PID,  # Product ID number
            0            # Serial number, NULL here
        )
        assert res == 0, f"uvc_find_device error: {res} {uvc_err_msg(res)}"
        self.dev = temp
            
        # Open UVC connection to Lepton
        temp = POINTER(uvc_device_handle)()
        res = self.libuvc.uvc_open(
            self.dev,   # Device to open
            byref(temp) # Handle on opened device
        )
        assert res == 0, f"uvc_open error: {res} {uvc_err_msg(res)}"
        self.devh = temp

        # Disable automatic FFC
        # TODO: Was getting some new error after adding this? Resource busy or smth
        # self._set_ffc_mode(LEP_SYS_FFC_SHUTTER_MODE_E.LEP_SYS_FFC_SHUTTER_MODE_MANUAL)

        # Select the format, resolution, and frame rate for the stream
        res = self.libuvc.uvc_get_stream_ctrl_format_size(
            self.devh,            # Device handle
            byref(self.ctrl),     # Device control object
            UVC_FRAME_FORMAT_Y16, # Constant to select raw 16-bit format
            RAW_THERMAL_SHAPE[1], # Frame width
            RAW_THERMAL_SHAPE[0], # Frame height
            RAW_THERMAL_RATE      # Frame rate
        )
        assert res == 0, f"uvc_get_stream_ctrl_format_size error: {res} {uvc_err_msg(res)}"

        # Start stream
        queue_ptr = pointer(self.frame_queue_struct)
        res = self.libuvc.uvc_start_streaming(
            self.devh,          # Device handle
            byref(self.ctrl),   # Device control object
            FRAME_CALLBACK_PTR, # Frame callback
            queue_ptr,          # User pointer
            0                   # Flags
        )
        assert res == 0, f"uvc_start_streaming error: {res} {uvc_err_msg(res)}"


    def stop_stream(self):
        """Closes the stream (if running) and deallocates any resources"""

        # Library failed to load
        if not hasattr(self, "libuvc"):
            return

        # Close the stream, free handle and all streaming resources
        if hasattr(self, 'devh'):
            self.libuvc.uvc_stop_streaming(self.devh)
            delattr(self, 'devh')

        # Release the Lepton
        if hasattr(self, 'dev'):
            self.libuvc.uvc_unref_device(self.dev)
            delattr(self, 'dev')
            
        # Close the UVC context. Shuts down any active cameras
        if hasattr(self, 'ctx'):
            self.libuvc.uvc_exit(self.ctx)
            delattr(self, 'ctx')


    def _set_ffc_mode(self, mode):
        """
        Sets the Lepton's FFC mode. Useful for enabling/disabling automatic FFC.

        Parameters:
        - mode (int): New shutter mode. Should be a member of LEP_SYS_FFC_SHUTTER_MODE_E
        """

        # Check if device is configured
        if not hasattr(self, 'devh'):
            return

        # Read shutter mode
        shutter_obj = LEP_SYS_FFC_SHUTTER_MODE_OBJ_T()
        self.libuvc.uvc_get_ctrl(self.devh, 6, 16, byref(shutter_obj), 32, 0x81)
        self.logger.debug(f"Shutter Info:\n{str(shutter_obj)}")

        # Change shutter mode
        if shutter_obj.shutterMode == mode: return
        shutter_obj.shutterMode = mode
        self.libuvc.uvc_set_ctrl(self.devh, 6, 16, byref(shutter_obj), 32, 0x81)

        # Check shutter mode
        self.libuvc.uvc_get_ctrl(self.devh, 6, 16, byref(shutter_obj), 32, 0x81)
        if shutter_obj.shutterMode != mode:
            self.logger.warning(f"Failed to set shutter mode. Expected {str(mode)}, got {str(shutter_obj.shutterMode)}.")


    def read(self):
        """
        Read a frame (if available) from the active stream
        
        Returns (tuple [bool, np.array]): First returns True if frame is valid,
        then the frame (None if invalid)
        """
        if self.frame_queue.empty():
            return False, None
        
        return True, self.frame_queue.get_nowait()



def py_frame_callback(frame_struct_ptr, queue_struct_ptr):
    """Callback function for new frame data. Invoked by libuvc"""

    # Dereference frame struct pointer and get contents
    frame = cast(frame_struct_ptr, POINTER(uvc_frame)).contents
    
    # Get frame dimensions
    w = frame.width
    h = frame.height

    # Check data size (bytes)
    if frame.data_bytes != 2*(w*h): return

    # Get a pointer to the array
    array_pointer = cast(frame.data, POINTER(c_uint16*(w*h)))

    # Specify the data type and shape
    data = np.frombuffer(array_pointer.contents, dtype=np.dtype(np.uint16))
    data = data.reshape(h, w)

    # Dereference the queue struct pointer and extract the python queue
    queue_ptr = cast(queue_struct_ptr, POINTER(QueueStruct))
    frame_queue = queue_ptr.contents.queue

    # Add the frame to the buffer
    try: frame_queue.put(data, block=False)
    except: pass

# Create pointer to callback function
FRAME_CALLBACK_PTR = CFUNCTYPE(None, POINTER(uvc_frame), c_void_p)(py_frame_callback)
