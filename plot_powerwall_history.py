#!/usr/bin/env python
#
# File: $Id$
#
"""
Get the day history from the Tesla remote API and plot it using matplotlib
"""

# system imports
#
# system imports
#
import os
import asyncio
import pprint
import time
from pathlib import Path
from collections import defaultdict
from datetime import datetime, date, timedelta

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import hvac
from tesla_api import TeslaApiClient

COLORS = ["red", "blue", "green", "yellow", "orange", "cyan", "magenta"]
TESLA_API_TOKEN_FILE = Path("~/.tesla-api-token").expanduser()
VAULT_TOKEN_FILE = Path("~/.vault-token").expanduser()
VAULT_SECRETS_PATH = os.getenv('VAULT_SECRETS_PATH')

CHARTS = [
    "battery_power",
    # "generator_power",
    "grid_power",
    # "grid_services_power",
    "solar_power",
]


####################################################################
#
def get_hvac_client():
    """
    Return a connection to our hashicorp vault server so we can get login
    credentials for the site we are going to download things from.

    Raises a RuntimeError if we are not able to authenticate to the vault
    server.
    """
    if "VAULT_ADDR" not in os.environ:
        raise RuntimeError('"VAULT_ADDR" not in environment')
    vault_addr = os.environ["VAULT_ADDR"]
    if "VAULT_TOKEN" in os.environ:
        vault_token = os.environ["VAULT_TOKEN"]
    elif VAULT_TOKEN_FILE.exists():
        with open(VAULT_TOKEN_FILE) as f:
            vault_token = f.read()

    hvac_client = hvac.Client(url=vault_addr, token=vault_token)
    if not hvac_client.is_authenticated():
        raise RuntimeError(f"Can not authenticate with token to {vault_addr}")
    return hvac_client


####################################################################
#
def get_login_credentials(hvac_client):
    """
    Go to vault, get our login credentials and return a dict properly
    formatted for authenticating with the web site.
    """
    login_credentials = hvac_client.secrets.kv.v1.read_secret(
        VAULT_SECRETS_PATH
    )
    return login_credentials["data"]


#############################################################################
#
async def save_token(token):
    """
    Save the oauth token for re-use instead of logging in again.  We
    store it in the vault cubbyhole secrets engine.
    """
    os.umask(0)
    with open(
        os.open(TESLA_API_TOKEN_FILE, os.O_CREAT | os.O_WRONLY, 0o600), "w"
    ) as fh:
        fh.write(token)


####################################################################
#
def read_token():
    """
    Reads the token from the token file. Returns None if file does not
    exist.
    """
    if not TESLA_API_TOKEN_FILE.exists():
        return None
    return open(TESLA_API_TOKEN_FILE, "r").read()


####################################################################
#
def matplotlib_ts(ts):
    """
    Use matplotlib to graph the data

    Keyword Arguments:
    ts -- list of dicts. Each dict contains the keys: 'battery_power',
          'generator_power', 'grid_power', 'grid_services_power',
          'solar_power', 'timestamp'

    'timestamp' is of the format: : '2020-10-25T00:00:00-07:00'
    All of the other values are floats (presummably in watts?)
    """
    min_y = 0
    max_y = 0

    timestamps = []
    series = defaultdict(list)

    for ts_d in ts:
        # timestamps.append(f"\"{ts_d['timestamp'][11:16]}\"")
        dt = datetime.strptime(ts_d["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        timestamps.append(dt)
        for c in CHARTS:
            min_y = min(min_y, ts_d[c])
            max_y = max(max_y, ts_d[c])
            series[c].append(ts_d[c])

    hours = mdates.HourLocator(interval=1)
    h_fmt = mdates.DateFormatter("%H", tz=timestamps[0].tzinfo)

    plt.gca().xaxis.set_major_formatter(h_fmt)
    plt.gca().xaxis.set_major_locator(hours)

    for c in CHARTS:
        plt.plot(timestamps, series[c], label=c)
    plt.xlabel("Time")
    plt.ylabel("Wh")
    plt.title(f"Tesla Power Gateway starting at {timestamps[0]}")
    plt.legend()
    plt.grid()
    plt.show()


#############################################################################
#
async def main():
    pp = pprint.PrettyPrinter(indent=2)
    email = password = None
    token = read_token()
    if token is None:
        hvac_client = get_hvac_client()
        creds = get_login_credentials(hvac_client)
        email = creds["username"]
        password = creds["password"]

    async with TeslaApiClient(
        email, password, token, on_new_token=save_token
    ) as client:
        energy_sites = await client.list_energy_sites()
        print(f"Number of energy sites = {len(energy_sites)}")

        # We only expect there to be a single site for our home
        # (Apricot Systematic)
        #
        assert len(energy_sites) == 1
        site_as01 = energy_sites[0]
        reserve = await site_as01.get_backup_reserve_percent()
        print(f"Backup reserve percent = {reserve}")
        operating_mode = await site_as01.get_operating_mode()
        print(f"Operating mode: {operating_mode}")
        version = await site_as01.get_version()
        print(f"Version: {version}")
        battery_count = await site_as01.get_battery_count()
        print(f"Battery count: {battery_count}")
        live_status = await site_as01.get_energy_site_live_status()
        print(f"Site live status:\n{pp.pformat(live_status)}")
        while True:
            live_status = await site_as01.get_energy_site_live_status()
            print(
                f"{datetime.now()} Battery charge: {live_status['percentage_charged']}%"
            )
            history_power = (
                await site_as01.get_energy_site_calendar_history_data(
                    kind="power", period="day"
                )
            )
            matplotlib_ts(history_power["time_series"])


############################################################################
############################################################################
#
# Here is where it all starts
#
if __name__ == "__main__":
    asyncio.run(main())
#
############################################################################
############################################################################
