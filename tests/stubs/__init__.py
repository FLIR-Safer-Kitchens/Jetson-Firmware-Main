"""
    Import these modules instead of the real ones 
    if you don't have the necessary hardware
    or want to test a module independently
"""

from .launcher import Launcher
from .alarm import AlarmBoard
from .arducam import Arducam
from .cooking_detection import CookingDetect
from .lepton import PureThermal
from .node_server import NodeServer
from .transcoder import Transcoder
from .user_detection import UserDetect
