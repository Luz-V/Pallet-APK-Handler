# Colored handler
import logging
import colorlog

########### LOG LEVEL ###########
logging.root.setLevel(logging.DEBUG)

# Define ANSI color
GRAY = '\033[90m'
RESET = '\033[0m'

# handler colors
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    fmt=f'{GRAY}[%(asctime)s]{RESET} : [%(log_color)s%(bold)s%(levelname)s{RESET}] '
        f'PAH | {GRAY}%(funcName)s(){RESET} | %(message)s',
    datefmt='%H:%M:%S',
    log_colors={
        'DEBUG':    'cyan',
        'INFO':     'green',
        'WARNING':  'yellow',
        'ERROR':    'red',
        'CRITICAL': 'bold_red',
    },
    style='%'
))

# Setup
logging.root.handlers = []
logging.root.addHandler(handler)


