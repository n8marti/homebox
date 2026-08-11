import logging
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
SERVER_IP = "192.168.1.1"
SERVER_URL = f"{PROTOCOL}://{SERVER_IP}"
logger = logging.getLogger()


def close_mbox(driver):
    """Close message box by running the CloseDlg() script."""
    logger.debug("Closing mbox.")
    driver.execute_script("CloseDlg();")
    # ol = wait_for_id(driver, "ol")
    # logger.debug(f"overlay: {ol.get_attribute('style')=}")


def ensure_mbox_dismissed(driver):
    # Get overlay.
    ol = wait_for_id(driver, "ol")
    # Wait for display value to be set.
    ol_display = get_style_data(ol).get("display")
    while ol_display is None:
        sleep(0.1)
        ol_display = get_style_data(ol).get("display")
    # Close mbox if overlay is blocking.
    while ol_display == "block":
        close_mbox(driver)
        sleep(0.1)
        ol_display = get_style_data(ol).get("display")


def get_style_data(elem):
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


def get_wan_ip(driver):
    """Get WAN IP from LTE WAN page."""
    load_lte_wan_page(driver)
    wan_ip_elem = driver.find_element(By.ID, "txtPdpIpv4Addr")
    # Wait for IP to be displayed.
    while wan_ip_elem.text in ("", "N/A"):
        sleep(0.1)
        load_lte_wan_page(driver)
        wan_ip_elem = driver.find_element(By.ID, "txtPdpIpv4Addr")
    return wan_ip_elem.text


def go_home(driver):
    """Request the Home page.
    WARNING: This does not ensure that the page is loaded.
    """
    driver.execute_script("createMenu(arguments[0]);", 1)


def load_lte_wan_page(driver):
    ensure_mbox_dismissed(driver)
    open_menu_internet(driver)
    driver.execute_script("displayForm('mApnInfo');")
    wait_for_id(driver, "txtPdpIpv4Addr")


def load_apn_management(driver):
    """Load APN Management page from Home."""
    open_menu_internet(driver)
    driver.execute_script("displayForm('mProfileManagement');")


def load_index(driver):
    """Load `index.html` page."""
    try:
        driver.get(f"{SERVER_URL}/index.html")
    except WebDriverException:
        logger.warning("Web page unavailable.")


def login_admin(driver):
    """Login as `admin` from `index.html`."""
    username_field = driver.find_element(By.ID, "tbarouter_username")
    username_field.send_keys("admin")
    password_field = driver.find_element(By.ID, "tbarouter_password")
    password_field.send_keys(Path("secret.txt").read_text().rstrip('\n'))
    driver.execute_script("Login();")


def open_menu_internet(driver):
    """Open Internet menu."""
    # internet_element = wait_for_id(driver, "2")
    # internet_element.click()
    driver.execute_script("ToInternet();")


def set_new_ip(window=False):
    wan_ip = None

    options = Options()
    if not window:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(executable_path="/snap/bin/chromium.chromedriver")
    with webdriver.Chrome(options=options, service=service) as wd:
        logger.debug("Loading index.html.")
        load_index(wd)

        logger.debug("Logging in.")
        login_admin(wd)

        logger.debug("Dismissing notification box if present.")
        ensure_mbox_dismissed(wd)

        # Get WAN IP.
        logger.debug("Getting WAN IP.")
        wan_ip = get_wan_ip(wd)

        logger.debug("Loading APN Management page.")
        # Open Internet menu & toggle APN.
        load_apn_management(wd)

        logger.debug("Toggling APN.")
        new_apn = toggle_apn(wd, wan_ip)

        # Get new WAN IP.
        logger.debug("Getting new WAN IP.")
        new_ip = get_wan_ip(wd)
        logger.info(f"New APN: {new_apn} ({new_ip})")
        return new_ip


def toggle_apn(driver, old_wan_ip):
    # Wait for Save button before messing with APN.
    save_button = wait_for_id(driver, "lt_btnSave")
    # Get current APN.
    apn_selector = Select(wait_for_id(driver, "selAPN1"))
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
    logger.debug(f"{driver.find_element(By.ID, "ol").get_attribute('style')=}")
    save_button.click()

    # Wait for "Saving..." dialog to disappear.
    logger.info("Saving config...")
    wait_elem = wait_for_id(driver, "PleaseWait")
    wait_mbox = driver.execute_script("return arguments[0].parentNode;", wait_elem)
    wait_mbox_display = get_style_data(wait_mbox).get("display")
    while wait_mbox_display == "block":
        sleep(0.1)
        wait_mbox_display = get_style_data(wait_mbox).get("display")
    ensure_mbox_dismissed(driver)
    return new_apn


def wait_for_id(driver, elem_id):
    elem = None
    ct = 0
    dt = 0.1
    while elem is None:
        try:
            elem = driver.find_element(By.ID, elem_id)
            break
        except NoSuchElementException:
            pass
        sleep(dt)
        ct += 1

    return elem
