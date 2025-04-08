import re
import time
from os import path
import random
import logging
import base64
import typing
from datetime import datetime
from selenium.webdriver import ActionChains, Chrome, ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.types import WaitExcTypes
from selenium.common import exceptions as sel_ex
import numpy as np
from .const import LOGIN_URL, BALANCE_URL, ELECTRIC_USAGE_URL
from .onnx import ONNX


# import cv2
from io import BytesIO
from PIL import Image


def base64_to_PLI(base64_str: str):
    base64_data = re.sub("^data:image/.+;base64,", "", base64_str)
    byte_data = base64.b64decode(base64_data)
    image_data = BytesIO(byte_data)
    img = Image.open(image_data)
    return img


class DataFetcher:
    def __init__(
        self, logger: logging.Logger, username: str, password: str, config: dict
    ):
        self._username = username
        self._password = password
        current_dir = path.dirname(__file__)
        # 构建目标文件的完整路径
        target_path = path.join(current_dir, "captcha.onnx")

        self._onnx = ONNX(target_path)
        self._driver: WebDriver = None
        self._config = config
        self._logger = logger

        self.DRIVER_IMPLICITY_WAIT_TIME = int(
            self._config.get("DRIVER_IMPLICITY_WAIT_TIME", 10)
        )
        self.RETRY_TIMES_LIMIT = int(self._config.get("RETRY_TIMES_LIMIT", 5))
        self.LOGIN_EXPECTED_TIME = int(self._config.get("LOGIN_EXPECTED_TIME", 10))
        self.RETRY_WAIT_TIME_OFFSET_UNIT = int(
            self._config.get("RETRY_WAIT_TIME_OFFSET_UNIT", 10)
        )
        self.IGNORE_USER_ID = self._config.get("IGNORE_USER_ID", "xxxxx,xxxxx").split(
            ","
        )

    # @staticmethod
    def _click_button(self, button_search_type, button_search_key, timeout=None):
        """wrapped click function, click only when the element is clickable"""
        if not timeout:
            timeout = self.DRIVER_IMPLICITY_WAIT_TIME
        click_element = WebDriverWait(
            self._driver, self.DRIVER_IMPLICITY_WAIT_TIME
        ).until(EC.element_to_be_clickable((button_search_type, button_search_key)))
        self._driver.execute_script("arguments[0].click();", click_element)

    def _visible_elem(
        self,
        button_search_type,
        button_search_key,
        timeout=None,
        ignore_timeout=False,
        ignored_exceptions: typing.Optional[WaitExcTypes] | None = None,
    ):
        """Wrapped click function, click only when the element is visible"""

        if not timeout:
            timeout = self.DRIVER_IMPLICITY_WAIT_TIME
        if ignore_timeout:
            ignored_exceptions = list(ignored_exceptions)
            ignored_exceptions.append(sel_ex.TimeoutException)
        elem = WebDriverWait(
            self._driver,
            timeout=timeout,
            ignored_exceptions=ignored_exceptions,
        ).until(
            EC.visibility_of_element_located((button_search_type, button_search_key))
        )
        return elem

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
        elems = WebDriverWait(
            self._driver,
            timeout=timeout,
            ignored_exceptions=ignored_exceptions,
        ).until(
            EC.visibility_of_any_elements_located(
                (button_search_type, button_search_key)
            )
        )
        return elems

    # @staticmethod
    def _is_captcha_legal(self, captcha):
        """check the ddddocr result, justify whether it's legal"""
        if len(captcha) != 4:
            return False
        return all(s.isalpha() or s.isdigit() for s in captcha)

    # @staticmethod
    def _sliding_track(self, distance):  # 机器模拟人工滑动轨迹
        # 获取按钮
        slider = self._driver.find_element(
            By.CLASS_NAME, "slide-verify-slider-mask-item"
        )
        ActionChains(self._driver, 500).click_and_hold(slider).perform()
        # 获取轨迹
        # tracks = _get_tracks(distance)
        # for t in tracks:
        yoffset_random = random.uniform(-2, 4)
        ActionChains(self._driver, 500).move_by_offset(
            xoffset=distance, yoffset=yoffset_random
        ).release().perform()

    def _init_webdriver(self):
        chrome_options = Options()
        chrome_options.add_argument("--incognito")
        chrome_options.add_argument("--window-size=1920,1080")
        if self._config.get("WEBDRIVER_HEADLESS"):
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")

        remote_driver = self._config.get("REMOTE_DRIVER")
        if remote_driver:
            self._driver: WebDriver = WebDriver(remote_driver, options=chrome_options)
        else:
            self._driver = Chrome(
                options=chrome_options,
                service=ChromeService("/usr/bin/chromedriver"),
            )
        self._driver.implicitly_wait(self.DRIVER_IMPLICITY_WAIT_TIME)
        self._driver.maximize_window()

    def _login(self, phone_code=False, scan_qr_code=False):
        def scan_qr_code_logic():
            cond = (
                By.XPATH,
                "//div[@class='login_ewm']/div[@class='sweepCodePic']/img",
            )

            def wait_for_element(_):
                try:
                    elem = self._driver.find_element(*cond)
                    if "data:image/png;base64" in elem.get_attribute("src"):
                        return elem
                except Exception:
                    return False

            qr_code_elem = WebDriverWait(self._driver, 5).until(wait_for_element)
            ActionChains(self._driver).move_to_element(qr_code_elem).perform()
            self._logger.info("please scan the QR code.")
            # wait for login success
            return WebDriverWait(self._driver, 20).until(
                EC.url_to_be("https://www.95598.cn/osgweb/my95598"),
                "waiting for scan qrcode login failed, not redirect to target page",
            )

        self._driver.get(LOGIN_URL)
        self._logger.info("Open LOGIN_URL: %s", LOGIN_URL)
        if scan_qr_code:
            return scan_qr_code_logic()

        # swtich to username-password login page
        self._click_button(By.CLASS_NAME, "user")
        self._logger.info("find_element 'user'.")
        self._click_button(By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[2]/span')
        # click agree button
        self._click_button(
            By.XPATH,
            '//*[@id="login_box"]/div[2]/div[1]/form/div[1]/div[3]/div/span[2]',
        )
        self._logger.info("Click the Agree option.")
        # if phone_code:
        #    self._click_button(
        #        By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[3]/span'
        #    )
        #    input_elements = self._visible_elems(By.CLASS_NAME, "el-input__inner")
        #    input_elements[2].send_keys(self._username)
        #    self._logger.info(f"input_elements username : {self._username}")
        #    self._click_button(
        #        By.XPATH,
        #        '//*[@id="login_box"]/div[2]/div[2]/form/div[1]/div[2]/div[2]/div/a',
        #    )
        #    code = input("Input your phone verification code: ")
        #    input_elements[3].send_keys(code)
        #    self._logger.info(f"input_elements verification code: {code}.")
        #    # click login button
        #    self._click_button(
        #        By.XPATH,
        #        '//*[@id="login_box"]/div[2]/div[2]/form/div[2]/div/button/span',
        #    )
        #    self._logger.info("Click login button.")
        #    return True

        # input username and password
        input_elements = self._visible_elems(By.CLASS_NAME, "el-input__inner")
        input_elements[0].send_keys(self._username)
        self._logger.info("input_elements username: %s", self._username)
        input_elements[1].send_keys(self._password)
        self._logger.info("input_elements password")
        self._click_button(By.CLASS_NAME, "el-button.el-button--primary")
        self._logger.info("Click login button.")
        # sometimes ddddOCR may fail, so add retry logic)
        for retry_times in range(1, self.RETRY_TIMES_LIMIT + 1):
            im_info_elem = self._visible_elem(By.ID, "slideVerify")
            background_image = base64_to_PLI(im_info_elem.screenshot_as_base64)
            self._logger.info("Get electricity canvas image successfully.")
            distance = self._onnx.get_distance(background_image)
            self._logger.info("Image CaptCHA distance is %s.", distance)
            if distance <= 0:
                self._logger.error(
                    "Image CaptCHA distance is %s, please check the image.", distance
                )
                self._click_button(
                    By.XPATH, "//div[@class='slide-verify-refresh-icon']"
                )
                time.sleep(2)
                continue

            self._sliding_track(round(distance * 1.06))  # 1.06是补偿
            # wait for login success
            if WebDriverWait(self._driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.url_to_be("https://www.95598.cn/osgweb/my95598")
            ):
                self._logger.info("Sliding CAPTCHA recognition success, login success.")
                return True

            self._logger.warning(
                "wait login success jump failed, retry times: %d", retry_times
            )
            err_msg = self._visible_elem(
                By.XPATH, "//div[@class='errmsg-tip']", 10, True
            )
            if err_msg:
                err_msg = err_msg.text
                self._logger.error("Sliding CAPTCHA recognition failed: %s", err_msg)
                return False
        return False

    def __enter__(self):
        self._init_webdriver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._driver.quit()

    def fetch(self):
        """main logic here"""
        self._logger.info("Webdriver initialized.")

        if not self._login(
            phone_code=bool(self._config.get("DEBUG_MODE")),
            scan_qr_code=bool(self._config.get("SCAN_QR_CODE")),
        ):
            self._logger.info("login unsuccessed !")
            return

        self._logger.info("login successed !")
        self._logger.info("Try to get the userid list")
        user_id_list = self._get_user_ids()
        self._logger.info(
            "Here are a total of %d userids, which are %s among which %s will be ignored.",
            len(user_id_list),
            user_id_list,
            self.IGNORE_USER_ID,
        )
        for userid_index, user_id in enumerate(user_id_list):
            try:
                # switch to electricity charge balance page
                self._driver.get(BALANCE_URL)
                self._choose_current_userid(userid_index)
                current_userid = self._get_current_userid()
                if current_userid in self.IGNORE_USER_ID:
                    self._logger.info(
                        "The user ID %s will be ignored in user_id_list", current_userid
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
                    yield (
                        user_id,
                        balance,
                        last_daily_date,
                        last_daily_usage,
                        yearly_charge,
                        yearly_usage,
                        month_charge,
                        month_usage,
                    )
            except (sel_ex.NoSuchElementException, sel_ex.TimeoutException) as e:
                if userid_index != len(user_id_list):
                    self._logger.info(
                        "The current user %s data fetching failed %s, the next user data will be fetched.",
                        user_id,
                        e,
                    )
                else:
                    self._logger.info(
                        "The user %s data fetching failed, %s", user_id, e
                    )
                    self._logger.info(
                        "Webdriver quit after fetching data successfully."
                    )
                continue

    def _get_current_userid(self):
        return self._driver.find_element(
            By.XPATH,
            '//*[@id="app"]/div/div/article/div/div/div[2]/div/div/div[1]/div[2]/div/div/div/div[2]/div/div[1]/div/ul/div/li[1]/span[2]',
        ).text

    def _choose_current_userid(self, userid_index):
        elements = self._driver.find_elements(By.CLASS_NAME, "button_confirm")
        if elements:
            self._click_button(
                By.XPATH,
                f"""//*[@id="app"]/div/div[2]/div/div/div/div[2]/div[2]/div/button""",
            )
        self._click_button(By.CLASS_NAME, "el-input__suffix")
        self._click_button(
            By.XPATH, f"/html/body/div[2]/div[1]/div[1]/ul/li[{userid_index + 1}]/span"
        )

    def _get_all_data(self, user_id, userid_index):
        balance = self._get_electric_balance()
        if balance is None:
            self._logger.info(
                "Get electricity charge balance for %s failed, Pass.", user_id
            )
        else:
            self._logger.info(
                "Get electricity charge balance for %s successfully, balance is %s CNY.",
                user_id,
                balance,
            )
        # swithc to electricity usage page
        self._driver.get(ELECTRIC_USAGE_URL)
        self._choose_current_userid(userid_index)
        # get data for each user id
        yearly_usage, yearly_charge = self._get_yearly_data()

        if yearly_usage is None:
            self._logger.error("Get year power usage for %s failed, pass", user_id)
        else:
            yearly_usage = float(yearly_usage)
            self._logger.info(
                "Get year power usage for %s successfully, usage is %s kwh",
                user_id,
                yearly_usage,
            )
        if yearly_charge is None:
            self._logger.error("Get year power charge for %s failed, pass", user_id)
        else:
            yearly_charge = float(yearly_charge)
            self._logger.info(
                "Get year power charge for %s successfully, yearly charge is %s CNY",
                user_id,
                yearly_charge,
            )

        # 按月获取数据
        month, month_usage, month_charge = self._get_month_usage()
        if month is None:
            self._logger.error("Get month power usage for %s failed, pass", user_id)
        else:
            for m in range(len(month)):
                self._logger.info(
                    "Get month power charge for %s successfully, %s usage is %s KWh, charge is %s CNY.",
                    user_id,
                    month[m],
                    month_usage[m],
                    month_charge[m],
                )
        # get yesterday usage
        last_daily_date, last_daily_usage = self._get_yesterday_usage()
        if last_daily_usage is None:
            self._logger.error(
                "Get daily power consumption for %s failed, pass", user_id
            )
        else:
            last_daily_usage = float(last_daily_usage)
            self._logger.info(
                "Get daily power consumption for %s successfully, , %s usage is %s kwh.",
                user_id,
                last_daily_date,
                last_daily_usage,
            )
        if month is None:
            self._logger.error("Get month power usage for %s failed, pass", user_id)

        # 新增储存用电量
        # if self.enable_database_storage:
        #     # 将数据存储到数据库
        #     self.__logger.info(
        #         "enable_database_storage is true, we will store the data to the database."
        #     )
        #     # 按天获取数据 7天/30天
        #     date, usages = self._get_daily_usage_data()
        #     self._save_user_data(
        #         user_id,
        #         balance,
        #         last_daily_date,
        #         last_daily_usage,
        #         date,
        #         usages,
        #         month,
        #         month_usage,
        #         month_charge,
        #         yearly_charge,
        #         yearly_usage,
        #     )
        # else:
        #     self.__logger.info(
        #         "enable_database_storage is false, we will not store the data to the database."
        #     )

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
        )

    def _get_user_ids(self):
        try:
            # 刷新网页
            self._driver.refresh()
            element = WebDriverWait(
                self._driver, self.DRIVER_IMPLICITY_WAIT_TIME
            ).until(EC.presence_of_element_located((By.CLASS_NAME, "el-dropdown")))
            # click roll down button for user id
            self._click_button(By.XPATH, "//div[@class='el-dropdown']/span")
            # wait for roll down menu displayed
            target = self._driver.find_element(
                By.CLASS_NAME, "el-dropdown-menu.el-popper"
            ).find_element(By.TAG_NAME, "li")
            WebDriverWait(self._driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.visibility_of(target)
            )
            WebDriverWait(self._driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
                EC.text_to_be_present_in_element(
                    (By.XPATH, "//ul[@class='el-dropdown-menu el-popper']/li"), ":"
                )
            )
            # get user id one by one
            userid_elements = self._driver.find_element(
                By.CLASS_NAME, "el-dropdown-menu.el-popper"
            ).find_elements(By.TAG_NAME, "li")
            return [
                re.findall("[0-9]+", element.text)[-1] for element in userid_elements
            ]
        except Exception as e:
            self._logger.error(
                f"Webdriver quit abnormly, reason: {e}. get user_id list failed."
            )

    def _get_electric_balance(self):
        try:
            balance = self._driver.find_element(By.CLASS_NAME, "num").text
            balance_text = self._driver.find_element(By.CLASS_NAME, "amttxt").text
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
            self._logger.error("The yearly data get failed %s", e)
            return None, None

        # get data
        try:
            yearly_usage = self._visible_elem(
                By.XPATH, "//ul[@class='total']/li[1]/span"
            ).text
        except Exception as e:
            self._logger.error("The yearly_usage data get failed : %s", e)
            yearly_usage = None

        try:
            yearly_charge = self._visible_elem(
                By.XPATH, "//ul[@class='total']/li[2]/span"
            ).text
        except Exception as e:
            self._logger.error("The yearly_charge data get failed : %s", e)
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
            self._logger.error(f"The yesterday data get failed : {e}")
            return None, None

    def _get_month_usage(self):
        """获取每月用电量."""
        try:
            self._click_button(
                By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-first']"
            )
            if datetime.now().month == 1:
                self._click_button(
                    By.XPATH, '//*[@id="pane-first"]/div[1]/div/div[1]/div/div/input'
                )
                span_element = self._driver.find_element(
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
            for i in range(len(month_element)):
                month.append(month_element[i][0])
                usage.append(month_element[i][1])
                charge.append(month_element[i][2])
            return month, usage, charge
        except Exception as e:
            self._logger.error(f"The month data get failed : {e.args}")
            return None, None, None

    # 增加获取每日用电量的函数
    def _get_daily_usage_data(self):
        """储存指定天数的用电量"""
        retention_days = int(self._config.get("DATA_RETENTION_DAYS", 7))  # 默认值为7天
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
            self._logger.error(f"Unsupported retention days value: {retention_days}")
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
                self._logger.info(f"The electricity consumption of {usage} get nothing")
        return date, usages
