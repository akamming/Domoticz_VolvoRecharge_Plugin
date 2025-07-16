#!/usr/bin/env python3
import requests
import json
import datetime
import configparser
import logging
import os
import subprocess
import sys

# Constantes voor bestandsnamen
TOKEN_FILE = "token.ini"
API_CONFIG_FILE = "volvo_api.ini"
AUTHORIZE_SCRIPT = "authorize.py"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Globale variabelen
access_token = None
vin = None
vccapikey = None
api_commands = {}

# Standaard endpoints en methodes voor ini file
DEFAULT_ENDPOINTS = {
    "available commands": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/commands",
    "command accessibility": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/command-accessibility",
    "diagnostics": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/diagnostics",
    "door status": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/doors",
    "engine (extra)": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/engine",
    "engine status": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/engine-status",
    "get vehicle info": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}",
    "list vehicles": "https://api.volvocars.com/connected-vehicle/v2/vehicles",
    "lock vehicle": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/commands/lock",
    "odometer": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/odometer",
    "recharge status (energy v2)": "https://api.volvocars.com/energy/v2/vehicles/{vin}/state",
    "start climatization": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/commands/climatization-start",
    "stop climatization": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/commands/climatization-stop",
    "tyre status": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/tyres",
    "unlock vehicle": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/commands/unlock",
    "vehicle location": "https://api.volvocars.com/location/v1/vehicles/{vin}/location",
    "warning status": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/warnings",
    "window status": "https://api.volvocars.com/connected-vehicle/v2/vehicles/{vin}/windows"
}

DEFAULT_HTTP_METHODS = {
    "available commands": "GET",
    "command accessibility": "GET",
    "diagnostics": "GET",
    "door status": "GET",
    "engine (extra)": "GET",
    "engine status": "GET",
    "get vehicle info": "GET",
    "list vehicles": "GET",
    "lock vehicle": "POST",
    "odometer": "GET",
    "recharge status (energy v2)": "GET",
    "start climatization": "POST",
    "stop climatization": "POST",
    "tyre status": "GET",
    "unlock vehicle": "POST",
    "vehicle location": "GET",
    "warning status": "GET",
    "window status": "GET"
}


def create_default_api_config():
    """Maak een volvo_api.ini aan met default endpoints en vraag om API key."""
    logger.info(f"{API_CONFIG_FILE} niet gevonden. Aanmaken met standaard endpoints.")
    api_key = input("Voer je Volvo API key in: ").strip()
    config = configparser.ConfigParser()
    config['API'] = {'vccapikey': api_key}
    config['CAR'] = {'vin': ''}
    config['ENDPOINTS'] = {k: v for k, v in DEFAULT_ENDPOINTS.items()}
    config['HTTP_METHODS'] = {k: v for k, v in DEFAULT_HTTP_METHODS.items()}

    with open(API_CONFIG_FILE, 'w') as f:
        config.write(f)
    logger.info(f"{API_CONFIG_FILE} aangemaakt met standaard configuratie.")


def LoadConfiguration():
    global access_token, vccapikey, vin, api_commands

    # Check of volvo_api.ini bestaat, zo niet maken
    if not os.path.exists(API_CONFIG_FILE):
        create_default_api_config()

    # Laad token
    token_cfg = configparser.ConfigParser()
    if os.path.exists(TOKEN_FILE):
        token_cfg.read(TOKEN_FILE)
        try:
            access_token = token_cfg['TOKEN']['access_token']
            if not access_token:
                raise KeyError("access_token leeg")
            logger.info("Access token geladen uit token.ini")
        except KeyError:
            logger.warning("Geen geldige access_token gevonden in token.ini")
            access_token = None
    else:
        logger.warning(f"{TOKEN_FILE} niet gevonden")
        access_token = None

    # Laad volvo_api.ini
    config = configparser.ConfigParser()
    config.optionxform = str  # behoud case voor keys in ini
    config.read(API_CONFIG_FILE)

    try:
        vccapikey = config['API']['vccapikey']
        vin = config['CAR'].get('vin', '').strip()
        logger.info("API-key geladen uit volvo_api.ini")
    except KeyError as e:
        logger.error(f"Fout in {API_CONFIG_FILE}: {e}")

    # Endpoints in dict zetten, normaliseren naar lower case keys voor consistentie
    if 'ENDPOINTS' in config and 'HTTP_METHODS' in config:
        api_commands.clear()
        for name in config['ENDPOINTS']:
            url = config['ENDPOINTS'][name]
            method = config['HTTP_METHODS'].get(name, 'GET').upper()
            api_commands[name.lower()] = (url, method)
        logger.info(f"{len(api_commands)} API endpoints geladen uit {API_CONFIG_FILE}")
    else:
        logger.error(f"Secties [ENDPOINTS] en/of [HTTP_METHODS] ontbreken in {API_CONFIG_FILE}")


def reauthorize():
    """Vraag om autorisatie en run authorize.py, herstart script daarna."""
    antwoord = input("Geen geldige access_token. Wil je autoriseren? (j/n): ").strip().lower()
    if antwoord == 'j':
        if os.path.exists(AUTHORIZE_SCRIPT):
            logger.info(f"Start autorisatie via {AUTHORIZE_SCRIPT}...")
            ret = subprocess.run([sys.executable, AUTHORIZE_SCRIPT])
            if ret.returncode == 0:
                logger.info("Autorisatie succesvol. Script wordt opnieuw gestart...")
                # Herstart script
                os.execv(sys.executable, [sys.executable] + sys.argv)
            else:
                logger.error("Autorisatie script faalde.")
                sys.exit(1)
        else:
            logger.error(f"Autorisatie script {AUTHORIZE_SCRIPT} niet gevonden.")
            sys.exit(1)
    else:
        logger.info("Autorisatie overgeslagen. Programma stopt.")
        sys.exit(0)


def GetVin():
    global access_token, vin, vccapikey

    if vin:
        logger.info(f"VIN opgehaald uit configuratiebestand: {vin}")
        return

    if not access_token:
        logger.error("Geen access_token beschikbaar")
        reauthorize()

    url = "https://api.volvocars.com/extended-vehicle/v1/vehicles"
    logger.info("Ophalen van VIN via API...")

    try:
        response = requests.get(
            url,
            headers={
                "accept": "application/json",
                "vcc-api-key": vccapikey,
                "Authorization": f"Bearer {access_token}"
            }
        )
        response.raise_for_status()
        vjson = response.json()

        vin = vjson["vehicles"][0]["id"]
        logger.info(f"VIN opgehaald via API: {vin}")

        opslaan = input("VIN niet in config. Wil je deze opslaan in volvo_api.ini? (j/n): ").strip().lower()
        if opslaan == "j":
            config = configparser.ConfigParser()
            config.read(API_CONFIG_FILE)
            if "CAR" not in config:
                config["CAR"] = {}
            config["CAR"]["vin"] = vin
            with open(API_CONFIG_FILE, "w") as configfile:
                config.write(configfile)
            logger.info(f"VIN opgeslagen in {API_CONFIG_FILE}")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logger.error("Access token ongeldig of verlopen (401).")
            reauthorize()
        else:
            logger.error(f"HTTP fout bij ophalen van VIN: {e}")
    except Exception as e:
        logger.error(f"Fout bij ophalen van VIN: {e}")


def APIcommand(name, url, method, accept="application/json"):
    global vin, vccapikey, access_token

    if not vin:
        logger.error("Geen VIN beschikbaar om API aan te roepen")
        return

    url = url.replace("{vin}", vin)
    logger.info(f"Commando: {name}")
    try:
        start = datetime.datetime.now()
        headers = {
            "accept": accept,
            "vcc-api-key": vccapikey,
            "Authorization": f"Bearer {access_token}"
        }
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers)
        else:
            logger.error(f"HTTP methode '{method}' wordt niet ondersteund")
            return

        response.raise_for_status()
        logger.info(f"Status: {response.status_code}")
        logger.info(f"Tijd: {datetime.datetime.now() - start}")
        try:
            logger.info(f"Response:\n{json.dumps(response.json(), indent=4)}")
        except json.JSONDecodeError:
            logger.info(f"Response niet JSON:\n{response.text}")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logger.error("Access token ongeldig of verlopen (401).")
            reauthorize()
        else:
            logger.error(f"HTTP fout bij '{name}': {e}")
    except requests.exceptions.RequestException as error:
        logger.error(f"Fout bij '{name}': {error}")


def show_menu():
    keys_sorted = sorted(api_commands.keys())
    # Bepaal kolombreedtes
    col1_width = max(len("Nummer"), 6)
    col2_width = max(len("Command"), max(len(k) for k in keys_sorted))
    col3_width = max(len("URL"), max(len(api_commands[k][0]) for k in keys_sorted))

    # Print header
    print()
    print(f"{'Nummer':<{col1_width}} | {'Command':<{col2_width}} | {'URL':<{col3_width}}")
    print("-" * (col1_width + col2_width + col3_width + 6))

    for i, key in enumerate(keys_sorted, 1):
        url, _ = api_commands[key]
        print(f"{i:<{col1_width}} | {key:<{col2_width}} | {url:<{col3_width}}")

    print("-" * (col1_width + col2_width + col3_width + 6))
    print("0      | Exit")

    while True:
        keuze = input("Maak je keuze: ").strip()
        if keuze == "0":
            logger.info("Programma wordt afgesloten.")
            break

        try:
            keuze_index = int(keuze) - 1
            if 0 <= keuze_index < len(keys_sorted):
                key = keys_sorted[keuze_index]
                url, method = api_commands[key]
                APIcommand(key, url, method)
                break  # na 1 commando uitvoeren stop je menu, of haal break weg om menu te herhalen
            else:
                print("Ongeldige keuze, probeer opnieuw.")
        except ValueError:
            print("Voer een getal in.")

def main():
    LoadConfiguration()

    # Check access token
    if not access_token:
        reauthorize()

    # Check VIN
    GetVin()

    # Start menu
    show_menu()


if __name__ == "__main__":
    main()

