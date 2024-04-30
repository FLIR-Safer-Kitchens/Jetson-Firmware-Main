"""A class for imposing time-based hysteresis on a boolean value"""

import time

class HysteresisBool():
    """A class for imposing time-based hysteresis on a boolean value"""

    def __init__(self, trip_time, release_time, initial=False):
        """
        Parameters:
        - trip_time (float): Duration in seconds that a True value must be sustained in order to latch
        - release_time (float): Duration in seconds that a False value must be sustained in order to latch
        - initial (bool): Initial value of the latched value. Default is False
        """
        self._latched_value = initial
        self._current_value = initial

        # Save trip/release time
        self._t_trip    = trip_time
        self._t_release = release_time
        
        # Timestamp of last current-value change
        self._change_ts = time.time()

    @property
    def value(self):
        return self._latched_value
    
    @value.setter
    def value(self, new):
        # Change current value and reset change timestamp
        if new != self._current_value:
            self._current_value = new
            self._change_ts = time.time()

        # Time since last change
        current_period = time.time() - self._change_ts
        
        # If the current value has not changed for a sufficently long time, latch it
        if self._current_value and current_period > self._t_trip:
            self._latched_value = True # Trip
        
        elif not self._current_value and current_period > self._t_release:
            self._latched_value = False # Release
