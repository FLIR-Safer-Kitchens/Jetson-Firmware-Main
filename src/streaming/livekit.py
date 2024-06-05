import asyncio
import logging
import socketio
import socket
import cv2
from signal import SIGINT, SIGTERM
from streaming.livekit import rtc
import numpy as np


# Globals for livekit
running = None
room = None
token = None
url = None


# Globals for frame reading
BUFF_SIZE = 65507 # Maximum UDP packet size
START_MARKER = b'\xFF\xD8' # JPEG start marker
END_MARKER   = b'\xFF\xD9' # JPEG end marker
TARGET_FRAME_PERIOD = 1.0/24 # Cap frame rate at 24 FPS

UDP_PORT = 12345
frame_task = None
frame_sock = None


# "Track" for incoming video
WIDTH, HEIGHT = 640, 480
source = rtc.VideoSource(WIDTH, HEIGHT)
track = rtc.LocalVideoTrack.create_video_track("webcam", source)
options = rtc.TrackPublishOptions()
options.source = rtc.TrackSource.SOURCE_CAMERA


# Initialize Socket.IO client
SOCKETIO_PORT = 3000
sio = socketio.AsyncClient()


async def read_from_sock():
    # Get newest UDP packet
    try:
        frame_data = None
        while True:
            frame_data = frame_sock.recvfrom(BUFF_SIZE)[0]
    except BlockingIOError:
        pass

    # Check if we got any frames
    if frame_data == None:
        return False, None

    if (START_MARKER in frame_data) and (END_MARKER in frame_data):
        # Get start and end of image
        start_idx = frame_data.index(START_MARKER)
        end_idx   = frame_data.index(END_MARKER) + len(END_MARKER)

        # Convert bytes to numpy array
        frame_bytes = np.frombuffer(frame_data[start_idx:end_idx], dtype=np.uint8)

        # Decode frame
        frame = cv2.imdecode(frame_bytes, flags=cv2.IMREAD_UNCHANGED)
        return type(frame) == np.ndarray, frame

    else: return None, False


# Reads frames from a UDP server and publishes them to the track
async def capture_frames():
    global frame_sock

    # Close UDP Socket
    if isinstance(frame_sock, socket.socket):
        frame_sock.close()
    
    # Create new socket instance
    frame_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    frame_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    frame_sock.setblocking(False)
    
    frame_sock.bind(("127.0.0.1", UDP_PORT))

    while True:
        start_time = asyncio.get_event_loop().time()

        # Read new frame data
        ret, frame = await read_from_sock()
        if not ret:
            continue
        
        # Publish frame data
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
        video_frame = rtc.VideoFrame(WIDTH, HEIGHT, rtc.VideoBufferType.BGRA, frame)
        source.capture_frame(video_frame)

        # Delay to achieve target frame rate
        dt = asyncio.get_event_loop().time() - start_time
        await asyncio.sleep(max(0, TARGET_FRAME_PERIOD - dt))


# Check and restart frame task if needed
async def frame_task_done_cb():
    global frame_task, frame_sock

    if frame_task.done():
        # Close UDP Socket
        if isinstance(frame_sock, socket.socket):
            frame_sock.close()
            frame_sock = None

        # Check if the task raised an exception
        try:
            frame_task.result()  
        except asyncio.CancelledError:
            logging.info("Frame task cancelled")
        except Exception as e:
            logging.error("Frame task raised an exception: %s", e)
        
        # Restart the task
        logging.info("Restarting frame capturing task")
        frame_task = asyncio.create_task(capture_frames())


# Join or rejoin a livekit room
async def join_room(new_token, new_url):
    global room, token, url

    # Check for redundant join requests
    if isinstance(room, rtc.Room) and room.isconnected():
        if (new_token == token) and (new_url == url):
            return

    # Create new room or disconnect from the current one
    if room is None: room = rtc.Room()
    await room.disconnect()

    # Try to connect to room
    try:
        logging.info("Connecting to %s", url)
        await room.connect(new_url, new_token)
        logging.info("Connected to room %s", room.name)
    except rtc.ConnectError as e:
        logging.error("Failed to connect to the room: %s", e)
        return
    
    # Publish track to room
    publication = await room.local_participant.publish_track(track, options)
    logging.info("Published track %s", publication.sid)


# On status message received from socketio server
@sio.event
async def status(data):
    global room, token, url

    # Parse data from the server
    stream_on = data.get("liveStreamOn")
    token     = data.get("liveStreamToken")
    url       = data.get("liveStreamURL")

    logging.info("Received URL and token from server")
    
    # Connect to the room
    if stream_on and token and url:
        await join_room(token, url)
 

async def main():
    global room
    
    # Create room object
    room = rtc.Room()

    # Start the task to capture frames
    frame_task = asyncio.create_task(capture_frames())
    frame_task.add_done_callback(frame_task_done_cb)

    # wait for Socket.IO events
    await sio.connect(f"http://localhost:{SOCKETIO_PORT}")
    await sio.wait()



if __name__ == "__main__":
    # Configure logger
    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.StreamHandler()],
    )

    # Create main event loop
    loop = asyncio.get_event_loop()

    async def cleanup():
        # Leave room
        if room: await room.disconnect()

        # Disconnect from client
        await sio.disconnect()

        # Stop frame task
        frame_task.cancel()
        try: await frame_task
        except asyncio.CancelledError: pass

        # Stop the main event loop
        loop.stop()

    # Add event handler for graceful shutdown
    for signal in [SIGINT, SIGTERM]:
        loop.add_signal_handler(signal, lambda: asyncio.ensure_future(cleanup()))

    # Run the main loop
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
