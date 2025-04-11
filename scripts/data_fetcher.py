import logging
import os
import re
import time

import random
import base64
import typing

from datetime import datetime
from selenium.webdriver import Chrome, ChromeService
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from sensor_updator import MQTTSensorUpdator
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.types import WaitExcTypes
from selenium.common import exceptions as sel_ex

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


class DataFetcher:
    def __init__(self, username: str, password: str):
        if "PYTHON_IN_DOCKER" not in os.environ:
            import dotenv

            dotenv.load_dotenv(verbose=True)
        self._username = username
        self._password = password
        self.onnx = ONNX("./captcha.onnx")

        # 获取 ENABLE_DATABASE_STORAGE 的值，默认为 False
        # self.enable_database_storage = (
        #     os.getenv("ENABLE_DATABASE_STORAGE", "false").lower() == "true"
        # )

        self.DRIVER_IMPLICITY_WAIT_TIME = int(
            os.getenv("DRIVER_IMPLICITY_WAIT_TIME", 10)
        )
        self.RETRY_TIMES_LIMIT = int(os.getenv("RETRY_TIMES_LIMIT", 5))
        self.LOGIN_EXPECTED_TIME = int(os.getenv("LOGIN_EXPECTED_TIME", 10))
        self.RETRY_WAIT_TIME_OFFSET_UNIT = int(
            os.getenv("RETRY_WAIT_TIME_OFFSET_UNIT", 10)
        )
        self.IGNORE_USER_ID = os.getenv("IGNORE_USER_ID", "").split(",")

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
        ignore_timeout=False,
        ignored_exceptions: typing.Optional[WaitExcTypes] | None = None,
    ):
        """wrapped click function, click only when the element is visible"""

        if not timeout:
            timeout = self.DRIVER_IMPLICITY_WAIT_TIME
        if ignore_timeout:
            ignored_exceptions = list(ignored_exceptions)
            ignored_exceptions.append(sel_ex.TimeoutException)
        return WebDriverWait(
            self.__driver,
            timeout=timeout,
            ignored_exceptions=ignored_exceptions,
        ).until(
            EC.visibility_of_element_located((button_search_type, button_search_key))
        )

    def _visible_elems(
        self,
        button_search_type,
        button_search_key,
        timeout=None,
        ignore_timeout=False,
        ignored_exceptions: typing.Optional[WaitExcTypes] | None = None,
    ):
        """wrapped click function, click only when the elements is visible"""
        if not timeout:
            timeout = self.DRIVER_IMPLICITY_WAIT_TIME
        if ignore_timeout:
            ignored_exceptions = list(ignored_exceptions)
            ignored_exceptions.append(sel_ex.TimeoutException)
        return WebDriverWait(
            self.__driver,
            timeout=timeout,
            ignored_exceptions=ignored_exceptions,
        ).until(
            EC.visibility_of_any_elements_located(
                (button_search_type, button_search_key)
            )
        )

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
    def _sliding_track(self, distance):  # 机器模拟人工滑动轨迹
        # 获取按钮
        slider = self.__driver.find_element(
            By.CLASS_NAME, "slide-verify-slider-mask-item"
        )
        ActionChains(self.__driver, 500).click_and_hold(slider).perform()
        # 获取轨迹
        # tracks = _get_tracks(distance)
        # for t in tracks:
        yoffset_random = random.uniform(-2, 4)
        ActionChains(self.__driver, 500).move_by_offset(
            xoffset=distance, yoffset=yoffset_random
        ).release().perform()

    def _init_webdriver(self):
        chrome_options = Options()
        chrome_options.add_argument("--incognito")
        chrome_options.add_argument("--window-size=1920,1080")
        if os.getenv("WEBDRIVER_HEADLESS"):
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")

        remote_driver = os.getenv("REMOTE_DRIVER")
        if remote_driver:
            self.__driver: WebDriver = WebDriver(remote_driver, options=chrome_options)
        else:
            self.__driver = Chrome(
                service=ChromeService(executable_path="/usr/bin/chromedriver"),
                options=chrome_options,
            )
        self.__driver.implicitly_wait(self.DRIVER_IMPLICITY_WAIT_TIME)
        self.__driver.maximize_window()

    def _login(self, phone_code=False, scan_qr_code=False):
        def scan_qr_code_logic():
            cond = (
                By.XPATH,
                "//div[@class='login_ewm']/div[@class='sweepCodePic']/img",
            )

            def wait_for_element(_):
                try:
                    elem = self.__driver.find_element(*cond)
                    if "data:image/png;base64" in elem.get_attribute("src"):
                        return elem
                except sel_ex.NoSuchElementException:
                    return False

            qr_code_elem = WebDriverWait(self.__driver, 5).until(wait_for_element)
            ActionChains(self.__driver).move_to_element(qr_code_elem).perform()
            logging.info("Please scan the QR code within 30 seconds.")
            # wait for login success
            return WebDriverWait(self.__driver, 30).until(
                EC.url_to_be("https://www.95598.cn/osgweb/my95598"),
                "Waiting for scanning qrcode login failed to redirect to target page",
            )

        self.__driver.get(LOGIN_URL)
        logging.info(f"Open LOGIN_URL:{LOGIN_URL}.")
        if scan_qr_code:
            return scan_qr_code_logic()

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

        # input username and password
        input_elements = self._visible_elems(By.CLASS_NAME, "el-input__inner")
        input_elements[0].send_keys(self._username)
        logging.info(f"input_elements username : {self._username}")
        input_elements[1].send_keys(self._password)
        logging.info(f"input_elements password")
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
                self._click_button(
                    By.XPATH, "//div[@class='slide-verify-refresh-icon']"
                )
                time.sleep(2)
                continue

            self._sliding_track(round(distance * 1.06))  # 1.06是补偿
            # wait for login success
            if WebDriverWait(self.__driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.url_to_be("https://www.95598.cn/osgweb/my95598")
            ):
                logging.info(f"Sliding CAPTCHA recognition success, login success.")
                return True

            logging.warning(
                f"wait login success jump failed, retry times: {retry_times}"
            )
            err_msg = self._visible_elem(By.XPATH, "//div[@class='errmsg-tip']", 10)
            if err_msg:
                err_msg = err_msg.text
                logging.error(f"Sliding CAPTCHA recognition failed, {err_msg}")
                return False
        return False

    def __enter__(self):
        try:
            self._init_webdriver()
        except sel_ex.WebDriverException as e:
            logging.error("fail to init webdriver", e)
            raise RuntimeError("fail to init webdriver, check config")
        return self

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
        updator = MQTTSensorUpdator(
            os.getenv("MQTT_USERNAME"),
            os.getenv("MQTT_PASSWORD"),
            os.getenv("MQTT_HOST"),
            int(os.getenv("MQTT_PORT", 1883)),
        )
        with updator:
            if not updator.ping():
                raise RuntimeError("mqtt not connected")

        if self._login(
            phone_code=bool(os.getenv("DEBUG_MODE")),
            scan_qr_code=bool(os.getenv("SCAN_QR_CODE")),
        ):
            logging.info("login successed !")
        else:
            logging.info("login unsuccessed !")
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
                    data = (
                        balance,
                        last_daily_date,
                        last_daily_usage,
                        yearly_charge,
                        yearly_usage,
                        month_charge,
                        month_usage,
                        lastdays_usages,
                    ) = self._get_all_data(user_id, userid_index)
                    logging.debug("fetch data success", data)
                    with updator:
                        updator.update_one_userid(
                            user_id,
                            balance,
                            last_daily_date,
                            last_daily_usage,
                            yearly_charge,
                            yearly_usage,
                            month_charge,
                            month_usage,
                            lastdays_usages,
                        )
                    logging.info("success update sensor for user_id: %s", user_id)
            except (sel_ex.NoSuchElementException, sel_ex.TimeoutException) as e:
                if userid_index != len(user_id_list):
                    logging.info(
                        f"The current user {user_id} data fetching failed {e}, the next user data will be fetched."
                    )
                else:
                    logging.info(f"The user {user_id} data fetching failed, {e}")
                    logging.info("Webdriver quit after fetching data successfully.")
                continue

    def _get_current_userid(self):
        return self.__driver.find_element(
            By.XPATH,
            '//*[@id="app"]/div/div/article/div/div/div[2]/div/div/div[1]/div[2]/div/div/div/div[2]/div/div[1]/div/ul/div/li[1]/span[2]',
        ).text

    def _choose_current_userid(self, userid_index):
        elements = self.__driver.find_elements(By.CLASS_NAME, "button_confirm")
        if elements:
            self._click_button(
                By.XPATH,
                '//*[@id="app"]/div/div[2]/div/div/div/div[2]/div[2]/div/button',
            )
        self._click_button(By.CLASS_NAME, "el-input__suffix")
        self._click_button(
            By.XPATH, f"/html/body/div[2]/div[1]/div[1]/ul/li[{userid_index+1}]/span"
        )

    def _get_all_data(self, user_id, userid_index):
        balance = self._get_electric_balance()
        if balance is None:
            logging.warning(f"Get electricity charge balance for {user_id} failed, Pass.")
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
        if yearly_charge is None:
            logging.error(f"Get year power charge for {user_id} failed, pass")

        # 按月获取数据
        month, month_usage, month_charge = self._get_month_usage()
        if month is None:
            logging.error(f"Get month power usage for {user_id} failed, pass")

        # get yesterday usage
        last_daily_date, last_daily_usage = self._get_yesterday_usage()
        if last_daily_usage is None:
            logging.error(f"Get daily power consumption for {user_id} failed, pass")

        last_days_usages = None
        # 按天获取数据 7天/30天
        if os.getenv("DATA_RETENTION_DAYS"):
            last_days_usages = self._get_daily_usage_data()

        month_charge = float(month_charge[-1]) if month_charge else None
        month_usage = float(month_usage[-1]) if month_usage else None

        return (
            balance,
            last_daily_date,
            last_daily_usage,
            yearly_charge,
            yearly_usage,
            month_charge,
            month_usage,
            last_days_usages,
        )

    def _get_user_ids(self):
        try:
            # 刷新网页
            element = WebDriverWait(
                self.__driver, self.DRIVER_IMPLICITY_WAIT_TIME
            ).until(EC.presence_of_element_located((By.CLASS_NAME, "el-dropdown")))
            # click roll down button for user id
            self._click_button(By.XPATH, "//div[@class='el-dropdown']/span")

            # wait for roll down menu displayed
            target = self.__driver.find_element(
                By.CLASS_NAME, "el-dropdown-menu.el-popper"
            ).find_element(By.TAG_NAME, "li")

            WebDriverWait(self.__driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.visibility_of(target)
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

    def _get_electric_balance(self):
        try:
            balance = self.__driver.find_element(By.CLASS_NAME, "num").text
            balance_text = self.__driver.find_element(By.CLASS_NAME, "amttxt").text

            return -float(balance) if "欠费" in balance_text else float(balance)
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
            logging.error("The yearly data get failed %s", e)
            return None, None

        # get data
        try:
            yearly_usage = self._visible_elem(
                By.XPATH, "//ul[@class='total']/li[1]/span"
            ).text
        except Exception as e:
            logging.error("The yearly_usage data get failed : %s", e)
            yearly_usage = None

        try:
            yearly_charge = self._visible_elem(
                By.XPATH, "//ul[@class='total']/li[2]/span"
            ).text
        except Exception as e:
            logging.error("The yearly_charge data get failed : %s", e)
            yearly_charge = None

        return float(yearly_usage), float(yearly_charge)

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
            self._visible_elem(
                By.CLASS_NAME,
                "total",
            )
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
            for index, _ in enumerate(month_element):
                month.append(month_element[index][0])
                usage.append(month_element[index][1])
                charge.append(month_element[index][2])
            return month, usage, charge
        except Exception as e:
            logging.error(f"The month data get failed : {e.args}")
            return None, None, None

    # 增加获取每日用电量的函数
    def _get_daily_usage_data(
        self,
    ) -> typing.List[typing.Tuple[str, float]] | None:
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
            return None

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

        # 将用电量保存为字典
        lastdays_usage = []
        for elem in days_element:
            day = elem.find_element(By.XPATH, "td[1]/div").text
            usage = elem.find_element(By.XPATH, "td[2]/div").text
            if usage != "":
                lastdays_usage.append((day, float(usage)))
        return lastdays_usage
