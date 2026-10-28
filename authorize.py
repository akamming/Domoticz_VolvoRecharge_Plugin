#!/usr/bin/env python3

# Script for volvo plugin to generate .ini file with token using 2FA
import argparse
import getpass
import time
import json
import configparser
import requests

#constants
OAUTH_TOKEN_URL = "https://volvoid.eu.volvocars.com/as/token.oauth2"
OAUTH_AUTH_URL = "https://volvoid.eu.volvocars.com/as/authorization.oauth2"

def parse_args():
    parser = argparse.ArgumentParser(
        description="Authorize Volvo plugin and generate token.ini using 2FA"
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable verbose debug logging for Volvo API requests/responses",
    )
    return parser.parse_args()

args = parse_args()
debug = args.debug


def Debug(text):
    if debug:
        print(text)


def _redact_headers(headers):
    redacted = {}
    sensitive = {"authorization", "vcc-api-key", "cookie", "set-cookie"}
    for key, value in headers.items():
        if key.lower() in sensitive:
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = value
    return redacted


def _safe_json(response):
    try:
        return response.json()
    except ValueError:
        return None


def _redact_payload(payload):
    if isinstance(payload, dict):
        redacted = {}
        sensitive = {"password", "otp", "access_token", "refresh_token", "code"}
        for key, value in payload.items():
            if key.lower() in sensitive:
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = value
        return redacted
    return payload


def DebugResponse(response, label):
    if not debug:
        return

    Debug("")
    Debug("========== " + label + " ==========")
    Debug("Request: " + response.request.method + " " + response.request.url)
    Debug("Request headers:")
    Debug(json.dumps(_redact_headers(dict(response.request.headers)), indent=4))
    request_body = response.request.body
    if request_body is not None:
        if isinstance(request_body, bytes):
            request_body = request_body.decode("utf-8", errors="replace")
        try:
            parsed_body = json.loads(request_body)
            request_body = json.dumps(_redact_payload(parsed_body), indent=4)
        except (TypeError, ValueError):
            pass
        Debug("Request body:")
        Debug(str(request_body))

    Debug("Response status: " + str(response.status_code))
    Debug("Response headers:")
    Debug(json.dumps(dict(response.headers), indent=4))
    response_json = _safe_json(response)
    if response_json is not None:
        Debug("Response body (json):")
        Debug(json.dumps(response_json, indent=4))
    else:
        Debug("Response body (text):")
        Debug(response.text)
    Debug("====================================")
    Debug("")

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
        "vcc-api-key": vccapikey,
        'user-agent': 'okhttp/4.10.0',
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json; charset=utf-8"
    }

    auth = auth_session.get(OAUTH_AUTH_URL + url_params)
    DebugResponse(auth, "Initial authorization")
    if auth.status_code != 200:
        print("Error responding on OAUTH_URL: "+str(auth.status_code))
        break

    response = _safe_json(auth)
    if response is None:
        print("Error: Expected JSON response from Volvo auth endpoint.")
        break
    Debug(json.dumps(response,indent=4))

    if response["status"] != "USERNAME_PASSWORD_REQUIRED":
        print("Unexpected status on auth start: "+response["status"])
        break

    url=EnsureHTTPS(response["_links"]["checkUsernamePassword"]["href"]+"?action=checkUsernamePassword")
    Debug(url)
    body={ "username": username, "password": password }
    auth_session.headers.update({"x-xsrf-header": "PingFederate"})
    auth=auth_session.post(url,json.dumps(body))
    DebugResponse(auth, "Check username/password")
    if auth.status_code != 200:
        err = _safe_json(auth)
        if err:
            details = err.get("details", [])
            if any(d.get("code") == "CREDENTIAL_VALIDATION_FAILED" for d in details):
                print("Incorrect username, password or API key. Please try again.")
                vccapikey = input("Enter your VOC API Key: ")
                username = input("Enter your VOC Username: ")
                password = getpass.getpass("Enter your VOC Password: ")
                _save_credentials = False
                continue
        print("Error on OAUTH_URL: "+str(auth.status_code))
        if err:
            print(json.dumps(err, indent=4))
        else:
            print(auth.text)
        break

    response = _safe_json(auth)
    if response is None:
        print("Error: Expected JSON response after username/password check.")
        break
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
    DebugResponse(auth, "Check OTP")
    if auth.status_code != 200:
        print("OTP unsuccessful, invalid status_code: "+str(auth.status_code))
        break

    response = _safe_json(auth)
    if response is None:
        print("Error: Expected JSON response after OTP check.")
        break
    if response["status"] != "OTP_VERIFIED":
        print("Invalid response status on CheckOTP: "+str(response["status"]))
        break

    Debug("OTP succesful, continuing auth")
    url=EnsureHTTPS(response["_links"]["continueAuthentication"]["href"] + "?action=continueAuthentication")
    auth=auth_session.post(url, data="{}")
    DebugResponse(auth, "Continue authentication")
    if auth.status_code != 200:
        print("Invalid status_code in CheckOTP: "+str(auth.status_code))
        break
    response = _safe_json(auth)
    if response is None:
        print("Error: Expected JSON response on continueAuthentication.")
        break
    Debug(json.dumps(response,indent=4))

    Debug("checkAuth succesful, getting token")
    auth_session.headers.update({"content-type": "application/x-www-form-urlencoded"})
    body = {"code": response["authorizeResponse"]["code"], "grant_type": "authorization_code"}
    auth = auth_session.post(OAUTH_TOKEN_URL, data=body)
    DebugResponse(auth, "Get token")
    if auth.status_code != 200:
        print("Invalid status_code on continueAuthentication: "+str(auth.status_code))
        break
    response = _safe_json(auth)
    if response is None:
        print("Error: Expected JSON token response.")
        break
    Debug(json.dumps(response,indent=4))

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
