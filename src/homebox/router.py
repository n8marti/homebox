import logging
import sys
from pathlib import Path
from time import sleep

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

APNS = ("MTN_internet", "MTN_mobile")
PROTOCOL = "http"
SECRETS_DIRS = [".", "~"]
SERVER_IP = "192.168.1.1"
SERVER_URL = f"{PROTOCOL}://{SERVER_IP}"
logger = logging.getLogger()


class HomeboxMixin:
    """Browser-agnostic functionality mix-in."""

    def load_apn_management(self):
        """Load APN Management page from Home."""
        self.load_menu_internet()
        self.execute_script("displayForm('mProfileManagement');")

    def load_index(self):
        """Load `index.html` page."""
        try:
            self.get(f"{SERVER_URL}/index.html")
        except WebDriverException as e:
            logger.critical("Web page unavailable.")
            logger.critical(e)
        # FIXME: Something is requiring a wait here when using Epiphany.
        # self._wait_for_id("tbarouter_username")
        # sleep(5)

    def load_lte_wan_page(self):
        """Open LTE WAN page."""
        self._ensure_mbox_dismissed()
        self.load_menu_internet()
        self.execute_script("displayForm('mApnInfo');")
        self._wait_for_id("txtPdpIpv4Addr")

    def load_menu_internet(self):
        """Open Internet menu."""
        self.execute_script("ToInternet();")

    def login(self):
        logger.debug("Loading index.html.")
        self.load_index()
        logger.debug("Logging in.")
        self._login_admin()
        logger.debug("Dismissing notification box if present.")
        self._ensure_mbox_dismissed()

    def get_wan_ip(self):
        """Get WAN IP via the LTE WAN page."""
        self.load_lte_wan_page()
        wan_ip_elem = self.find_element(By.ID, "txtPdpIpv4Addr")
        # Wait for IP to be displayed.
        while wan_ip_elem.text in ("", "N/A"):
            sleep(0.1)
            self.load_lte_wan_page()
            wan_ip_elem = self.find_element(By.ID, "txtPdpIpv4Addr")
        return wan_ip_elem.text

    def toggle_apn(self, old_wan_ip):
        # Wait for Save button before messing with APN.
        save_button = self._wait_for_id("lt_btnSave")
        # Get current APN.
        apn_selector = Select(self._wait_for_id("selAPN1"))
        apn = apn_selector.first_selected_option.text
        logger.info(f"Current APN: {apn} ({old_wan_ip})")

        # Toggle APN.
        # NOTE: It's possible that the APN could be set to any of the 4 options,
        # but we will only worry about two here.
        if apn != APNS[0]:
            new_apn = APNS[0]
        else:
            new_apn = APNS[1]
        apn_selector.select_by_visible_text(new_apn)
        logger.debug(f"{self.find_element(By.ID, "ol").get_attribute('style')=}")
        save_button.click()

        # Wait for "Saving..." dialog to disappear.
        logger.info("Saving config...")
        wait_elem = self._wait_for_id("PleaseWait")
        wait_mbox = self.execute_script("return arguments[0].parentNode;", wait_elem)
        wait_mbox_display = self._style_data(wait_mbox).get("display")
        while wait_mbox_display == "block":
            sleep(0.1)
            wait_mbox_display = self._style_data(wait_mbox).get("display")
        self._ensure_mbox_dismissed()
        return new_apn

    def _close_mbox(self):
        """Close message box by running the CloseDlg() script."""
        logger.debug("Closing mbox.")
        self.execute_script("CloseDlg();")

    def _ensure_mbox_dismissed(self):
        # Get overlay.
        ol = self._wait_for_id("ol")
        # Wait for display value to be set.
        ol_display = self._style_data(ol).get("display")
        while ol_display is None:
            sleep(0.1)
            ol_display = self._style_data(ol).get("display")
        # Close mbox if overlay is blocking.
        while ol_display == "block":
            self._close_mbox()
            sleep(0.1)
            ol_display = self._style_data(ol).get("display")

    def _homebox_txt(self):
        """Find homebox.txt, which contains the login password."""
        for d in SECRETS_DIRS:
            p = Path(d).resolve()
            f = p / "homebox.txt"
            if f.is_file():
                return f

    def _login_admin(self):
        """Login as `admin` from `index.html`."""
        username_field = self.find_element(By.ID, "tbarouter_username")
        username_field.send_keys("admin")
        password_field = self.find_element(By.ID, "tbarouter_password")
        homebox_txt = self._homebox_txt()
        if homebox_txt is None:
            logger.critical("homebox.txt not found; can't login!")
            sys.exit(1)
        password_field.send_keys(homebox_txt.read_text().rstrip('\n'))
        self.execute_script("Login();")

    def _style_data(self, elem):
        data = {}
        style_raw = elem.get_attribute("style")
        pairs = style_raw.split(";")
        for pair in pairs:
            try:
                k, v = pair.split(":")
                data[k.strip()] = v.strip()
            except ValueError:
                pass
        return data

    def _wait_for_id(self, elem_id):
        elem = None
        ct = 0
        dt = 0.1
        while elem is None:
            try:
                elem = self.find_element(By.ID, elem_id)
                break
            except NoSuchElementException:
                pass
            sleep(dt)
            ct += 1
        return elem


class ChromiumSnap(webdriver.Chrome, HomeboxMixin):
    """Preconfigure Chromium Snap webdriver."""

    def __init__(self, window=False, **kwargs):
        options = Options()
        if not window:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        service = Service(executable_path="/snap/bin/chromium.chromedriver")
        super().__init__(options=options, service=service)


class Epiphany(webdriver.WebKitGTK, HomeboxMixin):
    """Preconfigure Epiphany (GNOME Web) webdriver."""

    def __init__(self, window=False, **kwargs):
        options = webdriver.WebKitGTKOptions()
        options.binary_location = "/usr/bin/epiphany"
        options.add_argument("--automation-mode")
        options.set_capability("browserName", "Epiphany")
        super().__init__(options=options)



def get_wan_ip(window=False):
    """Return the WAN IP address from the MTN Homebox.
    This is a comprehensive function that assumes the user is not logged in.
    """
    # with Epiphany(window=window) as wd:
    with ChromiumSnap(window=window) as wd:
        wd.login()
        return wd.get_wan_ip()


def set_new_ip(window=False):
    with ChromiumSnap(window=window) as wd:
        logger.debug("Loading index.html.")
        wd.load_index()

        logger.debug("Logging in.")
        wd._login_admin()

        logger.debug("Dismissing notification box if present.")
        wd._ensure_mbox_dismissed()

        # Get WAN IP.
        logger.debug("Getting WAN IP.")
        wan_ip = wd.get_wan_ip()

        logger.debug("Loading APN Management page.")
        # Open Internet menu & toggle APN.
        wd.load_apn_management()

        logger.debug("Toggling APN.")
        new_apn = wd.toggle_apn(wan_ip)

        # Get new WAN IP.
        logger.debug("Getting new WAN IP.")
        new_ip = wd.get_wan_ip()
        logger.info(f"New APN: {new_apn} ({new_ip})")
        return new_ip
