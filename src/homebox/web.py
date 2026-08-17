from pathlib import Path

from flask import Flask, render_template, request, send_file

from . import http_api


app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    wan_ip = http_api.get_wan_ip()
    if request.method == "POST":
        if request.form.get("new_wan_ip") == "yes":
            wan_ip = http_api.get_wan_ip(new=True)
        elif request.form.get("view_log_file") == "yes":
            data = log()
            if data is not None:
                return data
    return render_template("index.html", wan_ip=wan_ip)


@app.route("/log")
def log():
    filepath = Path.home() / "homebox" / "bandwidth.log"
    if filepath.is_file():
        return send_file(str(filepath), mimetype="text/plain")


def main():
    app.run(host="127.0.0.1", port=8000, debug=True)


if __name__ == "__main__":
    main()
