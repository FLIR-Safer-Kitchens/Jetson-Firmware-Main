"""Test for alarm board MCU communication"""

# Add parent directory to the Python path
import os, sys
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', "src")))

from misc.logs import configure_main_log
import logging

from misc.alarm import AlarmBoard
# from stubs import AlarmBoard


def main():
    # Configure logger
    configure_main_log(False, True)

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Connect to alarm board
    alarm = AlarmBoard()
    alarm.connect()

    try:
        # User input loop
        while True:
            key = input("cmd: ")

            if key == 'q':
                raise KeyboardInterrupt
            elif key == 's':
                assert alarm.startAlarm()
            elif key == 'p':
                assert alarm.stopAlarm()
    
    except KeyboardInterrupt: pass
    except:
        logger.exception("")
    finally:
        alarm.disconnect()


if __name__ == "__main__":
    main()
