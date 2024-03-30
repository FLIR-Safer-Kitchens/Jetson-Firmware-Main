"""Event wrapper to help manage several child events"""

from multiprocessing import Event

class BroadcastEvent():
    """
    Manages a list of child events\n
    Setting and clearing is performed on all children
    """

    def __init__(self):
        self.__children = []

    def get_child(self):
        """Returns (multiprocessing.Event): Child event belonging to this instance"""
        child = Event()
        self.__children.append(child)
        return child
    
    def set(self):
        """Sets all child events"""
        for ch in self.__children: ch.set()
    
    def clear(self):
        """Clears all child events"""
        for ch in self.__children: ch.clear()

