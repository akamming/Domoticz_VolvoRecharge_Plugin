#!/usr/bin/env python3
import requests
import json
import datetime
import configparser
import logging
import os

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
api_commands = {}  # komt uit ini

def LoadConfiguration():
    global access_token, vccapikey, vin, api_commands

    # Laad access_token uit token.ini
    token_cfg = configparser.ConfigParser()
    if os.path.exists("token.ini"):
        token_cfg.read("token.ini")
        try:
            access_token = token_cfg['TOKEN']['access_token']
            logger.info("Access token geladen uit token.ini")
        except KeyError:
            logger.error("Kon access_token niet vinden in token.ini")
    else:
        logger.error("token.ini niet gevonden")

    # Laad API-configuratie incl endpoints
    config = configparser.ConfigParser()
    if os.path.exists("volvo_api.ini"):
        config.read("volvo_api.ini")
        try:
            vccapikey = config['API']['vccapikey']
            vin = config['CAR'].get('vin', '').strip()
            logger.info("API-key geladen uit volvo_config.ini")
        except KeyError as e:
            logger.error("Fout in volvo_config.ini: %s", e)

        # Endpoints en methodes laden
        if 'ENDPOINTS' in config and 'HTTP_METHODS' in config:
            api_commands.clear()
            for name in config['ENDPOINTS']:
                url = config['ENDPOINTS'][name]
                method = config['HTTP_METHODS'].get(name, 'GET').upper()
                api_commands[name] = (url, method)
            logger.info(f"{len(api_commands)} API endpoints geladen uit ini")
        else:
            logger.error("Secties [ENDPOINTS] en/of [HTTP_METHODS] ontbreken in volvo_config.ini")
    else:
        logger.error("volvo_config.ini niet gevonden")

def GetVin():
    global access_token, vin, vccapikey

    if vin:
        logger.info("VIN opgehaald uit configuratiebestand: %s", vin)
        return

    if not access_token:
        logger.error("Geen access_token beschikbaar")
        return

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
        logger.info("VIN opgehaald via API: %s", vin)

        opslaan = input("VIN niet in config. Wil je deze opslaan in volvo_config.ini? (j/n): ").strip().lower()
        if opslaan == "j":
            config = configparser.ConfigParser()
            config.read("volvo_api.ini")
            if "CAR" not in config:
                config["CAR"] = {}
            config["CAR"]["vin"] = vin
            with open("volvo_api.ini", "w") as configfile:
                config.write(configfile)
            logger.info("VIN opgeslagen in volvo_config.ini")
    except Exception as e:
        logger.error("Fout bij ophalen van VIN: %s", e)

def APIcommand(name, url, method, accept="application/json"):
    global vin, vccapikey, access_token

    if not vin:
        logger.error("Geen VIN beschikbaar om API aan te roepen")
        return

    url = url.replace("{vin}", vin)
    logger.info("Commando: %s", name)
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
        logger.info("Status: %s", response.status_code)
        logger.info("Tijd: %s", datetime.datetime.now() - start)
        try:
            logger.info("Response:\n%s", json.dumps(response.json(), indent=4))
        except json.JSONDecodeError:
            logger.info("Response niet JSON:\n%s", response.text)
    except requests.exceptions.RequestException as error:
        logger.error("Fout bij '%s': %s", name, error)

def show_menu():
    while True:
        sorted_commands = sorted(api_commands.items(), key=lambda item: item[0].lower())
        print("\n--- Volvo API Menu ---")
        print(f"{'Nr':>3} | {'Naam':<30} | {'Methode':<6} | URL")
        print("-" * 80)
        for i, (name, (url, method)) in enumerate(sorted_commands, 1):
            print(f"{i:3d} | {name:<30.30} | {method:<6} | {url}")
        print("-" * 80)
        print("  0 | Stoppen")

        try:
            keuze = int(input("Kies een commando (nummer): "))
            if keuze == 0:
                break
            elif 1 <= keuze <= len(sorted_commands):
                name, (url, method) = sorted_commands[keuze - 1]
                APIcommand(name, url, method)
            else:
                print("Ongeldige keuze.")
        except ValueError:
            print("Voer een geldig nummer in.")

if __name__ == "__main__":
    logger.info("Start Volvo API Tool")
    LoadConfiguration()
    GetVin()
    show_menu()

