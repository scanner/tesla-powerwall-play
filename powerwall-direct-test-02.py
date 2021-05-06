#!/usr/bin/env python
#
# File: $Id$
#
"""
Poking the powerwall backup gateway2 via python
"""

# system imports
#
import os
import pprint
from pathlib import Path

# 3rd party imports
import hvac
from tesla_powerwall import Powerwall, MeterType
from tesla_powerwall.error import PowerwallUnreachableError


VAULT_TOKEN_FILE = Path("~/.vault-token").expanduser()
VAULT_SECRETS_PATH = os.getenv("VAULT_SECETS_PATH")
BACKUP_GW_ADDR = os.getenv("BACKUP_GW_ADDR")


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

    power_wall = Powerwall(BACKUP_GW_ADDR)
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
