# external imports
import os
import asyncpg
import logging
from logging.handlers import RotatingFileHandler


async def get_db_connection() -> asyncpg.Pool:
    """Connects to the PostgreSQL database"""
    user = os.environ['PostgreSQL user']
    password = os.environ['PostgreSQL password']
    database = os.environ['PostgreSQL database']
    host = os.environ['PostgreSQL host']

    credentials = {'user': user, 'password': password, 'database': database, 'host': host}

    return await asyncpg.create_pool(**credentials, command_timeout=60)


async def set_up_logger(name: str, level: int) -> logging.Logger:
    """Sets up a logger for this module"""
    # Discord logging guide: https://discordpy.readthedocs.io/en/latest/logging.html#logging-setup
    # Python's intro to logging: https://docs.python.org/3/howto/logging.html#logging-basic-tutorial
    # Documentation for RotatingFileHandler: https://docs.python.org/3/library/logging.handlers.html?#logging.handlers.RotatingFileHandler
    logger = logging.getLogger(name)
    logger.setLevel(level)
    max_bytes = 1024 * 1024  # 1 MiB
    handler = RotatingFileHandler(filename='bot.log', encoding='utf-8', mode='a', maxBytes=max_bytes, backupCount=1)
    formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
