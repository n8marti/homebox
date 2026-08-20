import logging
import threading

import tkinter as tk
from tkinter import font

from . import http_api

logger = logging.getLogger()


class GuiApp(tk.Tk):
    MTN_BLUE = "#1A5FB4"
    MTN_GOLD = "#F5C211"
    MTN_GRAY = "#C0BFBC"
    MTN_WHITE = "#F6F5F4"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Homebox Control")
        self.geometry("640x400")  # 8:5 ratio
        self.configure(bg=self.MTN_GRAY)

        self.win = tk.Frame(self, bg=self.MTN_GOLD, padx=20, pady=20)
        self.win.place(relx=0.5, rely=0.5, anchor="c")
        self.defaultfont = font.nametofont("TkDefaultFont")
        self.defaultfont["size"] = 12
        self.monofont = font.nametofont("TkFixedFont")
        self.monofont["size"] = 11
        self.wan_ip = tk.StringVar()
        self.apn_profile = tk.StringVar()
        wan_txt = tk.Label(
            self.win,
            text="WAN IP address:",
            justify="left",
            bg=self.MTN_GOLD
        )
        wan_txt.grid(row=0, column=0, sticky="w")
        wan_val = tk.Label(
            self.win,
            textvariable=self.wan_ip,
            bg=self.MTN_GOLD,
            font=self.monofont
        )
        wan_val.grid(row=0, column=1, sticky="e", padx=(5,0))
        apn_txt = tk.Label(
            self.win,
            text="APN Profile:",
            justify="left",
            bg=self.MTN_GOLD
        )
        apn_txt.grid(row=1, column=0, sticky="w")
        apn_val = tk.Label(
            self.win,
            textvariable=self.apn_profile,
            bg=self.MTN_GOLD,
            font=self.monofont
        )
        apn_val.grid(row=1, column=1, sticky="e", padx=(0,5))
        wan_btn = tk.Button(
            self.win,
            text="Get new WAN IP",
            command=self.new_wan_ip
        )
        wan_btn.grid(row=2, column=0, columnspan=2)

        self.wan_ip_str = None
        self.get_wan_ip()

    def get_wan_ip(self):
        logger.debug("Called self.get_wan_ip()")
        thread = HCThread(http_api.get_wan_ip)
        logger.debug(f"Starting thread: {thread}")
        thread.start()
        self._monitor(thread, self._parse_wan_ip_str, cb_args=(thread,))

    def new_wan_ip(self):
        # thread = HCThread(http_api.get_wan_ip, kwargs={"new": True})
        import time
        thread = HCThread(time.sleep, args=(15))
        thread.start()
        self._monitor(thread, self.wan_var)

    def run(self):
        self.mainloop()

    def _monitor(self, thread, callback, cb_args=None, cb_kwargs=None):
        if thread.is_alive():
            logger.debug(f"Waiting on {thread}")
            self.after(100, lambda: self._monitor(thread, callback, cb_args, cb_kwargs))
        elif isinstance(callback, tk.Variable):  # tk Variable
            logger.debug(f"Setting tk.Variable: {callback} = {thread.result}")
            callback.set(thread.result)
        elif callable(callback):  # callback func
            if cb_args is None:
                cb_args = []
            if cb_kwargs is None:
                cb_kwargs = {}
            logger.debug(f"Calling callback: {callback.__name__}(*{cb_args=}, **{cb_kwargs=})")
            callback(*cb_args, **cb_kwargs)
        else:  # assume it's variable
            logger.debug(f"Setting Python variable: {callback} = {thread.result}")
            callback = thread.result

    def _parse_wan_ip_str(self, thread):
        self.wan_ip_str = thread.result
        if self.wan_ip_str is not None:
            wan_ip, _, apn_profile = self.wan_ip_str.split()
            self.wan_ip.set(wan_ip)
            self.apn_profile.set(apn_profile)


class HCThread(threading.Thread):
    def __init__(self, func: callable, args=None, kwargs=None):
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        super().__init__(args=args, kwargs=kwargs)
        self.func = func
        self.result = None

    def run(self):
        self.result = self.func(*self._args, **self._kwargs)


def run_gui(args):
    logger.debug("Called gui.run_gui()")
    GuiApp().run()
