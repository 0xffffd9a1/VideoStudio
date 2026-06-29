import logging
import os

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "videostudio.log")

def setup_logger(name: str = "VideoStudio"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Файловый обработчик
    fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    # Консольный обработчик
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

# Общий логгер для всего проекта
logger = setup_logger()