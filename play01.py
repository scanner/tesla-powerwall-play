#!/usr/bin/env python
#
# File: $Id$
#
"""
Test poking at the PowerWall
"""
import os
from time import sleep
from pathlib import Path
import pprint

from tesla_powerwall import Powerwall, MeterType
from tesla_powerwall.error import PowerwallUnreachableError
import hvac

VAULT_TOKEN_FILE = Path("~/.vault-token").expanduser()
VAULT_SECRETS_PATH = os.getenev("VAULT_SECRETS_PATH")
POWERWALL_HOST = os.getenv("BACKUP_GW_ADDR")


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


#############################################################################
#
def main():
    pp = pprint.PrettyPrinter(indent=2)

    creds = get_login_credentials()

    power_wall = Powerwall(POWERWALL_HOST)
    try:
        power_wall.detect_and_pin_version()
    except PowerwallUnreachableError as e:
        print(e)
        return

    print(
        "Detected and pinned version: {}".format(
            power_wall.get_pinned_version()
        )
    )
    _ = power_wall.login(creds["password"])
    print("Current charge: {}".format(power_wall.get_charge()))
    print("Device Type: {}".format(power_wall.get_device_type()))

    print(f"Authenticated: {power_wall.get_api().is_authenticated()}")

    print(f"Sitemaster: {power_wall.get_sitemaster()}")
    print(f"Grid status: {power_wall.get_grid_status()}")
    print(f"Grid service activer: {power_wall.is_grid_services_active()}")
    site_info = power_wall.get_site_info()
    print(f"Site info: {pp.pformat(site_info.response)}")
    status = power_wall.get_status()
    print(f"Status: {pp.pformat(status.response)}")

    print(f"Device type: {power_wall.get_device_type()}")
    print(f"Serial numbers: {power_wall.get_serial_numbers()}")
    print(f"Version: {power_wall.get_version()}")

    # # XXX These methods need auth:
    print(f"Operation mode: {power_wall.get_operation_mode()}")
    # print(f"Backup reserved pct: {power_wall.get_backup_reserved_percentage()}")
    print(f"Solars: {power_wall.get_solars()}")
    print(f"VIN: {power_wall.get_vin()}")

    meters = power_wall.get_meters()
    # print(f"Meters: {pp.pformat(meters.response)}")
    for meter_type in MeterType:
        meter = meters.get_meter(meter_type)
        print(f"Meter: {meter_type}")
        print(f"  Energy exported: {meter.energy_exported}")
        print(f"  Energy imported: {meter.energy_imported}")
        print(f"  Instant power: {meter.instant_power}")
        print(f"  meter info: {pp.pformat(meter)}")
        # print(f"  Instant reactive power: {meter.instant_reactive_power}")
        # print(f"  Instant apparent power: {meter.instant_apparent_power}")
        # print(f"  Instant average voltage: {meter.instant_average_voltage}")
        # print(f"  Instant total current: {meter.instant_total_current}")
        # print(f"  Is Active: {meter.is_active()}")
        # print(f"  Is drawing from: {meter.is_drawing_from()}")
        # print(f"  Is sending to: {meter.is_sending_to()}")

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
