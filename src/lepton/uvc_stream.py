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
    """Uses the GroupGets libuvc library to stream raw thermal video from a PureThermal board"""

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

        # Define pointers to structs
        self.ctx  = POINTER(uvc_context)()
        self.dev  = POINTER(uvc_device)()
        self.devh = POINTER(uvc_device_handle)()
        self.ctrl = uvc_stream_ctrl()


    def start_stream(self):
        """Connects to PureThermal board and opens the raw-16 video stream"""

        # Check for open stream
        if any([ptr != None for ptr in (self.ctx, self.dev, self.devh)]):
            self.logger.warning("A stream is already open, call stop_stream() first")
            return

        # Clear old frames
        while not self.frame_queue.empty():
            self.frame_queue.get_nowait()

        # Initialize the libuvc context
        res = self.libuvc.uvc_init(
            byref(self.ctx), # The location where the context reference should be stored.
            0                # USB context to use, NULL uses default context
        )
        assert res == 0, f"uvc_init error: {res} {uvc_err_msg(res)}"
            
        # Find Lepton
        res = self.libuvc.uvc_find_device(
            self.ctx,        # UVC context in which to search for the camera
            byref(self.dev), # Reference to the camera, or NULL if not found
            PT_USB_VID,      # Vendor ID number
            PT_USB_PID,      # Product ID number
            0                # Serial number, NULL here
        )
        assert res == 0, f"uvc_find_device error: {res} {uvc_err_msg(res)}"
            
        # Open UVC connection to Lepton
        res = self.libuvc.uvc_open(
            self.dev,        # Device to open
            byref(self.devh) # Handle on opened device
        )
        assert res == 0, f"uvc_open error: {res} {uvc_err_msg(res)}"

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
        if self.devh != None:
            self.libuvc.uvc_stop_streaming(self.devh)

        # Release the Lepton
        if self.dev != None:
            self.libuvc.uvc_unref_device(self.dev)
            
        # Close the UVC context. Shuts down any active cameras
        if self.ctx != None:
            self.libuvc.uvc_exit(self.ctx)


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
    if frame.data_bytes != 2*(w*h):
        return None

    # Get a pointer to the array
    array_pointer = cast(frame.data, POINTER(c_uint16*(w*h)))

    # Specify the data type and shape
    data = np.frombuffer(array_pointer.contents, dtype=np.dtype(np.uint16))
    data = data.reshape(h, w)

    # Dereference the queue struct pointer and extract the python queue
    queue_ptr = cast(queue_struct_ptr, POINTER(QueueStruct))
    frame_queue = queue_ptr.contents.queue

    # Add the frame to the buffer
    if not frame_queue.full():
        frame_queue.put(data)

# Create pointer to callback function
FRAME_CALLBACK_PTR = CFUNCTYPE(None, POINTER(uvc_frame), c_void_p)(py_frame_callback)
