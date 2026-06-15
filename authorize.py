#!/usr/bin/env python3

# Script for volvo plugin to generate .ini file with token using 2FA
import getpass
import time
import json
import configparser
import requests

#constants
OAUTH_TOKEN_URL = "https://volvoid.eu.volvocars.com/as/token.oauth2"
OAUTH_AUTH_URL = "https://volvoid.eu.volvocars.com/as/authorization.oauth2"

#switch debugging on or off
debug=False

def Debug(text):
    if debug:
        print (text)

def EnsureHTTPS(url):
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
        Debug("Url change to: "+str(url))
    return url

print("Starting VOC login with OTP")

# Read existing credentials from token.ini if available
_config = configparser.ConfigParser()
_config.read('token.ini')
_creds = _config['CREDENTIALS'] if 'CREDENTIALS' in _config else {}

vccapikey = _creds.get('voc_api_key', '').strip()
if not vccapikey:
    vccapikey = input("Enter your VOC API Key: ")

username = _creds.get('voc_user', '').strip()
if not username:
    username = input("Enter your VOC Username: ")

password = _creds.get('voc_pass', '').strip()
if not password:
    password = getpass.getpass("Enter your VOC Password: ")

# Remember whether credentials came from the file
_save_credentials = bool(_creds)


url_params = ("?client_id=h4Yf0b"
              "&response_type=code"
              "&acr_values=urn:volvoid:aal:bronze:2sv"
              "&response_mode=pi.flow"
              "&scope=openid email profile care_by_volvo:financial_information:invoice:read care_by_volvo:financial_information:payment_method care_by_volvo:subscription:read customer:attributes customer:attributes:write order:attributes vehicle:attributes tsp_customer_api:all conve:brake_status conve:climatization_start_stop conve:command_accessibility conve:commands conve:diagnostics_engine_status conve:diagnostics_workshop conve:doors_status conve:engine_status conve:environment conve:fuel_status conve:honk_flash conve:lock conve:lock_status conve:navigation conve:odometer_status conve:trip_statistics conve:tyre_status conve:unlock conve:vehicle_relation conve:warnings conve:windows_status energy:battery_charge_level energy:charging_connection_status energy:charging_system_status energy:electric_range energy:estimated_charging_time energy:recharge_status vehicle:attributes")

while True:
    auth_session = requests.session()
    auth_session.headers = {
        "authorization": "Basic aDRZZjBiOlU4WWtTYlZsNnh3c2c1WVFxWmZyZ1ZtSWFEcGhPc3kxUENhVXNpY1F0bzNUUjVrd2FKc2U0QVpkZ2ZJZmNMeXc=",
        'user-agent': 'okhttp/4.10.0',
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json; charset=utf-8"
    }

    auth = auth_session.get(OAUTH_AUTH_URL + url_params)
    if auth.status_code != 200:
        print("Error responding on OAUTH_URL: "+str(auth.status_code))
        break

    response = auth.json()
    Debug(json.dumps(response,indent=4))

    if response["status"] != "USERNAME_PASSWORD_REQUIRED":
        print("Unexpected status on auth start: "+response["status"])
        break

    url=EnsureHTTPS(response["_links"]["checkUsernamePassword"]["href"]+"?action=checkUsernamePassword")
    Debug(url)
    body={ "username": username, "password": password }
    auth_session.headers.update({"x-xsrf-header": "PingFederate"})
    auth=auth_session.post(url,json.dumps(body))
    if auth.status_code != 200:
        try:
            err = auth.json()
            details = err.get("details", [])
            if any(d.get("code") == "CREDENTIAL_VALIDATION_FAILED" for d in details):
                print("Incorrect username, password or API key. Please try again.")
                vccapikey = input("Enter your VOC API Key: ")
                username = input("Enter your VOC Username: ")
                password = getpass.getpass("Enter your VOC Password: ")
                _save_credentials = False
                continue
        except Exception:
            pass
        print("Error on OAUTH_URL: "+str(auth.status_code))
        print(json.dumps(auth.json(), indent=4))
        break

    response = auth.json()
    Debug(json.dumps(response,indent=4))

    if response["status"] != "OTP_REQUIRED":
        print("Incorrect username, password or API key. Please try again.")
        vccapikey = input("Enter your VOC API Key: ")
        username = input("Enter your VOC Username: ")
        password = getpass.getpass("Enter your VOC Password: ")
        _save_credentials = False
        continue  # retry the whole auth flow

    print("OTP sent to "+str(response["devices"][0]["type"])+"("+str(response["devices"][0]["target"])+")")
    otp=input("Enter your OTP: ")
    url=EnsureHTTPS(response["_links"]["checkOtp"]["href"] + "?action=checkOtp")
    Debug("url="+str(url))
    auth=auth_session.post(url,data=json.dumps({ "otp": otp }))
    Debug(json.dumps(auth.json(),indent=4))
    if auth.status_code != 200:
        print("OTP unsuccessful, invalid status_code: "+str(auth.status_code))
        break

    response=auth.json()
    if response["status"] != "OTP_VERIFIED":
        print("Invalid response status on CheckOTP: "+str(response["status"]))
        break

    Debug("OTP succesful, continuing auth")
    url=EnsureHTTPS(response["_links"]["continueAuthentication"]["href"] + "?action=continueAuthentication")
    auth=auth_session.post(url, data="{}")
    response=auth.json()
    Debug(json.dumps(response,indent=4))
    if auth.status_code != 200:
        print("Invalid status_code in CheckOTP: "+str(auth.status_code))
        break

    Debug("checkAuth succesful, getting token")
    auth_session.headers.update({"content-type": "application/x-www-form-urlencoded"})
    body = {"code": response["authorizeResponse"]["code"], "grant_type": "authorization_code"}
    auth = auth_session.post(OAUTH_TOKEN_URL, data=body)
    response=auth.json()
    Debug(json.dumps(response,indent=4))
    if auth.status_code != 200:
        print("Invalid status_code on continueAuthentication: "+str(auth.status_code))
        break

    # Credentials were typed in this session (not from ini): ask if user wants to save them
    if not _save_credentials:
        print("")
        print("WARNING: the password will be stored as plaintext in token.ini.")
        answer = input("Do you want to save your credentials (API key, username, password) in token.ini? (y/n): ").strip().lower()
        if answer in ('y', 'yes'):
            _save_credentials = True

    config=configparser.ConfigParser()
    config.read('token.ini')
    config["TOKEN"]={
            'access_token' : response['access_token'],
            'refresh_token' : response['refresh_token'],
            'expirytimestamp' : str(time.time()+int(response['expires_in']))}
    if _save_credentials:
        config["CREDENTIALS"]={
            'voc_api_key' : vccapikey,
            'voc_user' : username,
            'voc_pass' : password}
    with open('token.ini','w') as configfile:
        config.write(configfile)
    print("token.ini created, restart your Volvo plugin to use the new token.")
    break

