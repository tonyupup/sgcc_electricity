import logging
import os
import re
import subprocess
import time

import random
import base64
import sqlite3
import typing
import undetected_chromedriver as uc
from datetime import datetime
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from sensor_updator import SensorUpdator
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.types import WaitExcTypes

from const import *

import numpy as np

# import cv2
from io import BytesIO
from PIL import Image
from onnx import ONNX
import platform


def base64_to_PLI(base64_str: str):
    base64_data = re.sub("^data:image/.+;base64,", "", base64_str)
    byte_data = base64.b64decode(base64_data)
    image_data = BytesIO(byte_data)
    img = Image.open(image_data)
    return img


def get_transparency_location(image):
    """获取基于透明元素裁切图片的左上角、右下角坐标

    :param image: cv2加载好的图像
    :return: (left, upper, right, lower)元组
    """
    # 1. 扫描获得最左边透明点和最右边透明点坐标
    height, width, channel = image.shape  # 高、宽、通道数
    assert channel == 4  # 无透明通道报错
    first_location = None  # 最先遇到的透明点
    last_location = None  # 最后遇到的透明点
    first_transparency = []  # 从左往右最先遇到的透明点，元素个数小于等于图像高度
    last_transparency = []  # 从左往右最后遇到的透明点，元素个数小于等于图像高度
    for y, rows in enumerate(image):
        for x, BGRA in enumerate(rows):
            alpha = BGRA[3]
            if alpha != 0:
                if (
                    not first_location or first_location[1] != y
                ):  # 透明点未赋值或为同一列
                    first_location = (x, y)  # 更新最先遇到的透明点
                    first_transparency.append(first_location)
                last_location = (x, y)  # 更新最后遇到的透明点
        if last_location:
            last_transparency.append(last_location)

    # 2. 矩形四个边的中点
    top = first_transparency[0]
    bottom = first_transparency[-1]
    left = None
    right = None
    for first, last in zip(first_transparency, last_transparency):
        if not left:
            left = first
        if not right:
            right = last
        if first[0] < left[0]:
            left = first
        if last[0] > right[0]:
            right = last

    # 3. 左上角、右下角
    upper_left = (left[0], top[1])  # 左上角
    bottom_right = (right[0], bottom[1])  # 右下角

    return upper_left[0], upper_left[1], bottom_right[0], bottom_right[1]


class DataFetcher:
    def __init__(self, username: str, password: str):
        if "PYTHON_IN_DOCKER" not in os.environ:
            import dotenv

            dotenv.load_dotenv(verbose=True)
        self._username = username
        self._password = password
        self.onnx = ONNX("./captcha.onnx")

        # 获取 ENABLE_DATABASE_STORAGE 的值，默认为 False
        self.enable_database_storage = (
            os.getenv("ENABLE_DATABASE_STORAGE", "false").lower() == "true"
        )
        self.DRIVER_IMPLICITY_WAIT_TIME = int(
            os.getenv("DRIVER_IMPLICITY_WAIT_TIME", 20)
        )
        self.RETRY_TIMES_LIMIT = int(os.getenv("RETRY_TIMES_LIMIT", 5))
        self.LOGIN_EXPECTED_TIME = int(os.getenv("LOGIN_EXPECTED_TIME", 10))
        self.RETRY_WAIT_TIME_OFFSET_UNIT = int(
            os.getenv("RETRY_WAIT_TIME_OFFSET_UNIT", 10)
        )
        self.IGNORE_USER_ID = os.getenv("IGNORE_USER_ID", "xxxxx,xxxxx").split(",")

    # @staticmethod
    def _click_button(self, button_search_type, button_search_key, timeout=None):
        """wrapped click function, click only when the element is clickable"""
        if not timeout:
            timeout = self.DRIVER_IMPLICITY_WAIT_TIME
        click_element = WebDriverWait(
            self.__driver, self.DRIVER_IMPLICITY_WAIT_TIME
        ).until(EC.element_to_be_clickable((button_search_type, button_search_key)))
        self.__driver.execute_script("arguments[0].click();", click_element)

    def _visible_elem(
        self,
        button_search_type,
        button_search_key,
        timeout=None,
        ignored_exceptions: typing.Optional[WaitExcTypes] | None = None,
    ):
        """wrapped click function, click only when the element is visible"""

        if not timeout:
            timeout = self.DRIVER_IMPLICITY_WAIT_TIME
        click_element = WebDriverWait(
            self.__driver,
            timeout=timeout,
            ignored_exceptions=ignored_exceptions,
        ).until(
            EC.visibility_of_element_located((button_search_type, button_search_key))
        )
        return click_element

    def _visible_elems(
        self,
        button_search_type,
        button_search_key,
        timeout=None,
        ignored_exceptions: typing.Optional[WaitExcTypes] | None = None,
    ):
        """wrapped click function, click only when the elements is visible"""
        if not timeout:
            timeout = self.DRIVER_IMPLICITY_WAIT_TIME
        click_element = WebDriverWait(
            self.__driver,
            timeout=timeout,
            ignored_exceptions=ignored_exceptions,
        ).until(
            EC.visibility_of_any_elements_located(
                (button_search_type, button_search_key)
            )
        )
        return click_element

    # @staticmethod
    def _is_captcha_legal(self, captcha):
        """check the ddddocr result, justify whether it's legal"""
        if len(captcha) != 4:
            return False
        for s in captcha:
            if not s.isalpha() and not s.isdigit():
                return False
        return True

    # @staticmethod
    def _get_chromium_version(self):
        result = str(subprocess.check_output(["chromium", "--product-version"]))
        version = re.findall(r"(\d*)\.", result)[0]
        logging.info(f"chromium-driver version is {version}")
        return int(version)

    # @staticmethod
    def _sliding_track(self, distance):  # 机器模拟人工滑动轨迹
        # 获取按钮
        slider = self.__driver.find_element(
            By.CLASS_NAME, "slide-verify-slider-mask-item"
        )
        ActionChains(self.__driver).click_and_hold(slider).perform()
        # 获取轨迹
        # tracks = _get_tracks(distance)
        # for t in tracks:
        yoffset_random = random.uniform(-2, 4)
        ActionChains(self.__driver).move_by_offset(
            xoffset=distance, yoffset=yoffset_random
        ).perform()

    def connect_user_db(self, user_id):
        """创建数据库集合，db_name = electricity_daily_usage_{user_id}
        :param user_id: 用户ID"""
        try:
            # 创建数据库
            DB_NAME = os.getenv("DB_NAME", "homeassistant.db")
            self.connect = sqlite3.connect(DB_NAME)
            self.connect.cursor()
            logging.info(f"Database of {DB_NAME} created successfully.")
            # 创建表名
            self.table_name = f"daily{user_id}"
            sql = f"""CREATE TABLE IF NOT EXISTS {self.table_name} (
                    date DATE PRIMARY KEY NOT NULL, 
                    usage REAL NOT NULL)"""
            self.connect.execute(sql)
            logging.info(f"Table {self.table_name} created successfully")

            # 创建data表名
            self.table_expand_name = f"data{user_id}"
            sql = f"""CREATE TABLE IF NOT EXISTS {self.table_expand_name} (
                    name TEXT PRIMARY KEY NOT NULL,
                    value TEXT NOT NULL)"""
            self.connect.execute(sql)
            logging.info(f"Table {self.table_expand_name} created successfully")

        # 如果表已存在，则不会创建
        except sqlite3.Error as e:
            logging.debug(f"Create db or Table error:{e}")
            return False
        return True

    def insert_data(self, data: dict):
        if self.connect is None:
            logging.error("Database connection is not established.")
            return
        # 创建索引
        try:
            sql = f"INSERT OR REPLACE INTO {self.table_name} VALUES(strftime('%Y-%m-%d','{data['date']}'),{data['usage']});"
            self.connect.execute(sql)
            self.connect.commit()
        except BaseException as e:
            logging.debug(f"Data update failed: {e}")

    def insert_expand_data(self, data: dict):
        if self.connect is None:
            logging.error("Database connection is not established.")
            return
        # 创建索引
        try:
            sql = f"INSERT OR REPLACE INTO {self.table_expand_name} VALUES('{data['name']}','{data['value']}');"
            self.connect.execute(sql)
            self.connect.commit()
        except BaseException as e:
            logging.debug(f"Data update failed: {e}")

    def _init_webdriver(self):
        chrome_options = Options()
        chrome_options.add_argument("--incognito")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")

        remote_driver = os.getenv("REMOTE_DRIVER")
        if remote_driver:
            self.__driver: WebDriver = WebDriver(remote_driver, options=chrome_options)
        else:
            self.__driver = uc.Chrome(
                driver_executable_path="/usr/bin/chromedriver",
                options=chrome_options,
            )
        self.__driver.implicitly_wait(self.DRIVER_IMPLICITY_WAIT_TIME)
        self.__driver.maximize_window()

    def _login(self, phone_code=False):
        def scan_qr_code():
            cond = (
                By.XPATH,
                "//div[@class='login_ewm']/div[@class='sweepCodePic']/img",
            )

            def wait_for_element(driver):
                try:
                    elem = self.__driver.find_element(*cond)
                    if "data:image/png;base64" in elem.get_attribute("src"):
                        return elem
                except Exception:
                    return False

            qr_code_elem = WebDriverWait(self.__driver, 5).until(wait_for_element)

            ActionChains(self.__driver).move_to_element(qr_code_elem).perform()
            return WebDriverWait(self.__driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.url_to_be("https://www.95598.cn/osgweb/my95598")
            )

        self.__driver.get(LOGIN_URL)
        logging.info(f"Open LOGIN_URL:{LOGIN_URL}.")
        # swtich to username-password login page
        self._click_button(By.CLASS_NAME, "user")
        logging.info("find_element 'user'.")
        self._click_button(By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[2]/span')
        # click agree button
        self._click_button(
            By.XPATH,
            '//*[@id="login_box"]/div[2]/div[1]/form/div[1]/div[3]/div/span[2]',
        )
        logging.info("Click the Agree option.")
        if phone_code:
            self._click_button(
                By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[3]/span'
            )
            input_elements = self._visible_elems(By.CLASS_NAME, "el-input__inner")
            input_elements[2].send_keys(self._username)
            logging.info(f"input_elements username : {self._username}")
            self._click_button(
                By.XPATH,
                '//*[@id="login_box"]/div[2]/div[2]/form/div[1]/div[2]/div[2]/div/a',
            )
            code = input("Input your phone verification code: ")
            input_elements[3].send_keys(code)
            logging.info(f"input_elements verification code: {code}.")
            # click login button
            self._click_button(
                By.XPATH,
                '//*[@id="login_box"]/div[2]/div[2]/form/div[2]/div/button/span',
            )
            logging.info("Click login button.")
            return True
        else:
            # input username and password
            input_elements = self._visible_elems(By.CLASS_NAME, "el-input__inner")
            input_elements[0].send_keys(self._username)
            logging.info(f"input_elements username : {self._username}")
            input_elements[1].send_keys(self._password)
            logging.info(f"input_elements password : {self._password}")
            self._click_button(By.CLASS_NAME, "el-button.el-button--primary")
            logging.info("Click login button.")
            # sometimes ddddOCR may fail, so add retry logic)
            for retry_times in range(1, self.RETRY_TIMES_LIMIT + 1):
                im_info_elem = self._visible_elem(By.ID, "slideVerify")
                background_image = base64_to_PLI(im_info_elem.screenshot_as_base64)
                logging.info(f"Get electricity canvas image successfully.")
                distance = self.onnx.get_distance(background_image)
                logging.info(f"Image CaptCHA distance is {distance}.")
                if distance <= 0:
                    logging.error(
                        f"Image CaptCHA distance is {distance}, please check the image."
                    )
                    self._click_button(By.CLASS_NAME, "el-button.el-button--primary")
                    time.sleep(2)
                    continue

                self._sliding_track(round(distance * 1.06))  # 1.06是补偿
                # wait for login success
                if WebDriverWait(self.__driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                    EC.url_to_be("https://www.95598.cn/osgweb/my95598")
                ):
                    logging.info(f"Sliding CAPTCHA recognition success, login success.")
                    return True
                else:
                    err_msg = self._visible_elem(By.XPATH, "/div[@class='errmsg-tip']")
                    if err_msg:
                        err_msg = err_msg.text
                        logging.error(f"Sliding CAPTCHA recognition failed, {err_msg}")
                        return False
                    continue
        logging.error(
            f"Login failed, maybe caused by Sliding CAPTCHA recognition failed"
        )
        return False

    def __enter__(self):
        return self._init_webdriver()

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.__driver:
                self.__driver.quit()
            if self.connect:
                self.connect.close()
            logging.info("Webdriver closed.")
        except:
            pass

    def fetch(self):
        """main logic here"""
        logging.info("Webdriver initialized.")
        updator = SensorUpdator()

        try:
            if self._login(
                phone_code=os.getenv("DEBUG_MODE", "false").lower() == "true"
            ):
                logging.info("login successed !")
            else:
                logging.info("login unsuccessed !")
                return
        except Exception as e:
            logging.error(
                f"Webdriver quit abnormly, reason: {e}. {self.RETRY_TIMES_LIMIT} retry times left."
            )
            return

        logging.info(f"Login successfully on {LOGIN_URL}")
        logging.info(f"Try to get the userid list")
        user_id_list = self._get_user_ids()
        logging.info(
            f"Here are a total of {len(user_id_list)} userids, which are {user_id_list} among which {self.IGNORE_USER_ID} will be ignored."
        )
        for userid_index, user_id in enumerate(user_id_list):
            try:
                # switch to electricity charge balance page
                self.__driver.get(BALANCE_URL)
                self._choose_current_userid(userid_index)
                current_userid = self._get_current_userid()
                if current_userid in self.IGNORE_USER_ID:
                    logging.info(
                        f"The user ID {current_userid} will be ignored in user_id_list"
                    )
                    continue
                else:
                    ### get data
                    (
                        balance,
                        last_daily_date,
                        last_daily_usage,
                        yearly_charge,
                        yearly_usage,
                        month_charge,
                        month_usage,
                    ) = self._get_all_data(user_id, userid_index)
                    updator.update_one_userid(
                        user_id,
                        balance,
                        last_daily_date,
                        last_daily_usage,
                        yearly_charge,
                        yearly_usage,
                        month_charge,
                        month_usage,
                    )
            except Exception as e:
                if userid_index != len(user_id_list):
                    logging.info(
                        f"The current user {user_id} data fetching failed {e}, the next user data will be fetched."
                    )
                else:
                    logging.info(f"The user {user_id} data fetching failed, {e}")
                    logging.info("Webdriver quit after fetching data successfully.")
                continue

    def _get_current_userid(self):
        current_userid = self.__driver.find_element(
            By.XPATH,
            '//*[@id="app"]/div/div/article/div/div/div[2]/div/div/div[1]/div[2]/div/div/div/div[2]/div/div[1]/div/ul/div/li[1]/span[2]',
        ).text
        return current_userid

    def _choose_current_userid(self, userid_index):
        elements = self.__driver.find_elements(By.CLASS_NAME, "button_confirm")
        if elements:
            self._click_button(
                By.XPATH,
                f"""//*[@id="app"]/div/div[2]/div/div/div/div[2]/div[2]/div/button""",
            )
        self._click_button(By.CLASS_NAME, "el-input__suffix")
        self._click_button(
            By.XPATH, f"/html/body/div[2]/div[1]/div[1]/ul/li[{userid_index+1}]/span"
        )

    def _get_all_data(self, user_id, userid_index):
        balance = self._get_electric_balance()
        if balance is None:
            logging.info(f"Get electricity charge balance for {user_id} failed, Pass.")
        else:
            logging.info(
                f"Get electricity charge balance for {user_id} successfully, balance is {balance} CNY."
            )
        # swithc to electricity usage page
        self.__driver.get(ELECTRIC_USAGE_URL)
        self._choose_current_userid(userid_index)
        # get data for each user id
        yearly_usage, yearly_charge = self._get_yearly_data()

        if yearly_usage is None:
            logging.error(f"Get year power usage for {user_id} failed, pass")
        else:
            logging.info(
                f"Get year power usage for {user_id} successfully, usage is {yearly_usage} kwh"
            )
        if yearly_charge is None:
            logging.error(f"Get year power charge for {user_id} failed, pass")
        else:
            logging.info(
                f"Get year power charge for {user_id} successfully, yealrly charge is {yearly_charge} CNY"
            )

        # 按月获取数据
        month, month_usage, month_charge = self._get_month_usage()
        if month is None:
            logging.error(f"Get month power usage for {user_id} failed, pass")
        else:
            for m in range(len(month)):
                logging.info(
                    f"Get month power charge for {user_id} successfully, {month[m]} usage is {month_usage[m]} KWh, charge is {month_charge[m]} CNY."
                )
        # get yesterday usage
        last_daily_date, last_daily_usage = self._get_yesterday_usage()
        if last_daily_usage is None:
            logging.error(f"Get daily power consumption for {user_id} failed, pass")
        else:
            logging.info(
                f"Get daily power consumption for {user_id} successfully, , {last_daily_date} usage is {last_daily_usage} kwh."
            )
        if month is None:
            logging.error(f"Get month power usage for {user_id} failed, pass")

        # 新增储存用电量
        if self.enable_database_storage:
            # 将数据存储到数据库
            logging.info(
                "enable_database_storage is true, we will store the data to the database."
            )
            # 按天获取数据 7天/30天
            date, usages = self._get_daily_usage_data()
            self._save_user_data(
                user_id,
                balance,
                last_daily_date,
                last_daily_usage,
                date,
                usages,
                month,
                month_usage,
                month_charge,
                yearly_charge,
                yearly_usage,
            )
        else:
            logging.info(
                "enable_database_storage is false, we will not store the data to the database."
            )

        if month_charge:
            month_charge = month_charge[-1]
        else:
            month_charge = None
        if month_usage:
            month_usage = month_usage[-1]
        else:
            month_usage = None

        return (
            balance,
            last_daily_date,
            last_daily_usage,
            yearly_charge,
            yearly_usage,
            month_charge,
            month_usage,
        )

    def _get_user_ids(self):
        try:
            # 刷新网页
            self.__driver.refresh()
            element = WebDriverWait(
                self.__driver, self.DRIVER_IMPLICITY_WAIT_TIME
            ).until(EC.presence_of_element_located((By.CLASS_NAME, "el-dropdown")))
            # click roll down button for user id
            self._click_button(By.XPATH, "//div[@class='el-dropdown']/span")
            logging.debug(
                f"""self._click_button(driver, By.XPATH, "//div[@class='el-dropdown']/span")"""
            )
            # wait for roll down menu displayed
            target = self.__driver.find_element(
                By.CLASS_NAME, "el-dropdown-menu.el-popper"
            ).find_element(By.TAG_NAME, "li")
            logging.debug(
                f"""target = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_element(By.TAG_NAME, "li")"""
            )
            WebDriverWait(self.__driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.visibility_of(target)
            )
            logging.debug(
                f"""WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(target))"""
            )
            WebDriverWait(self.__driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.text_to_be_present_in_element(
                    (By.XPATH, "//ul[@class='el-dropdown-menu el-popper']/li"), ":"
                )
            )
            # get user id one by one
            userid_elements = self.__driver.find_element(
                By.CLASS_NAME, "el-dropdown-menu.el-popper"
            ).find_elements(By.TAG_NAME, "li")
            userid_list = []
            for element in userid_elements:
                userid_list.append(re.findall("[0-9]+", element.text)[-1])
            return userid_list
        except Exception as e:
            logging.error(
                f"Webdriver quit abnormly, reason: {e}. get user_id list failed."
            )
            self.__driver.quit()

    def _get_electric_balance(self):
        try:
            balance = self.__driver.find_element(By.CLASS_NAME, "num").text
            balance_text = self.__driver.find_element(By.CLASS_NAME, "amttxt").text
            if "欠费" in balance_text:
                return -float(balance)
            else:
                return float(balance)
        except:
            return None

    def _get_yearly_data(self):
        try:
            if datetime.now().month == 1:
                self._click_button(
                    By.XPATH, '//*[@id="pane-first"]/div[1]/div/div[1]/div/div/input'
                )
                self._click_button(
                    By.XPATH, f"//span[contains(text(), '{datetime.now().year - 1}')]"
                )
                self._click_button(
                    By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-first']"
                )
            # wait for data displayed
            self._visible_elem(By.CLASS_NAME, "total", 3)
        except Exception as e:
            logging.error(f"The yearly data get failed : {e}")
            return None, None

        # get data
        try:
            yearly_usage = self._visible_elem(
                By.XPATH, "//ul[@class='total']/li[1]/span"
            ).text
        except Exception as e:
            logging.error(f"The yearly_usage data get failed : {e}")
            yearly_usage = None

        try:
            yearly_charge = self._visible_elem(
                By.XPATH, "//ul[@class='total']/li[2]/span"
            ).text
        except Exception as e:
            logging.error(f"The yearly_charge data get failed : {e}")
            yearly_charge = None

        return yearly_usage, yearly_charge

    def _get_yesterday_usage(self):
        """获取最近一次用电量"""
        try:
            # 点击日用电量
            self._click_button(
                By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-second']"
            )

            # 增加是哪一天
            date_elements = self._visible_elems(
                By.XPATH,
                "//div[@class='el-tab-pane dayd']//div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody/tr[1]/td/div",
            )
            last_daily_date = date_elements[0].text  # 获取最近一次用电量的日期
            return last_daily_date, float(date_elements[1].text)
        except Exception as e:
            logging.error(f"The yesterday data get failed : {e}")
            return None, None

    def _get_month_usage(self):
        """获取每月用电量"""
        try:
            self._click_button(
                By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-first']"
            )
            if datetime.now().month == 1:
                self._click_button(
                    By.XPATH, '//*[@id="pane-first"]/div[1]/div/div[1]/div/div/input'
                )
                span_element = self.__driver.find_element(
                    By.XPATH, f"//span[contains(text(), '{datetime.now().year - 1}')]"
                )
                span_element.click()
            # wait for month displayed
            self._visible_elem(By.CLASS_NAME, "total")
            month_element = self._visible_elem(
                By.XPATH,
                "//*[@id='pane-first']/div[1]/div[2]/div[2]/div/div[3]/table/tbody",
            ).text
            month_element = month_element.split("\n")
            month_element.remove("MAX")
            month_element = np.array(month_element).reshape(-1, 3)
            # 将每月的用电量保存为List
            month = []
            usage = []
            charge = []
            for i in range(len(month_element)):
                month.append(month_element[i][0])
                usage.append(month_element[i][1])
                charge.append(month_element[i][2])
            return month, usage, charge
        except Exception as e:
            logging.error(f"The month data get failed : {e}")
            return None, None, None

    # 增加获取每日用电量的函数
    def _get_daily_usage_data(self):
        """储存指定天数的用电量"""
        retention_days = int(os.getenv("DATA_RETENTION_DAYS", 7))  # 默认值为7天
        self._click_button(
            By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-second']"
        )
        # 7 天在第一个 label, 30 天 开通了智能缴费之后才会出现在第二个, (sb sgcc)
        if retention_days == 7:
            self._click_button(
                By.XPATH, "//*[@id='pane-second']/div[1]/div/label[1]/span[1]"
            )
        elif retention_days == 30:
            self._click_button(
                By.XPATH, "//*[@id='pane-second']/div[1]/div/label[2]/span[1]"
            )
        else:
            logging.error(f"Unsupported retention days value: {retention_days}")
            return

        # 等待用电量的数据出现
        usage_element = (
            By.XPATH,
            "//div[@class='el-tab-pane dayd']//div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody/tr[1]/td[2]/div",
        )
        self._visible_elem(*usage_element)

        # 获取用电量的数据
        days_element = self._visible_elems(
            By.XPATH,
            "//*[@id='pane-second']/div[2]/div[2]/div[1]/div[3]/table/tbody/tr",
        )  # 用电量值列表
        date = []
        usages = []
        # 将用电量保存为字典
        for i in days_element:
            day = i.find_element(By.XPATH, "td[1]/div").text
            usage = i.find_element(By.XPATH, "td[2]/div").text
            if usage != "":
                usages.append(usage)
                date.append(day)
            else:
                logging.info(f"The electricity consumption of {usage} get nothing")
        return date, usages

    def _save_user_data(
        self,
        user_id,
        balance,
        last_daily_date,
        last_daily_usage,
        date,
        usages,
        month,
        month_usage,
        month_charge,
        yearly_charge,
        yearly_usage,
    ):
        # 连接数据库集合
        if self.connect_user_db(user_id):
            # 写入当前户号
            dic = {"name": "user", "value": f"{user_id}"}
            self.insert_expand_data(dic)
            # 写入剩余金额
            dic = {"name": "balance", "value": f"{balance}"}
            self.insert_expand_data(dic)
            # 写入最近一次更新时间
            dic = {"name": f"daily_date", "value": f"{last_daily_date}"}
            self.insert_expand_data(dic)
            # 写入最近一次更新时间用电量
            dic = {"name": f"daily_usage", "value": f"{last_daily_usage}"}
            self.insert_expand_data(dic)

            # 写入年用电量
            dic = {"name": "yearly_usage", "value": f"{yearly_usage}"}
            self.insert_expand_data(dic)
            # 写入年用电电费
            dic = {"name": "yearly_charge", "value": f"{yearly_charge} "}
            self.insert_expand_data(dic)

            for index in range(len(date)):
                dic = {"date": date[index], "usage": float(usages[index])}
                # 插入到数据库
                try:
                    self.insert_data(dic)
                    logging.info(
                        f"The electricity consumption of {usages[index]}KWh on {date[index]} has been successfully deposited into the database"
                    )
                except Exception as e:
                    logging.debug(
                        f"The electricity consumption of {date[index]} failed to save to the database, which may already exist: {str(e)}"
                    )

            for index in range(len(month)):
                try:
                    dic = {
                        "name": f"{month[index]}usage",
                        "value": f"{month_usage[index]}",
                    }
                    self.insert_expand_data(dic)
                    dic = {
                        "name": f"{month[index]}charge",
                        "value": f"{month_charge[index]}",
                    }
                    self.insert_expand_data(dic)
                except Exception as e:
                    logging.debug(
                        f"The electricity consumption of {month[index]} failed to save to the database, which may already exist: {str(e)}"
                    )
            if month_charge:
                month_charge = month_charge[-1]
            else:
                month_charge = None

            if month_usage:
                month_usage = month_usage[-1]
            else:
                month_usage = None
            # 写入本月电量
            dic = {"name": f"month_usage", "value": f"{month_usage}"}
            self.insert_expand_data(dic)
            # 写入本月电费
            dic = {"name": f"month_charge", "value": f"{month_charge}"}
            self.insert_expand_data(dic)
            # dic = {'date': month[index], 'usage': float(month_usage[index]), 'charge': float(month_charge[index])}
            self.connect.close()
        else:
            logging.info(
                "The database creation failed and the data was not written correctly."
            )
            return


if __name__ == "__main__":
    with open("bg.jpg", "rb") as f:
        test1 = f.read()
        print(type(test1))
        print(test1)
