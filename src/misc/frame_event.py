"""Event wrappers to help manage several child events"""

from multiprocessing.synchronize import Event
from multiprocessing import get_context

class NewFrameEvent():
    """
    Manages a list of child events.

    Setting and clearing is performed on all children
    """

    def __init__(self):
        self.__children = []

    def get_child(self):
        """Returns (NewFrameConsumer): Child event belonging to this instance"""
        child = NewFrameConsumer()
        self.__children.append(child)
        return child

    def set(self):
        """Sets all child events"""
        for ch in self.__children: ch.set()

    def clear(self):
        """Clears all child events"""
        for ch in self.__children: ch.clear()


class NewFrameConsumer(Event):
    """
    Wrapper for multiprocessing.Event that allows the Event to be enabled/disabled.

    'enabled' property can be used to 'pause' a worker process that consumes video data
    """

    def __init__(self) -> None:
        super().__init__(ctx=get_context())
        self._enabled = True

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        
        # Lower flag when disabled
        if value == False: 
            super().clear()

    def set(self):
        # Only allows set() to take effect when enabled
        if self.enabled: super().set()
