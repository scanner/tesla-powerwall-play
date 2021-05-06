#!/usr/bin/env python
#
# File: $Id$
#
"""
Connect to the Tesla Backup Gateway 2.
Collect some statistics.
Send them to influxdb.

Usage:
  powerwall_to_influxdb.py [--debug]

Options:
  --version
  -h, --help        Show this text and exit
  --debug           Output debugging around http, redirects, and responses
"""

# system imports
#
import os

# 3rd party imports
#
from tesla_powerwall import Powerwall, MeterType
from tesla_powerwall.error import PowerwallUnreachableError
import hvac

from .utils import get_hvac_client, INFLUXDB_CREDS_PATH

BG_GATEWAY_SECRETS_PATH = os.getenv("VAULT_SECRETS_PATH")
BG_GATEWAY_HOST = os.getenv("BACKUP_GW_ADDR")

# Which keys in a meter do we care about..
#
METER_KEYS = (
    "energy_exported",
    "energy_imported",
    "instant_apparent_power",
    "instant_average_voltage",
    "instant_power",
    "instant_reactive_power",
    "instant_total_current",
)
#############################################################################
#
def main():
    """
    Get credentials from vault. Poke backup gateway. Push stats to influxdb
    """
    vault = get_hvac_client()
    bg_creds = vault.secrets.kv.v1.read_secret(BG_GATEWAY_SECRETS_PATH)
    influxdb_creds = vault.secrets.kv.v1.read_secret(INFLUXDB_CREDS_PATH)

    powerwall = Powerwall(BG_GATEWAY_HOST)
    try:
        powerwall.detect_and_pin_version()
    except PowerwallUnreachableError as e:
        print(e)
        return

    _ = powerwall.login(bg_creds["email"], bg_creds["password"])
    battery_pct_charge = powerwall.get_charge()
    site_info = powerwall.get_site_info()
    meters = power_wall.get_meters()
    meter_data = meters.response
    for (meter, data) in meters.items():
        pass
    return


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
