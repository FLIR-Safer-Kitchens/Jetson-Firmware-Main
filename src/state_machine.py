"""State machine for main process"""

from cooking_detection import CookingDetect
from lepton.polling import PureThermal
from user_detection import UserDetect
from constants import BLOB_MIN_TEMP
from arducam import Arducam
import logging
import time

# System states
STATE_RESET   = "Reset"
STATE_SETUP   = "Setup"
STATE_IDLE    = "Idle"
STATE_ACTIVE  = "Active"


class StateMachine:
    """State machine for main process"""

    def __init__( 
            self,
            arducam: Arducam, 
            arducam_args,
            purethermal: PureThermal, 
            purethermal_args,
            user_detect: UserDetect, 
            user_detect_args,
            cooking_detect: CookingDetect,
            cooking_detect_args
        ):
        """
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

        # Store launcher objects
        # Add an attribute for the worker's name
        # TODO: Not sure if it's good practice to add extra attributes like this, maybe add to Launcher?
        self.arducam      = arducam
        self.arducam.args = arducam_args
        self.arducam.name = "Arducam"

        self.purethermal      = purethermal
        self.purethermal.args = purethermal_args
        self.purethermal.name = "PureThermal"

        self.user_detect      = user_detect
        self.user_detect.args = user_detect_args
        self.user_detect.name = "User Detect"

        self.cooking_detect      = cooking_detect
        self.cooking_detect.args = cooking_detect_args
        self.cooking_detect.name = "Cooking Detect"

        # Bundle workers for easier iteration
        self.workers = (self.arducam, self.purethermal, self.user_detect, self.cooking_detect)

        # Initialize system state
        self.current_state = STATE_RESET
        self.alarm_active = False
        self.livestream_active = False

        # Helpful lambdas for checking conditions
        self.hotspots_detected    = lambda: self.purethermal.hotspot_detected.value
        self.valid_blobs_detected = lambda: self.cooking_detect.blobs_detected.value
        self.cooking_detected     = lambda: self.cooking_detect.cooking_detected.value
        self.unattended           = lambda: (time.time() - self.user_detect.last_detected.value) > 60*1 # 1 minute

        # Add an attribute to indicate when a worker should be on
        self.arducam.on_condition        = lambda: self.current_state == STATE_ACTIVE
        self.purethermal.on_condition    = lambda: self.current_state != STATE_RESET or self.livestream_active
        self.user_detect.on_condition    = lambda: self.current_state == STATE_ACTIVE
        self.cooking_detect.on_condition = lambda: self.current_state == STATE_ACTIVE


    def __set_state(self, next_state):
        """
        Set the current state. Start/stop necessary launchers.\n
        Parameters:
        - next_state (int): State index (StateMachine.STATE_x)
        """
        # Debug message
        if next_state == self.current_state: return # No change
        else: self.logger.info(f"State Change: {self.current_state} --> {next_state})")

        # Set state
        self.current_state = next_state

        # Start/stop workers
        for worker in self.workers:
            # Start worker
            if worker.on_condition():
                if not worker.running(): 
                    worker.start(*worker.args)

            # Stop worker
            elif worker.running():
                worker.stop()
        

    def __check_workers(self):
        """
        Check if workers encountered any errors. Restart them if possible\n
        Returns (bool): False for critical error, no recovery possible.
        """

        for worker in self.workers:
            # Worker active when it should not be
            if worker.running() and not worker.on_condition():
                self.logger.warning(f"{worker.name} was running in {self.current_state} state. Shuting down")
                worker.stop()
                if not self.purethermal.handle_exceptions(): return False

            # Worker not active when it should be
            elif not worker.running() and worker.on_condition():
                self.logger.warning(f"{worker.name} process died unexpectedly")

                # Attempt restart
                if worker.handle_exceptions():
                    worker.start(*worker.args)
                else: return False

        return True


    def update(self):
        """
        Update the system state\n
        Returns (bool): False if a fatal error occurred
        """
        # Startup (No state, No running workers)
        if self.current_state == STATE_RESET:
            # TODO: check for wifi
            # Transition to setup state if not set up
            if False:
                self.__set_state(STATE_SETUP)

            # Start lepton polling process if system has been configured
            else:
                print('sdfj')
                self.__set_state(STATE_IDLE)
        
        # Setup state
        elif self.current_state == STATE_SETUP:
            # Start polling purethermal
            # Wait for user to request livestream and start/stop transcoder
            # After setup is complete, go to idle
            self.__set_state(STATE_IDLE)

        # Idle state (no hotspots detected)
        elif self.current_state == STATE_IDLE:
            # TODO: report max temperature to node.js

            # Hotspot detected --> system active
            if self.hotspots_detected():
                self.__set_state(STATE_ACTIVE)
        
        # Active state (Hotspots detected, cooking/user detection active)
        elif self.current_state == STATE_ACTIVE:
            # No hotspots detected --> back to idle
            if not self.hotspots_detected():
                self.__set_state(STATE_IDLE)

            # Check if there are any valid blobs (may or may not be cooking)
            # We will only enable the user detection algorithm when a valid blob exists
            self.user_detect.args[2].enabled = self.valid_blobs_detected()

            # TODO: Report to node.js. Receive alarm state

            # ************************************************************
            # Alarm logic (will be handled by node server later)
            # Simple timer for now
            if not self.alarm_active:
                if self.cooking_detected() and self.unattended():
                    self.logger.info("\n******************\nALARM TRIGGERED\n******************")
            # ************************************************************
            
            # User returned --> Clear alarm and return to idle
            elif not self.unattended():
                self.logger.info("Alarm cleared")
                self.__set_state(STATE_IDLE)
        
        else:
            self.logger.warning(f"Unrecognized current state: {self.current_state}")
            return False

        # Check running workers
        return self.__check_workers()
