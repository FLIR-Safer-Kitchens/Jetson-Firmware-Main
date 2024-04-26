# Add parent directory to the Python path
import os, sys
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', "src")))


from alarm_board.alarm_board import AlarmBoard
from misc.logs import configure_main
import logging


def main():
    # Configure logger
    configure_main(False, True)

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Connect to alarm board
    alarm = AlarmBoard()
    alarm.connect()

    try:
        # Test the connection
        assert alarm.ping(), "Serial communication failed"

        # User input loop
        while True:
            key = input("cmd: ")

            if key == 'q':
                raise KeyboardInterrupt
            elif key == 's':
                assert alarm.startAlarm()
            elif key == 'p':
                assert alarm.stopAlarm()
            elif key == 't':
                assert alarm.ping()
    
    except BaseException as err:
        alarm.disconnect()
        if type(err) != KeyboardInterrupt: raise


if __name__ == "__main__":
    main()