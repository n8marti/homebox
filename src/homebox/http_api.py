import hashlib
import logging
import os
import random
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import requests
from dict2xml import DataSorter, dict2xml

from . import APNS, SERVER_URL

logger = logging.getLogger()


@dataclass
class AuthData:
    """Data that is needed for authentication."""

    SECRETS_DIRS = (".", os.getenv("HOME"))
    # variables
    authcnonce: str = None
    authcount: str = None
    ncount: int = 0
    _passwd: str = None
    # constants
    authqop: str = None
    authrealm: str = None
    nonce: str = None
    username: str = "admin"

    @property
    def ha1(self):
        return self._md5(f"{self.username}:{self.authrealm}:{self.passwd}")

    @property
    def passwd(self):
        if self._passwd is None:
            # Find homebox.txt, which contains the login password.
            homebox_txt = None
            for d in self.SECRETS_DIRS:
                p = Path(d).resolve()
                f = p / "homebox.txt"
                logger.debug(f"Checking for file: {f}")
                if f.is_file():
                    homebox_txt = f
                    break

            if homebox_txt is None:
                logger.critical("homebox.txt not found; can't login!")
                sys.exit(1)

            self._passwd = homebox_txt.read_text().rstrip("\n")
        return self._passwd

    def digest_res(self, request_type, ncount=None):
        salt = f"{random.randint(1, 100001)}{time.time()}"
        self.authcnonce = self._md5(salt)[:16]

        if ncount is None:
            count = self.ncount
            self.ncount += 1
        else:
            count = ncount
        temp = f"0000000000{self._hex(count)}"
        self.authcount = temp[len(temp) - 8:]
        logger.debug(f"{self.authcount=}")
        return self._md5(f"{self.ha1}:{self.nonce}:{self.authcount}:{self.authcnonce}:{self.authqop}:{self.ha2(request_type)}")

    def get_auth_header(self, request_type):
        data = {
            "username": self.username,
            "realm": self.authrealm,
            "nonce": self.nonce,
            "uri": "/cgi/xml_action.cgi",
            "response": self.digest_res(request_type, ncount=self.ncount),
            "qop": self.authqop,
            "nc": self.authcount,
            "cnonce": self.authcnonce,
        }
        header = "Digest "
        for i, (k, v) in enumerate(data.items()):
            header += f'{k}="{v}"'
            if i < len(data) - 1:
                header += ", "
        logger.debug(f"{header=}")
        return header

    def ha2(self, request_type):
        return self._md5(f"{request_type}:/cgi/xml_action.cgi")

    def _hex(self, d):
        return f"{d:X}"

    def _md5(self, s):
        return hashlib.md5(s.encode()).hexdigest()


class HomeboxSession(requests.Session):
    SERVER_URL = SERVER_URL

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.auth_data = AuthData()
        self.headers.update({
            # "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0",
            "Accept": "application/xml, text/xml, */*; q=0.01",
            "Accept-Language": "en-US,fr-FR;q=0.9,en;q=0.8",
            # "Accept-Encoding": "gzip, deflate",
            "X-Requested-With": "XMLHttpRequest",
            "Connection": "keep-alive",
            "Referer": f"{self.SERVER_URL}/index.html",
            # "Cookie": "CGISID=; projectConfig=0",
            # "Sec-GPC": "1",
        })
        self.logged_in = self.do_login()
        # logger.info(self.get_product_info())

    @property
    def active_apn_profile(self):
        xmlstr = self.post_xml("cm", "get_wan_configs")
        return self.xml_tag_value(xmlstr, "actived_profile1")

    @property
    def apn_number(self):
        try:
            num =int(self.xml_tag_value(self.post_xml("cm", "get_available_wan_num"), "num"))
        except ValueError:
            num = 1
        return num

    @property
    def apn_profile_names(self):
        names = self.xml_tag_value(self.post_xml("cm", "get_profile_info"), "profile_names").rstrip(",")
        return names.split(",")

    @property
    def connection_status(self):
        try:
            val = int(self.xml_tag_value(self.post_xml("cm", "get_link_context"), "connection_status"))
        except ValueError:
            val = None
        return val

    @property
    def wan_ip_and_apn(self):
        return f"{self.wan_ip} via {self.active_apn_profile}"

    @property
    def wan_ip(self):
        return self.xml_tag_value(self.post_xml("cm", "get_link_context"), "ipv4_ip")

    def do_login(self):
        # Get login params for setting self.auth_data values.
        login_param = self.get_auth_type()
        # logger.info(f"{login_param=}")
        if not login_param:
            return -1
        login_params = login_param.split()
        if login_params[0] == "Digest":
            self.auth_data.authrealm = login_params[1].split("=")[1].rstrip(",").strip('"')
            self.auth_data.nonce = login_params[2].split("=")[1].rstrip(",").strip('"')
            self.auth_data.authqop = login_params[3].split("=")[1].rstrip(",").strip('"')
        logger.debug(f"{self.auth_data.authrealm=}; {self.auth_data.nonce=}; {self.auth_data.authqop=}")

        # Attempt to authenticate.
        status = self._authentication()
        res = self._login_done(status)
        if res == "success":
            logger.info("Login successful.")
            return True

        logger.critical(f"Login unsuccessful; remaining attempts: {res}")
        return False

    def get_auth_type(self):
        headers = {
            "Expires": "-1",
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        }
        res = self.get(self._get_url("login.cgi"), headers=headers)
        return res.headers.get("WWW-Authenticate")

    def get_product_info(self):
        return self.post_xml("router", "router_get_product_info")

    def post_xml(self, obj_path, obj_method, control_map_in=None, type_=None):
        control_map = {
            "RGW/param/method": "call",
            "RGW/param/session": "000",
            "RGW/param/obj_path": obj_path,
            "RGW/param/obj_method": obj_method,
        }
        if control_map_in:
            control_map.update(control_map_in)

        xml_data = self._create_xml_docstr(control_map)
        if type_ != "clearInterval":
            # FIXME: This is a no-op.
            pass

        headers = {"Authorization": self.auth_data.get_auth_header("POST"), "csrftoken": "hfiehifejfklihefiuehflejhfueihfeuihfeui"}
        params = {"method": "set"}
        res = self.post(self._get_url("xml_action.cgi"), params=params, headers=headers, data=xml_data)
        logger.debug(f"{res.url=}")
        return res.text

    def toggle_apn(self, desired_apn=None):
        current_apn = self.active_apn_profile
        current_wan_ip = self.wan_ip
        logger.info(f"Current WAN IP: {current_wan_ip} via {current_apn}")
        profile_names = [p for p in self.apn_profile_names]

        # Toggle APN.
        if desired_apn is not None and desired_apn in profile_names:
            new_apn = desired_apn
            logger.info(f"Using user-requested APN profile: {new_apn}")
        else:
            if desired_apn is not None:
                logger.warning(f"Ingoring invalid APN profile: {desired_apn}")
            # Only toggle between two pre-determined values in this case.
            if current_apn != APNS[0]:
                new_apn = APNS[0]
            else:
                new_apn = APNS[1]
            logger.info(f"Using script-provided APN profile: {new_apn}")

        logger.debug(f"{self.apn_number=}")
        # Indicate which WAN APN is getting changed.
        j = 1
        # I don't think on this Homebox there will ever be more than 1 WAN, but
        # this is a failsafe, just in case.
        if self.apn_number > 1:
            logger.critical("More than 1 APN is active; APN must be changed manually.")
            return None

        control_map = {
            "RGW/wan/profile_name": new_apn,
            "RGW/wan/wan_type": f"wan{j}"
        }
        logger.debug(f"{control_map=}")
        xmlstr = self.post_xml("cm", "set_wan_info", control_map_in=control_map)
        if self.xml_tag_value(xmlstr, "setting_response") == "OK":
            self._wait_for_connection()
            return self.wan_ip
        logger.critical("Failed to set new APN and get new wan IP address.")
        return None


    def xml_tag_value(self, xmlstr, tag):
        root = ET.fromstring(xmlstr)
        ET.indent(root, space=" ")
        logger.debug(f"Looking for tag: {tag}")
        logger.debug(ET.tostring(root).decode())
        elem = root.find(f".//{tag}")
        if elem is not None:
            return elem.text

    def _authentication(self):
        params = {
            "Action": "Digest",
            "username": self.auth_data.username,
            "realm": self.auth_data.authrealm,
            "nonce": self.auth_data.nonce,
            "response": self.auth_data.digest_res("GET"),
            "qop": self.auth_data.authqop,
            "cnonce": self.auth_data.authcnonce,
            "nc": self.auth_data.authcount,
            "temp": "marvell",
        }
        logger.debug(f"authentication {params=}")
        auth_header = self.auth_data.get_auth_header("GET")
        logger.debug(f"{auth_header=}")

        headers = {
            "Authorization": auth_header,
            "Expires": "-1",
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        }
        res = self.get(self._get_url("login.cgi"), params=params, headers=headers)
        if res.status_code != 200:
            logger.critical(f"Authentication failed: {res.status_code} - {res.reason}")
        return res.headers.get("WWW-Authenticate")

    def _create_xml_docstr(self, control_map):
        logger.debug(f"{control_map=}")
        # Convert slash-separated parts to nested dict nodes.
        pure_dict = {}
        for k, v in control_map.items():
            tags = k.split("/")
            for i, tag in enumerate(tags):
                # logger.debug(f"{i}:{tag}")
                if i == 0:
                    d = pure_dict
                else:
                    d = d.get(tags[i - 1])
                # logger.debug(f"{d=}")
                if tag not in d:
                    if i == len(tags) - 1:
                        d[tag] = v
                    else:
                        d[tag] = {}
                # logger.debug(f"{pure_dict=}")
        xmlstr = dict2xml(pure_dict, newlines=False, data_sorter=DataSorter.never())
        # Manually add XML declaration.
        xmlstr = f'<?xml version="1.0" encoding="US-ASCII"?>{xmlstr}'
        logger.debug(f"{xmlstr=}")
        return xmlstr

    def _get_url(self, filepath):
        return f"{self.SERVER_URL}/{filepath}"

    def _login_done(self, urldata):
        if urldata:
            res = urldata.split(",")
            status = res[0]
            status = int(status.split("=")[1])
            if status == 0:
                return "success"
            elif status == 5:
                left_time = res[1].split("=")[1]
                left_times = 5 - status
                return f"{left_times};{left_time}"
            else:
                left_times = 5 - status
                return left_times

    def _wait_for_connection(self):
        timeout = 10  # seconds
        dt = 0.5
        ct_max = timeout / dt
        ct = 0
        while self.connection_status != 1:
            if ct >= ct_max:
                logger.warning("Timed out waiting for connection")
                break
            time.sleep(dt)
            ct += 1


def get_wan_ip(apn=None, new=False):
    with HomeboxSession() as session:
        if not session.logged_in:
            logger.critical("Login unsuccessful.")
            return False

        if new is True:
            session.toggle_apn(desired_apn=apn)
        return session.wan_ip_and_apn
