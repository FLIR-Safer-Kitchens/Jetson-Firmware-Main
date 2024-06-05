"""Constants and ctypes structures for interfacing with libuvc"""

from ctypes import *

class uvc_context(Structure):
    _fields_ = [
        ("usb_ctx", c_void_p),
        ("own_usb_ctx", c_uint8),
        ("open_devices", c_void_p),
        ("handler_thread", c_ulong),
        ("kill_handler_thread", c_int)
    ]

class uvc_device(Structure):
    _fields_ = [
        ("ctx", POINTER(uvc_context)),
        ("ref", c_int),
        ("usb_dev", c_void_p)
    ]

class uvc_device_handle(Structure):
    _fields_ = [
        ("dev", POINTER(uvc_device)),
        ("prev", c_void_p),
        ("next", c_void_p),
        ("usb_devh", c_void_p),
        ("info", c_void_p),
        ("status_xfer", c_void_p),
        ("status_buf", c_ubyte * 32),
        ("status_cb", c_void_p),
        ("status_user_ptr", c_void_p),
        ("button_cb", c_void_p),
        ("button_user_ptr", c_void_p),
        ("streams", c_void_p),
        ("is_isight", c_ubyte)
    ]

class uvc_stream_ctrl(Structure):
    _fields_ = [
        ("bmHint", c_uint16),
        ("bFormatIndex", c_uint8),
        ("bFrameIndex", c_uint8),
        ("dwFrameInterval", c_uint32),
        ("wKeyFrameRate", c_uint16),
        ("wPFrameRate", c_uint16),
        ("wCompQuality", c_uint16),
        ("wCompWindowSize", c_uint16),
        ("wDelay", c_uint16),
        ("dwMaxVideoFrameSize", c_uint32),
        ("dwMaxPayloadTransferSize", c_uint32),
        ("dwClockFrequency", c_uint32),
        ("bmFramingInfo", c_uint8),
        ("bPreferredVersion", c_uint8),
        ("bMinVersion", c_uint8),
        ("bMaxVersion", c_uint8),
        ("bInterfaceNumber", c_uint8)
    ]

class timeval(Structure):
    _fields_ = [("tv_sec", c_long), ("tv_usec", c_long)]

class uvc_frame(Structure):
    _fields_ = [
        ("data", POINTER(c_uint8)), # Image data for this frame
        ("data_bytes", c_size_t), # Size of image data buffer
        ("width", c_uint32), # Width of image in pixels
        ("height", c_uint32), # Height of image in pixels
        ("frame_format", c_uint), # Pixel data format. enum uvc_frame_format frame_format
        ("step", c_size_t), # Number of bytes per horizontal line (undefined for compressed format)
        ("sequence", c_uint32), # Frame number (may skip, but is strictly monotonically increasing)
        ("capture_time", timeval), # Estimate of system time when the device started capturing the image
        ("source", POINTER(uvc_device)), # Handle on the device that produced the image. WARNING: You must not call any uvc_* functions during a callback.
        ("library_owns_data", c_uint8) # Is the data buffer owned by the library? Set this field to zero if you are supplying the buffer.
    ]


UVC_ERRORS = { 
    0   : "Success (no error)",
    -1  : "Input/output error",
    -2  : "Invalid parameter",
    -3  : "Access denied",
    -4  : "No such device",
    -5  : "Entity not found",
    -6  : "Resource busy",
    -7  : "Operation timed out",
    -8  : "Overflow",
    -9  : "Pipe error",
    -10 : "System call interrupted",
    -11 : "Insufficient memory",
    -12 : "Operation not supported",
    -50 : "Device is not UVC-compliant",
    -51 : "Mode not supported",
    -52 : "Resource has a callback (can't use polling and async)",
    -99 : "Undefined error"
}

# Function to fetch error message given a return code
uvc_err_msg = lambda ret_code: UVC_ERRORS[ret_code] if ret_code in UVC_ERRORS else ""


# Format IDs
UVC_FRAME_FORMAT_UYVY = 4
UVC_FRAME_FORMAT_I420 = 5
UVC_FRAME_FORMAT_RGB = 7
UVC_FRAME_FORMAT_BGR = 8
UVC_FRAME_FORMAT_Y16 = 13


class LEP_SYS_FFC_SHUTTER_MODE_E(c_int):
    """Shutter mode enum"""
    LEP_SYS_FFC_SHUTTER_MODE_MANUAL = 0
    LEP_SYS_FFC_SHUTTER_MODE_AUTO = 1
    LEP_SYS_FFC_SHUTTER_MODE_EXTERNAL = 2
    LEP_SYS_FFC_SHUTTER_MODE_END = 3

    def __str__(self):
        values = {
            0: "LEP_SYS_FFC_SHUTTER_MODE_MANUAL",
            1: "LEP_SYS_FFC_SHUTTER_MODE_AUTO",
            2: "LEP_SYS_FFC_SHUTTER_MODE_EXTERNAL",
            3: "LEP_SYS_FFC_SHUTTER_MODE_END",
        }
        return values.get(self.value, f"Unknown({self.value})")


class LEP_SYS_SHUTTER_TEMP_LOCKOUT_STATE_E(c_int):
    """Shutter thermal lockout enum"""
    LEP_SYS_SHUTTER_LOCKOUT_INACTIVE = 0
    LEP_SYS_SHUTTER_LOCKOUT_HIGH = 1
    LEP_SYS_SHUTTER_LOCKOUT_LOW = 2

    def __str__(self):
        values = {
            0: "LEP_SYS_SHUTTER_LOCKOUT_INACTIVE",
            1: "LEP_SYS_SHUTTER_LOCKOUT_HIGH",
            2: "LEP_SYS_SHUTTER_LOCKOUT_LOW",
        }
        return values.get(self.value, f"Unknown({self.value})")


class LEP_SYS_ENABLE_E(c_int):
    """System enable/disable enum"""
    LEP_SYS_DISABLE = 0
    LEP_SYS_ENABLE = 1
    LEP_END_SYS_ENABLE = 2

    def __str__(self):
        values = {
            0: "LEP_SYS_DISABLE",
            1: "LEP_SYS_ENABLE",
            2: "LEP_END_SYS_ENABLE",
        }
        return values.get(self.value, f"Unknown({self.value})")


class LEP_SYS_FFC_SHUTTER_MODE_OBJ_T(Structure):
    """Big struct for all FFC/shutter stuff"""
    _fields_ = [
        ("shutterMode", LEP_SYS_FFC_SHUTTER_MODE_E),
        ("tempLockoutState", LEP_SYS_SHUTTER_TEMP_LOCKOUT_STATE_E),
        ("videoFreezeDuringFFC", LEP_SYS_ENABLE_E),
        ("ffcDesired", LEP_SYS_ENABLE_E),
        ("elapsedTimeSinceLastFfc", c_uint32),
        ("desiredFfcPeriod", c_uint32),
        ("explicitCmdToOpen", c_bool),
        ("desiredFfcTempDelta", c_uint16),
        ("imminentDelay", c_uint16),
    ]

    def __str__(self):
        result = []
        for field_name, field_type in self._fields_:
            value = getattr(self, field_name)
            if isinstance(value, (LEP_SYS_FFC_SHUTTER_MODE_E, LEP_SYS_SHUTTER_TEMP_LOCKOUT_STATE_E, LEP_SYS_ENABLE_E)):
                result.append(f"{field_name}: {str(value)}")
            else:
                result.append(f"{field_name}: {value}")
        return "\n".join(result)
