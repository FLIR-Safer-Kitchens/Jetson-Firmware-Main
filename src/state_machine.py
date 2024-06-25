"""State machine for main process"""

from constants import STREAM_TYPE_THERMAL, STREAM_TYPE_VISIBLE, STREAM_UDP_PORT
from misc.node_server import NodeServer
from misc.launcher import Launcher
from misc.alarm import AlarmBoard
import logging
import time

# System states
STATE_SETUP   = "Setup"
STATE_IDLE    = "Idle"
STATE_ACTIVE  = "Active"
STATE_ALARM   = "Alarm"


class WorkerProcess:
    """Wrapper for worker proceses"""

    def __init__(self, name, launcher: Launcher, start_args):
        # Save worker info
        self.name = name
        self.launcher = launcher
        self.start_args = start_args

        # Lambda to indicate when the worker should be active
        self.on_condition = lambda: False

        # Expose launcher functions
        self.running = self.launcher.running
        self.streaming_ports = self.launcher.streaming_ports
        self.handle_exceptions = self.launcher.handle_exceptions

    def start(self):
        self.launcher.start(*self.start_args)

    def stop(self, check_exceptions=False):
        self.launcher.stop()
        if check_exceptions:
            return self.launcher.handle_exceptions()
        else:
            return True



class StateMachine:
    """State machine for main process"""

    def __init__( 
            self,
            node_server:    NodeServer,  
            alarm_board:    AlarmBoard,
            arducam:        WorkerProcess,
            purethermal:    WorkerProcess, 
            user_detect:    WorkerProcess, 
            cooking_detect: WorkerProcess
        ):
        """
        Parameters:
        - node_server (NodeServer): The node.js server object  
        - alarm_board (AlarmBoard): The alarm board server object
        - arducam (WorkerProcess): Arducam polling launcher and args
        - purethermal (WorkerProcess): Purethermal polling launcher and args
        - user_detect (WorkerProcess): User detection launcher and args
        - cooking_detect (WorkerProcess): Cooking detection launcher and args
        """

        # Get logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
    
        # Store node server object
        self.node_server = node_server

        # Store alarm board
        self.alarm_board = alarm_board

        # Store worker process objects
        self.arducam = arducam
        self.purethermal = purethermal
        self.user_detect = user_detect
        self.cooking_detect = cooking_detect

        # Bundle workers for easier iteration
        self.workers = (
            self.arducam, 
            self.purethermal, 
            self.user_detect, 
            self.cooking_detect
        )

        # Initialize system state
        self.current_state = STATE_SETUP
        self.livestream_active = False
        self.livestream_type = ""

        # Macro for pausing user detection
        self.user_detection_enabled = self.user_detect.start_args[1].enabled

        # Helpful lambdas for getting process outputs
        self.hotspots_detected    = lambda: self.purethermal.launcher.hotspot_detected.value
        self.max_temp             = lambda: self.purethermal.launcher.max_temp.value
        self.cooking_coords       = lambda: self.cooking_detect.launcher.cooking_coords[:]
        self.unattended_time      = lambda: (time.time() - self.user_detect.launcher.last_detected.value)

        # Lambdas to check whether a worker should be on
        self.arducam.on_condition        = lambda: self.current_state in {STATE_ACTIVE, STATE_ALARM} or (self.livestream_active and self.livestream_type == STREAM_TYPE_VISIBLE)
        self.purethermal.on_condition    = lambda: self.current_state != STATE_SETUP or (self.livestream_active and self.livestream_type == STREAM_TYPE_THERMAL)
        self.user_detect.on_condition    = lambda: self.current_state != STATE_SETUP
        self.cooking_detect.on_condition = lambda: self.current_state == STATE_ACTIVE or self.current_state == STATE_ALARM


    def _set_state(self, next_state):
        """
        Set the current state. Start/stop necessary launchers

        Parameters:
        - next_state (int): State index (StateMachine.STATE_x)
        """
        # Debug message
        if next_state == self.current_state: return # No change
        else: self.logger.info(f"State Change: {self.current_state} --> {next_state})")

        # Setup state (Device not configured)
        if self.current_state == STATE_SETUP:
            # Start lepton and load user detection model
            if next_state == STATE_IDLE:
                if self.livestream_active and self.livestream_type == STREAM_TYPE_THERMAL:
                    self.purethermal.start()

                # Start user detection but disable it
                self.user_detection_enabled = False
                self.user_detect.start()

            # Unrecognized transition
            else: self.logger.error("Unrecognized state transition")

        # Idle state (Device configured, No hotspots detected)
        elif self.current_state == STATE_IDLE:
            # Shut down lepton and user detection model
            if next_state == STATE_SETUP:
                if not (self.livestream_active and self.livestream_type == STREAM_TYPE_THERMAL):
                    self.purethermal.stop()
                self.user_detect.stop()

            # Start arducam, enable user detection, start cooking detection
            elif next_state == STATE_ACTIVE:
                self.arducam.start()
                self.user_detection_enabled = True
                self.cooking_detect.start()

            # Unrecognized transition
            else: self.logger.error("Unrecognized state transition")

        # Active state (Device configured, Hotspots detected)
        elif self.current_state == STATE_ACTIVE:
            # Shut down lepton, cooking detection, arducam, user detection
            if next_state == STATE_SETUP:
                self.cooking_detect.stop()
                self.user_detect.stop()
                if not (self.livestream_active and self.livestream_type == STREAM_TYPE_THERMAL):
                    self.purethermal.stop()
                if not (self.livestream_active and self.livestream_type == STREAM_TYPE_VISIBLE):
                    self.arducam.stop()

            # Leave everything running
            elif next_state == STATE_ALARM:
                self.alarm_board.startAlarm()

            # Disable user detection, shut down arducam and cooking detection
            elif next_state == STATE_IDLE:
                self.cooking_detect.stop()
                self.user_detection_enabled = False
                if not (self.livestream_active and self.livestream_type == STREAM_TYPE_VISIBLE):
                    self.arducam.stop()

            # Unrecognized transition
            else: self.logger.error("Unrecognized state transition")
            
        # Alarm state (Device configured, Alarm active)
        elif self.current_state == STATE_ALARM:
            # Shut down lepton, cooking detection, arducam, user detection
            if next_state == STATE_SETUP:
                self.alarm_board.stopAlarm()
                self.cooking_detect.stop()
                self.user_detect.stop()
                if not (self.livestream_active and self.livestream_type == STREAM_TYPE_THERMAL):
                    self.purethermal.stop()
                if not (self.livestream_active and self.livestream_type == STREAM_TYPE_VISIBLE):
                    self.arducam.stop()

            # Disable user detection, shut down arducam and cooking detection
            elif next_state == STATE_IDLE:
                self.alarm_board.stopAlarm()
                self.cooking_detect.stop()
                self.user_detection_enabled = False
                if not (self.livestream_active and self.livestream_type == STREAM_TYPE_VISIBLE):
                    self.arducam.stop()

            # Unrecognized transition
            else: self.logger.error("Unrecognized state transition")

        # Set current state
        self.current_state = next_state


    def _check_workers(self):
        """
        Check if workers encountered any errors. Restart them if possible

        Returns (bool): False for critical error, no recovery possible.
        """

        for worker in self.workers:
            # Worker active when it should not be
            if worker.running() and not worker.on_condition():
                self.logger.warning(f"{worker.name} was running in {self.current_state} state. Shuting down")
                
                if not worker.stop(check_exceptions=True):
                    return False

            # Worker not active when it should be
            elif not worker.running() and worker.on_condition():
                self.logger.warning(f"{worker.name} process died unexpectedly")

                # Attempt restart
                if worker.handle_exceptions():
                    worker.start()
                else: return False

        return True


    def update(self):
        """
        Update the system state

        Returns (bool): False if a fatal error occurred
        """

        # === Report Status to Node.js ===
        self.node_server.send_status(
            cooking_coords = self.cooking_coords(),
            max_temp = self.max_temp(),
            unattended_time=self.unattended_time()
        )

        # === Handle Livestream ===
        # Check if user has requested the livestream
        on_prev = self.livestream_active
        self.livestream_active = self.node_server.livestream_on

        # Start livestream
        if self.livestream_active and not on_prev:
            # Check the requested stream type
            self.livestream_type = self.node_server.livestream_type

            # Thermal
            if self.livestream_type == STREAM_TYPE_THERMAL:
                if self.current_state == STATE_SETUP:
                    self.purethermal.start()
                self.purethermal.streaming_ports.append(STREAM_UDP_PORT)
           
            # Visible
            elif self.livestream_type == STREAM_TYPE_VISIBLE:
                if self.current_state not in {STATE_ACTIVE, STATE_ALARM}:
                    self.arducam.start()
                self.arducam.streaming_ports.append(STREAM_UDP_PORT)

        # Stop livestream
        elif not self.livestream_active and on_prev:
            # Thermal
            if self.livestream_type == STREAM_TYPE_THERMAL:
                if self.current_state == STATE_SETUP:
                    if not self.purethermal.stop(check_exceptions=True):
                        return False
                
                idx = self.purethermal.streaming_ports.index(STREAM_UDP_PORT)
                self.purethermal.streaming_ports.pop(idx)
            
            # Visible
            elif self.livestream_type == STREAM_TYPE_VISIBLE:
                if self.current_state not in {STATE_ACTIVE, STATE_ALARM}:
                    if not self.arducam.stop(check_exceptions=True):
                        return False
                
                idx = self.arducam.streaming_ports.index(STREAM_UDP_PORT)
                self.arducam.streaming_ports.pop(idx)

        # === Handle State Transitions ===
        # Setup state (Device not configured)
        if self.current_state == STATE_SETUP:
            # Wait for the node.js server to tell us that the device has been configured
            if self.node_server.configured:
                self._set_state(STATE_IDLE)

        # Idle state (Device configured, No hotspots detected)
        elif self.current_state == STATE_IDLE:
            # System needs to be reconfigured --> setup state
            if not self.node_server.configured:
                self._set_state(STATE_SETUP)

            # Hotspot detected --> system active
            elif self.hotspots_detected():
                self._set_state(STATE_ACTIVE)

        # Active state (Device configured, Hotspots detected)
        elif self.current_state == STATE_ACTIVE:
            # System needs to be reconfigured --> setup state
            if not self.node_server.configured:
                self._set_state(STATE_SETUP)

            # Alarm activated --> enter alarm state
            elif self.node_server.alarm_on:
                self._set_state(STATE_ALARM)

            # No hotspots detected --> back to idle
            elif not self.hotspots_detected():
                self._set_state(STATE_IDLE)

        # Alarm state (Device configured, Alarm active)
        elif self.current_state == STATE_ALARM:
            # System needs to be reconfigured --> setup state
            if not self.node_server.configured:
                self._set_state(STATE_SETUP)

            # Alarm turned off, go back to idle
            elif not self.node_server.alarm_on:
                self._set_state(STATE_IDLE)

        # Just in case the state gets screwed up
        else: 
            self.logger.error(f"Unrecognized state: {self.current_state}")
            return False

        # Check running workers
        return self._check_workers()
