from signal import SIGINT, SIGTERM
import socketio.exceptions
from livekit import rtc
import numpy as np
import socketio
import asyncio
import logging
import socket
import cv2


# Globals for livekit
running = None
room = None
token = None
url = None

# Create RTC "Track" for incoming video
WIDTH, HEIGHT = 640, 480
source = rtc.VideoSource(WIDTH, HEIGHT)
track  = rtc.LocalVideoTrack.create_video_track("webcam", source)
options = rtc.TrackPublishOptions()
options.source = rtc.TrackSource.SOURCE_CAMERA


# Globals for frame reading
BUFF_SIZE = 65507 # Maximum UDP packet size
START_MARKER = b'\xFF\xD8' # JPEG start marker
END_MARKER   = b'\xFF\xD9' # JPEG end marker

IN_FRAME_PERIOD  = 1.0/30 # Maximum frame period of incoming frame data
OUT_FRAME_PERIOD = 1.0/24 # Cap frame rate

UDP_PORT = 12345
frame_task = None
frame_sock = None

# Initialize Socket.IO client
SOCKETIO_PORT = 3000
sio = socketio.AsyncClient()


async def read_from_sock(sock):
    """
    Read the latest frame from the UDP socket

    Parameters:
    - sock (socket.socket): Socket to read from

    Returns (tuple): Boolean data-valid flag, then the image data (numpy.ndarray), if valid
    """
    # Get newest UDP packet
    frame_data = None
    try:
        coro = asyncio.get_event_loop().sock_recv(sock, BUFF_SIZE)
        frame_data = await asyncio.wait_for(coro, timeout=0.5*IN_FRAME_PERIOD)
    
    # No data available within timeout
    except asyncio.TimeoutError: pass  
    except:
        logging.exception("Error while reading frames:\n")
        return False, None

    # Check if the frame data is in proper JPEG format
    if (type(frame_data) == bytes) and (START_MARKER in frame_data) and (END_MARKER in frame_data):
        
        # Get start and end of image
        start_idx = frame_data.index(START_MARKER)
        end_idx   = frame_data.index(END_MARKER) + len(END_MARKER)

        # Convert bytes to numpy array
        frame_bytes = np.frombuffer(frame_data[start_idx:end_idx], dtype=np.uint8)

        # Decode frame
        frame = cv2.imdecode(frame_bytes, flags=cv2.IMREAD_COLOR)
        return type(frame) == np.ndarray, frame

    else: return False, None


# Reads frames from a UDP server and publishes them to the track
async def capture_frames():
    """Coroutine to read frames from the UDP socket and publish them to the RTC track"""
    global frame_sock

    # Close existing UDP Socket
    if isinstance(frame_sock, socket.socket):
        frame_sock.close()
    
    # Create new socket instance
    frame_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    frame_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    frame_sock.setblocking(False)
    frame_sock.bind(("127.0.0.1", UDP_PORT))
    logging.info(f"Ready to receive frame on port {UDP_PORT}")

    while True:
        start_time = asyncio.get_event_loop().time()

        # Read new frame data
        ret, frame = await read_from_sock(frame_sock)
        if ret:
            # Publish frame data
            frame = cv2.resize(frame, (WIDTH, HEIGHT))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
            video_frame = rtc.VideoFrame(WIDTH, HEIGHT, rtc.VideoBufferType.BGRA, frame)
            source.capture_frame(video_frame)

        # Delay to achieve target frame rate
        dt = asyncio.get_event_loop().time() - start_time
        await asyncio.sleep(max(0, OUT_FRAME_PERIOD - dt))


async def join_room(new_token, new_url):
    """
    Join or rejoin a livekit room
    
    Parameters:
    - new_token (str): The latest auth token sent by the server
    - new_url (url): The latest livekit URL sent by the server
    """
    global room, token, url

    # Check for redundant join requests
    if isinstance(room, rtc.Room) and room.isconnected():
        if (new_token == token) and (new_url == url):
            logging.debug("Already connected to requested room")
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
    else:
        token = new_token
        url   = new_url
    
    # Publish track to room
    publication = await room.local_participant.publish_track(track, options)
    logging.info("Published track %s", publication.sid)


@sio.event
async def status(data):
    """Callback for handling status events from the soketio server"""
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
    global room, frame_task, frame_sock
    
    # Create room object
    room = rtc.Room()

    # Start the task to capture frames
    # TODO: Need to make sure this gets restarted if it dies
    frame_task = asyncio.ensure_future(capture_frames())

    # Wait for Socket.IO events
    while True:
        try:
            await sio.connect(f"http://127.0.0.1:{SOCKETIO_PORT}")
            logging.info("Connected to Socket.IO server")
            break
        except socketio.exceptions.ConnectionError as e:
            logging.error(f"Failed to connect to Socket.IO server:\n{e}\nRetrying...")
            await asyncio.sleep(1)  # Wait for 1 second before retrying

    await sio.wait()


if __name__ == "__main__":
    # Configure logger
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

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
