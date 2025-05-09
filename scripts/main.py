import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta

import schedule
from const import *
from data_fetcher import DataFetcher


def main():
    global RETRY_TIMES_LIMIT

    if "PYTHON_IN_DOCKER" not in os.environ:
        # 读取 .env 文件
        import dotenv

        dotenv.load_dotenv(verbose=True)
    if os.path.isfile("/data/options.json"):
        with open("/data/options.json") as f:
            options = json.load(f)
        try:
            PHONE_NUMBER = options.get("PHONE_NUMBER")
            PASSWORD = options.get("PASSWORD")
            JOB_START_TIME = options.get("JOB_START_TIME", "07:00")
            LOG_LEVEL = options.get("LOG_LEVEL", "INFO")
            RETRY_TIMES_LIMIT = int(options.get("RETRY_TIMES_LIMIT", 5))

            logger_init(LOG_LEVEL)
            os.environ["HASS_URL"] = options.get(
                "HASS_URL", "http://homeassistant.local:8123/"
            )
            os.environ["HASS_TOKEN"] = options.get("HASS_TOKEN", "")
            os.environ["ENABLE_DATABASE_STORAGE"] = str(
                options.get("ENABLE_DATABASE_STORAGE", "false")
            ).lower()
            os.environ["IGNORE_USER_ID"] = options.get("IGNORE_USER_ID", "xxxxx,xxxxx")
            os.environ["DB_NAME"] = options.get("DB_NAME", "homeassistant.db")
            os.environ["RETRY_TIMES_LIMIT"] = str(options.get("RETRY_TIMES_LIMIT", 5))
            os.environ["DRIVER_IMPLICITY_WAIT_TIME"] = str(
                options.get("DRIVER_IMPLICITY_WAIT_TIME", 60)
            )
            os.environ["LOGIN_EXPECTED_TIME"] = str(
                options.get("LOGIN_EXPECTED_TIME", 10)
            )
            os.environ["RETRY_WAIT_TIME_OFFSET_UNIT"] = str(
                options.get("RETRY_WAIT_TIME_OFFSET_UNIT", 10)
            )
            os.environ["DATA_RETENTION_DAYS"] = str(options.get("DATA_RETENTION_DAYS"))
            os.environ["RECHARGE_NOTIFY"] = str(
                options.get("RECHARGE_NOTIFY", "false")
            ).lower()
            os.environ["BALANCE"] = str(options.get("BALANCE", 5.0))
            os.environ["PUSHPLUS_TOKEN"] = options.get("PUSHPLUS_TOKEN", "")
            logging.info("当前以Homeassistant Add-on 形式运行.")
        except Exception as e:
            logging.error(
                "Failing to read the options.json file, the program will exit with an error message: %s.",
                e,
            )
            sys.exit()
    else:
        try:
            PHONE_NUMBER = os.getenv("PHONE_NUMBER")
            PASSWORD = os.getenv("PASSWORD")
            JOB_START_TIME = os.getenv("JOB_START_TIME", "07:00")
            LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
            RETRY_TIMES_LIMIT = int(os.getenv("RETRY_TIMES_LIMIT", "5"))

            logger_init(LOG_LEVEL)
            logging.info("The current run runs as a docker image.")
        except Exception as e:
            logging.error(
                "Failing to read the .env file, the program will exit with an error message: %s.",
                e,
            )
            sys.exit()

    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info("The current date is %s.", current_datetime)

    fetcher = DataFetcher(PHONE_NUMBER, PASSWORD)
    next_run_time = datetime.strptime(JOB_START_TIME, "%H:%M") + timedelta(hours=12)
    logging.info(
        "Run job now! The next run will be at %s and %s every day",
        JOB_START_TIME,
        next_run_time.strftime("%H:%M"),
    )
    schedule.every().day.at(JOB_START_TIME).do(run_task, fetcher)
    schedule.every().day.at(next_run_time.strftime("%H:%M")).do(run_task, fetcher)

    signal.signal(
        signal.SIGUSR1, lambda sig, _: sig == signal.SIGUSR1 and run_task(fetcher)
    )

    while True:
        schedule.run_pending()
        time.sleep(1)


RUNNING = False


def run_task(data_fetcher: DataFetcher):
    global RUNNING
    if RUNNING:
        logging.info("has running task, break.")
        return
    RUNNING = True
    for retry_times in range(1, RETRY_TIMES_LIMIT + 1):
        try:
            with data_fetcher:
                data_fetcher.fetch()
                RUNNING = False
                return
        except Exception:
            logging.warning("run %d times failed, retry", retry_times)


def logger_init(level: str):
    logger = logging.getLogger()
    logger.setLevel(level)
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)
    format_handle = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] ---- %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setFormatter(format_handle)
    logger.addHandler(sh)


if __name__ == "__main__":
    main()
