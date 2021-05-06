#!/usr/bin/env python
#
# File: $Id$
#
"""
Try using the tesla-api instead of talking to the powerwall directly
"""

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
VAULT_SECRETS_PATH = os.getenev("VAULT_SECRETS_PATH")

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
def tg_plot_history_power(ts):
    """
    Plot the timeseries data using termgraph

    Keyword Arguments:

    ts -- list of dicts. Each dict contains the keys: 'battery_power',
          'generator_power', 'grid_power', 'grid_services_power',
          'solar_power', 'timestamp'

    'timestamp' is of the format: : '2020-10-25T00:00:00-07:00'
    All of the other values are floats (presummably in watts?)
    """
    # Open our output data file we are generating for termgraph and
    # define in it what data columns we are writing.
    #
    with open("termgraph.dat", "w") as fh:
        fh.write(f"# Tesla energy graph starting {ts[0]['timestamp']}\n")
        fh.write(f"@ {','.join(CHARTS)}\n")

        for ts_d in ts:
            # We generate one row at a time. The row label, then the data
            # in the same order as we wrote in the header above.
            #
            row = []
            row.append(ts_d["timestamp"][11:16])
            for c in CHARTS:
                row.append(str(abs(ts_d[c])))
            fh.write(",".join(row))
            fh.write("\n")


####################################################################
#
def write_blessed_datafile(ts):
    """
    Write a javascript file that can be used by `blessed` to write an
    ascii chart

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
        timestamps.append(f"\"{ts_d['timestamp'][11:16]}\"")
        for c in CHARTS:
            min_y = min(min_y, ts_d[c])
            max_y = max(max_y, ts_d[c])
            series[c].append(str(ts_d[c]))

    # Open our output data file we are generating for termgraph and
    # define in it what data columns we are writing.
    #
    with open("tesla-blessed.js", "w") as fh:
        fh.write(
            f"""
var blessed = require('blessed')
, contrib = require('../index')
, screen = blessed.screen()
, line = contrib.line(
      {{ width: 164
      , height: 24
      , xPadding: 5
      , minY: {min_y}
      , showLegend: true
      , legend: {{width: 12}}
      , wholeNumbersOnly: false // true=do not show fraction in y axis
      , label: 'Power data'}});
"""
        )
        series_names = []
        for idx, c in enumerate(CHARTS):
            series_name = f"series{idx}"
            series_names.append(series_name)
            fh.write(f"var {series_name} = {{\n")
            fh.write(f"      title: '{c}',\n")
            fh.write(f"      x: [{','.join(timestamps)}],\n")
            fh.write(f"      y: [{','.join(series[c])}],\n")
            fh.write(f"      style: {{line: '{COLORS[idx]}'}}\n")
            fh.write("   };\n")
        fh.write("screen.append(line); //must append before setting data\n")
        set_data = ", ".join(series_names)
        fh.write(f"line.setData([{set_data}]);\n")
        fh.write(
            """
screen.key(['escape', 'q', 'C-c'], function(ch, key) {
  return process.exit(0);
});

screen.render();
"""
        )


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

        # history_energy = await site_as01.get_energy_site_calendar_history_data(
        #     kind="energy", period="lifetime"
        # )
        # print(f"History energy: \n{pp.pformat(history_energy)}")

        # history_sc = await site_as01.get_energy_site_calendar_history_data(
        #     kind="self_consumption", period="lifetime"
        # )
        # print(f"History self consumption:\n{pp.pformat(history_sc)}")

        while True:
            live_status = await site_as01.get_energy_site_live_status()
            print(f"Site live status:\n{pp.pformat(live_status)}")
            time.sleep(150)

        # tg_plot_history_power(history_power["time_series"])
        # write_blessed_datafile(history_power["time_series"])

        # print("Increment backup reserve percent")
        # await energy_sites[0].set_backup_reserve_percent(reserve + 1)


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
