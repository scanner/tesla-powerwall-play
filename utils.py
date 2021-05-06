#!/usr/bin/env python
#
# File: $Id$
#
"""
Utils used by our scripts that talk to the tesla API or the backup gateway API
"""

# system imports
#
import os
from pathlib import Path

import hvac

IFLUXDB_CREDS_PATH = os.getenv("IFLUXDB_CREDS_PATH")
VAULT_TOKEN_FILE = Path("~/.vault-token").expanduser()


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
