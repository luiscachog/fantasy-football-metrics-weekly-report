import logging
import logging.handlers as handlers
import os
import re
import sys
import time
from configparser import NoSectionError

# from logging.handlers import RotatingFileHandler
from logging.handlers import TimedRotatingFileHandler

import colorama
from colorama import Fore, Style

from utils.app_config_parser import AppConfigParser

colorama.init()

config = AppConfigParser()
config.read(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.ini")
)


class StyledFormatter(logging.Formatter):
    def __init__(self, msg):
        logging.Formatter.__init__(self, msg)

    def format(self, record):

        record.name = "{0}{1}{2}".format(
            Fore.RESET, record.name, Style.RESET_ALL
        )

        log_level = record.levelname
        if log_level == "DEBUG":
            record.levelname = "{0}{1}{2}".format(
                Fore.MAGENTA, log_level, Style.RESET_ALL
            )
            record.message = "{0}{1}{2}".format(
                Fore.MAGENTA, record.getMessage(), Style.RESET_ALL
            )
        elif log_level == "INFO":
            record.levelname = "{0}{1}{2}".format(
                Fore.WHITE, log_level, Style.RESET_ALL
            )
            record.message = "{0}{1}{2}".format(
                Fore.WHITE, record.getMessage(), Style.RESET_ALL
            )
        elif log_level == "WARNING":
            record.levelname = "{0}{1}{2}".format(
                Fore.YELLOW, log_level, Style.RESET_ALL
            )
            record.message = "{0}{1}{2}".format(
                Fore.YELLOW, record.getMessage(), Style.RESET_ALL
            )
        elif log_level == "ERROR":
            record.levelname = "{0}{1}{2}".format(
                Fore.RED, log_level, Style.RESET_ALL
            )
            record.message = "{0}{1}{2}".format(
                Fore.RED, record.getMessage(), Style.RESET_ALL
            )
        elif log_level == "CRITICAL":
            record.levelname = "{0}{1}{2}".format(
                Fore.RED, log_level, Style.RESET_ALL
            )
            record.message = "{0}{1}{2}".format(
                Fore.RED, record.getMessage(), Style.RESET_ALL
            )
        else:
            record.message = record.getMessage()

        # noinspection PyUnresolvedReferences
        if self.usesTime():
            record.asctime = "{0}{1}{2}".format(
                Fore.RESET,
                self.formatTime(record, self.datefmt),
                Style.RESET_ALL,
            )
        s = self.formatMessage(record)
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + record.exc_text
        if record.stack_info:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + self.formatStack(record.stack_info)

        return s


# class taken from stackoverflow: https://stackoverflow.com/a/8468041
# noinspection PyPep8Naming,PyUnresolvedReferences
class SizedTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    Handler for logging to a set of files, which switches from one file
    to the next when the current file reaches a certain size, or at certain
    timed intervals
    """

    def __init__(
        self,
        filename,
        maxBytes=0,
        backupCount=0,
        encoding=None,
        delay=0,
        when="h",
        interval=1,
        utc=False,
    ):
        handlers.TimedRotatingFileHandler.__init__(
            self, filename, when, interval, backupCount, encoding, delay, utc
        )
        self.maxBytes = maxBytes
        self.stream = None

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, see if the supplied record would cause the file to exceed
        the size limit we have.
        """
        if self.stream is None:  # delay was set...
            self.stream = self._open()
        if self.maxBytes > 0:  # are we rolling over?
            msg = "%s\n" % self.format(record)
            # due to non-posix-compliant Windows feature
            self.stream.seek(0, 2)
            if self.stream.tell() + len(msg) >= self.maxBytes:
                return 1
        t = int(time.time())
        if t >= self.rolloverAt:
            return 1
        return 0

    # noinspection PyBroadException
    def emit(self, record):
        try:
            if self.shouldRollover(record):
                self.doRollover()

            if self.stream is None:
                self.stream = self._open()

            try:
                ansi_escape = re.compile(
                    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
                )
                msg = ansi_escape.sub("", self.format(record))
                stream = self.stream
                # issue 35046: merged two stream.writes into one.
                stream.write(msg + self.terminator)
                self.flush()
            except RecursionError:  # See issue 36272
                raise
            except Exception:
                self.handleError(record)

        except Exception:
            self.handleError(record)


def get_logger(module_name=None, propagate=True):

    log_level_mapping = {
        "info": logging.INFO,
        "debug": logging.DEBUG,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    try:
        log_level = log_level_mapping[config.get("Configuration", "log_level")]
    except (KeyError, NoSectionError):
        log_level = logging.INFO

    log_file_dir = "logs"
    log_file_name = "out.log"
    log_file = os.path.join(log_file_dir, log_file_name)

    if not os.path.exists(log_file_dir):
        os.makedirs(log_file_dir)

    log_formatter = StyledFormatter(
        "%(asctime)s {0}-{1} %(name)s {0}-{1} %(levelname)s {0}-{1} %(message)s".format(
            Fore.RESET, Style.RESET_ALL
        )
    )

    sh = logging.StreamHandler(stream=sys.stderr)
    sh.setLevel(log_level)
    sh.setFormatter(log_formatter)

    # 10*1024*1024 = 10mb
    # 1*1024*1024 = 1mb

    # # rotate logs WITHOUT timed rotation
    # rfh = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)

    # rotate logs WITH timed rotation
    rfh = SizedTimedRotatingFileHandler(
        log_file,
        when="h",
        interval=1,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        # encoding='bz2'  # uncomment for bz2 compression
    )

    rfh.setLevel(logging.DEBUG)
    rfh.setFormatter(log_formatter)

    if module_name:
        logger = logging.getLogger(module_name)
    else:
        logger = logging.getLogger()

    if logger.hasHandlers():
        logger.handlers = []

    logger.setLevel(logging.DEBUG)
    logger.addHandler(sh)
    logger.addHandler(rfh)

    if not propagate:
        logger.propagate = False

    return logger


if __name__ == "__main__":

    log_filename = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "logs", "out.log"
    )
    test_logger = get_logger(__name__)
    test_logger.setLevel(logging.DEBUG)
    handler = SizedTimedRotatingFileHandler(
        log_filename,
        when="s",  # s = seconds, m = minutes, h = hours, midnight = at midnight, etc.
        interval=3,  # how many increments of the "when" configuration to wait before creating next log file
        maxBytes=100,
        backupCount=5,
        # encoding='bz2',  # uncomment for bz2 compression
    )
    test_logger.addHandler(handler)
    for i in range(100):
        time.sleep(0.1)
        test_logger.debug("i=%d" % i)
