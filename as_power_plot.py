#!/usr/bin/env python
#
# File: $Id$
#
"""
Continuously plot powerwall and solar roof data via matplotlib.
"""

# system imports
#
import os
import json
from pathlib import Path
import pprint
from datetime import datetime

# 3rd party modules
#
import pytz
from tesla_powerwall import Powerwall, MeterType
from tesla_powerwall.error import PowerwallUnreachableError

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.dates as mdates

# Project modules
#
from utils import get_hvac_client


TIMEZONE = pytz.timezone("US/Pacific")
NUM_SAMPLE_HORIZON = 1440  # 1 day at 1 minute between samples
PLOT_INTERVAL = 1000 * 60  # once a minute
HISTORY_FILE_DIR = Path("~/Sync/misc/powerwall_data").expanduser()
LAST_DAY_FILE = HISTORY_FILE_DIR / "last_24h.json"
HISTORY_FILE_FMT = "%Y-%m-%d_data.json"
DATE_FMT = "%Y-%m-%d_%H:%M:%S%z"
PP = pprint.PrettyPrinter(indent=2)
VAULT_SECRETS_PATH = os.getenev("VAULT_SECRETS_PATH")
POWERWALL_HOST = os.getenv("BACKUP_GW_ADDR")


####################################################################
#
def get_login_credentials():
    """
    Go to vault, get our login credentials and return a dict properly
    formatted for authenticating with the web site.
    """
    hvac_client = get_hvac_client()
    login_credentials = hvac_client.secrets.kv.v1.read_secret(
        VAULT_SECRETS_PATH
    )
    return login_credentials["data"]


####################################################################
#
def draw_plot(i, creds, ax, ax2, x_axis, meter_values, battery_pct):
    """
    Read values from the powerwall and plot them vs time.

    Keyword Arguments:
    i            --
    creds        --
    x_axis       --
    meter_values --
    battery_pct  --
    """
    powerwall = Powerwall(POWERWALL_HOST)
    try:
        powerwall.detect_and_pin_version()
    except PowerwallUnreachableError as e:
        print(e)
        return
    _ = powerwall.login(creds["password"])

    # Get new values..
    now = datetime.now(tz=pytz.utc)
    now = now.astimezone(TIMEZONE)
    x_axis.append(now)
    battery_pct.append(powerwall.get_charge())
    meters = powerwall.get_meters()
    for meter_type in MeterType:
        meter = meters.get_meter(meter_type)
        meter_type = meter_type.value
        meter_values[meter_type].append(meter.instant_power)

    # Truncate at our horizon for number of samples to keep
    #
    x_axis = x_axis[-NUM_SAMPLE_HORIZON:]
    battery_pct = battery_pct[-NUM_SAMPLE_HORIZON:]
    for meter_type in MeterType:
        meter_type = meter_type.value
        meter_values[meter_type] = meter_values[meter_type][
            -NUM_SAMPLE_HORIZON:
        ]

    # Write our file out to both by-date and last 24h files as json
    #
    data = {
        "meter_values": meter_values,
        "x_axis": [x.strftime(DATE_FMT) for x in x_axis],
        "battery_pct": battery_pct,
    }
    try:
        with open(LAST_DAY_FILE, "w") as f:
            json.dump(data, f)
        today_file = HISTORY_FILE_DIR / now.strftime(HISTORY_FILE_FMT)
        with open(today_file, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

    ax.clear()
    ax2.clear()

    legend_lines = []
    legend_names = []
    for meter_type in MeterType:
        meter_type = meter_type.value
        (l,) = ax.plot(x_axis, meter_values[meter_type])
        legend_lines.append(l)
        legend_names.append(meter_type)

    ax.set_ylabel("Wh")
    ax.grid(which="major", axis="both", color="grey")

    (l,) = ax2.plot(x_axis, battery_pct, color="lightblue", linestyle="dashed")
    legend_lines.append(l)
    legend_names.append("Battery % Chg")
    ax2.set_ylabel("% Chg")
    ax2.grid(which="major", color="lightblue", linestyle="dotted")

    hours = mdates.HourLocator(interval=1)
    h_fmt = mdates.DateFormatter("%H", tz=now.tzinfo)
    qtr_hr = mdates.MinuteLocator(byminute=[15, 30, 45], interval=1)

    ax.legend(legend_lines, legend_names, loc="best")
    ax.xaxis.set_major_formatter(h_fmt)
    ax.xaxis.set_major_locator(hours)
    ax.xaxis.set_minor_locator(qtr_hr)

    plt.title("AS Powerwall")


#############################################################################
#
def main():
    """
    Get credentials. Connection to powerwall. In matplotlib animation
    loop get data from powerwall and plot.
    """
    creds = get_login_credentials()

    # Load saved data if it exists
    #
    if LAST_DAY_FILE.exists():
        with open(LAST_DAY_FILE, "r") as f:
            data = json.load(f)
            meter_values = data["meter_values"]
            x_axis = [datetime.strptime(x, DATE_FMT) for x in data["x_axis"]]
            battery_pct = data["battery_pct"]
    else:
        meter_values = {}
        for meter_type in MeterType:
            meter_type = meter_type.value
            meter_values[meter_type] = []
        battery_pct = []  # battery charge percent plotting on Y2 axis
        x_axis = []  # Timestamps plotted on X axis

    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    ax2 = ax.twinx()

    _ = animation.FuncAnimation(
        fig,
        draw_plot,
        fargs=(creds, ax, ax2, x_axis, meter_values, battery_pct),
        interval=PLOT_INTERVAL,
    )
    plt.show()


############################################################################
############################################################################
#
# Here is where it all starts
#
if __name__ == "__main__":
    main()
#
############################################################################
############################################################################
