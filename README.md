# Jetson Nano Firmware

## Primary Functions:
- Control the system state
- Read thermal image data from the Lepton (on a [PureThermal carrier board](https://groupgets.com/products/purethermal-mini-pro-jst-sr))
- Detect whether cooking is occurring based of thermal image data
- Read visible image data from the IMX219 image sensor (on a [Arducam B0196 carrier board](https://www.arducam.com/product/b0196arducam-8mp-1080p-usb-camera-module-1-4-cmos-imx219-mini-uvc-usb2-0-webcam-board-with-1-64ft-0-5m-usb-cable-for-windows-linux-android-and-mac-os/))
- Detect the user's presence based on visible image data
- Interface with the Node.js server that communicates with the IOS app
- Interface with the camera module microcontroller to trigger the hardware alarm system

<br><hr>

## Initial Setup (on Jetson Nano)

### Install Dependencies
TODO

### Install libuvc
TODO

### Install Python Modules
TODO

### Set USB Permissions
TODO

### Build the TensorRT Engine
TODO

<br>

## Running the Firmware
TODO

<br><hr>

## Module Descriptions
The firmware consists of four primary modules: [arducam](#arducam), [lepton](#lepton), [cooking_detection](#cooking_detection), and [user_detection](#user_detection). Theses modules each contain "workers" which are python [multiprocessing](https://docs.python.org/3/library/multiprocessing.html) processes that can be started and stopped based on the system state. The outputs of these modules, in addition to the inputs from the app interface, are used by the state machine to determine the system state.

<br>

### arducam
The arducam module is used to continuously read frames from the visible camera. 

`polling.py` contains the class responsible for starting/stopping the worker process.

`polling_worker.py` contains the worker that reads from the arducam. The worker has two possible outputs for image data: a shared memory location used by the user detection process, and a UDP streaming output that can be used for debugging or live streaming.

<br>

### lepton
The lepton module contains all of the tools for polling the lepton and processing the thermal image data.

`polling_worker.py` contains the worker that reads from the purethermal carrier board. Similar to the Arducam, the lepton polling worker can output to both shared memory or UDP; however, the worker has additional outputs to indicate the hottest detected temperature and whether a hotspot is visible.

`polling.py` contains the class responsible for starting/stopping the worker process.

`uvc_stream.py` and `uvc_structs.py` implement the libuvc interface that allows the Jetson nano to connect to and read from the purethermal carrier board.

`win_drivers/` and `uvc_windows.py` facilitate camera polling on windows and are only intended for debugging use. 

`utils.py` implements low-level tools for processing thermal image data such as normalization, AGC, and raw-data-to-temperature conversion

`file_utils.py` contains tools for reading .tiff files and writing lepton video data to a file

<br>

### cooking_detection
The cooking detection module is responsible for detecting cooking based on thermal image data. The algorithm looks for regions of hot pixels, which we sometimes refer to as hotspots or blobs, and tracks their temperatures over time. Blobs that have a rising or constant temperature are likely being actively heated (i.e. associated with cooking).

`cooking_detect_worker.py` contains the worker that detects cooking from thermal image data. This includes finding blobs in the image, matching blobs between subsequent images, and evaluating temperature trends to identify cooking blobs. The output of the detection algorithm is a list of coordinates that correspond to the centroids of al cooking blobs. The apps uses these coordinates to inform the user which burners are being used for cooking.

`cooking_detect.py` contains the class responsible for starting/stopping the worker process.

`blob.py` contains the Blob class, which encapsulates a bunch of methods needed to process thermal hotspots (blobs)

`theil_sen.py` implements a [Theil-Sen slope estimator](https://en.wikipedia.org/wiki/Theil%E2%80%93Sen_estimator). The algorithm is used to evaluate temperature trends and was chosen for its robustness to outliers

<br>

### user_detection
The user detection algorithm is responsible for detecting if a user is present in the image.

`user_detection_worker.py` contains the worker that detects the user from visible image data using the [YOLOv7](https://docs.ultralytics.com/models/yolov7/) (or [YOLOv8](https://docs.ultralytics.com/models/yolov8/) on Windows) object detection model. The output of the worker is an epoch timestamp indicating the most recent time that the user was detected.

`user_detect.py` contains the class responsible for starting/stopping the worker process.

`trt_engine.py` implements a wrapper for the TensorRT engine, which performs the YOLOv7 inference on the Jetson nano's GPU. Adapted from [this repo](https://github.com/mailrocketsystems/JetsonYoloV7-TensorRT/blob/main/yoloDet.py).

`build_engine/` contains all of the files/scripts required to build the TensorRT engine. Copied from [this repo](https://github.com/mailrocketsystems/JetsonYoloV7-TensorRT). 

`yolov8n.pt` the model weights used to run YOLOv8 on Windows; this is only used for debugging.

<br>

### Other Modules (misc)

`alarm.py` handles serial communication with the microcontroller that controls the hardware alarms.

`frame_event.py` contains wrappers for [threading.Event](https://docs.python.org/3/library/threading.html#event-objects)s that create a parent-child hierarchy such that setting/clearing a parent affects all of its children, but setting/clearing a child only affects that object. This module is used for indicating when a new frame has been written to memory.

`hysteresis.py` contains a wrapper for a boolean value that applies time-based [hysteresis](https://en.wikipedia.org/wiki/Hysteresis) such that a the value must stay the same for a specified period of time to be read as that value.

`launcher.py` contains the parent class for all worker classes. The class has methods for starting/stopping a process, checking if a process is running, and handling errors generated by a process.

`logs.py` contains several classes and methods for dealing with logs. This includes configuring the logs for main and subprocesses. Additionally, the module contains classes to implement a queue system where workers can dump their log messages to be emitted in the main process.

`monitor.py` contains classes to stream, view, and record image data streamed over UDP. Recording and viewing are primarily used fr debugging; however, the MonitorServer class also helps to facilitate live streaming. 

`node_server.py` implements the interface with the node.js server that communicates with the app. This is done using a [socket.io](https://github.com/miguelgrinberg/python-socketio) client. The firmware is responsible for outputting the relevant detection outputs, and the node.js server is responsible for the alarm triggering logic and telling the firmware to start/stop the live stream.

<br><hr>

## Future Improvements
- Make the Theil-Sen estimator incremental rather than computing from scratch every time
- Have the arducam dewarping matrix flip the image upside down (or rotate 180) rather than doing it in a separate function call
- Implement a better lepton control interface to control FFC, set gain, read camera temperature, etc.
