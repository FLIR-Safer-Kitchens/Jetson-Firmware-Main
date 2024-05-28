"""State machine for main process"""

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
            cooking_detect: WorkerProcess,
            livestream:     WorkerProcess
        ):
        """

        TODO: UPDATE

        Parameters:
        - arducam (arducam.Arducam): Arducam polling launcher
        - arducam_args (tuple): Arguments to pass to the launcher's start() method
        - purethermal (lepton.polling.PureThermal): Purethermal polling launcher
        - purethermal_args (tuple): Arguments to pass to the launcher's start() method
        - user_detect (user_detection.UserDetect): User detection launcher
        - user_detect_args (tuple): Arguments to pass to the launcher's start() method
        - cooking_detect (cooking_detection.CookingDetect): Cooking detection launcher
        - cooking_detect_args (tuple): Arguments to pass to the launcher's start() method
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
        self.livestream = livestream

        # Bundle workers for easier iteration
        self.workers = (
            self.arducam, 
            self.purethermal, 
            self.user_detect, 
            self.cooking_detect, 
            self.livestream
        )

        # Initialize system state
        self.current_state = STATE_SETUP
        self.livestream_active = False

        # Macro for pausing user detection
        # TODO: Does this work lol
        self.user_detection_enabled = self.user_detect.start_args[1].enabled

        # Helpful lambdas for getting process outputs
        self.hotspots_detected    = lambda: self.purethermal.launcher.hotspot_detected.value
        self.max_temp             = lambda: self.purethermal.launcher.max_temp.value
        self.cooking_coords       = lambda: self.cooking_detect.launcher.cooking_coords[:]
        self.unattended_time      = lambda: (time.time() - self.user_detect.launcher.last_detected.value)

        # Add an attribute to indicate when a worker should be on
        self.arducam.on_condition        = lambda: self.current_state == STATE_ACTIVE or self.current_state == STATE_ALARM
        self.purethermal.on_condition    = lambda: self.current_state != STATE_SETUP or self.livestream_active
        self.user_detect.on_condition    = lambda: self.current_state != STATE_SETUP
        self.cooking_detect.on_condition = lambda: self.current_state == STATE_ACTIVE or self.current_state == STATE_ALARM
        self.livestream.on_condition     = lambda: self.livestream_active


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
                if not self.purethermal.running():
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
                self.purethermal.stop()
                self.arducam.stop()

            # Leave everything running
            elif next_state == STATE_ALARM:
                self.alarm_board.startAlarm()

            # Disable user detection, shut down arducam and cooking detection
            elif next_state == STATE_IDLE:
                self.cooking_detect.stop()
                self.user_detection_enabled = False
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
                self.purethermal.stop()
                self.arducam.stop()

            # Disable user detection, shut down arducam and cooking detection
            elif next_state == STATE_IDLE:
                self.alarm_board.stopAlarm()
                self.cooking_detect.stop()
                self.user_detection_enabled = False
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
        m3u8_path = self.livestream.launcher.m3u8_path if self.livestream_active else None
        self.node_server.send_status(
            cooking_coords = self.cooking_coords(),
            max_temp = self.max_temp(),
            unattended_time=self.unattended_time(),
            m3u8_path=m3u8_path
        )

        # === Handle Livestream ===
        # Check if user has requested the livestream
        prev = self.livestream_active
        self.livestream_active = self.node_server.livestream_on

        # Start livestream
        if self.livestream_active and not prev:
            if self.current_state == STATE_SETUP:
                self.purethermal.start()
            self.livestream.start()

        # Stop livestream
        elif not self.livestream_active and prev:
            if not self.livestream.stop(check_exceptions=True):
                return False
            
            if self.current_state == STATE_SETUP:
                if not self.purethermal.stop(check_exceptions=True):
                    return False
        
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
