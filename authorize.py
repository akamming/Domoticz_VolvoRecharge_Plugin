#!/usr/bin/env python3

# Script for volvo plugin to generate .ini file with token using 2FA
import argparse
import base64
import configparser
import getpass
import hashlib
import json
import re
import secrets
import time
from urllib.parse import parse_qs, urljoin, urlparse

import requests

# constants
CLIENT_ID = "mo2qy9h_10"
REDIRECT_URI = "vca://www.volvocars.com/l/vca/oauth/callback"
AUTH_URL = "https://volvoid.eu.volvocars.com/as/authorization.oauth2"
TOKEN_URL = "https://volvoid.eu.volvocars.com/as/token.oauth2"
USER_AGENT = "vca-android/7.2.0"
SCOPES = (
    "openid email profile "
    "care_by_volvo:financial_information:invoice:read "
    "care_by_volvo:financial_information:payment_method "
    "care_by_volvo:subscription:read customer:attributes "
    "customer:attributes:write order:attributes vehicle:attributes "
    "tsp_customer_api:all conve:brake_status conve:climatization_start_stop "
    "conve:command_accessibility conve:commands conve:diagnostics_engine_status "
    "conve:diagnostics_workshop conve:doors_status conve:engine_status "
    "conve:environment conve:fuel_status conve:honk_flash conve:lock "
    "conve:lock_status conve:navigation conve:odometer_status "
    "conve:trip_statistics conve:tyre_status conve:unlock "
    "conve:vehicle_relation conve:warnings conve:windows_status "
    "energy:battery_charge_level energy:charging_connection_status "
    "energy:charging_system_status energy:electric_range "
    "energy:estimated_charging_time energy:recharge_status vehicle:attributes"
)


class OAuthError(Exception):
    pass


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


def _redact_payload(payload):
    if isinstance(payload, dict):
        redacted = {}
        sensitive = {
            "password",
            "otp",
            "access_token",
            "refresh_token",
            "code",
            "code_verifier",
            "code_challenge",
        }
        for key, value in payload.items():
            if key.lower() in sensitive:
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = value
        return redacted
    return payload


def _safe_json(response):
    try:
        return response.json()
    except ValueError:
        return None


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


def create_pkce_pair():
    verifier = secrets.token_urlsafe(64)[:86]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge


def extract_context_string(html, key):
    match = re.search(
        r'"' + re.escape(key) + r'"\s*:\s*"((?:\\.|[^"\\])*)"',
        html,
    )
    if not match:
        return None
    return json.loads('"' + match.group(1) + '"')


def extract_login_action(html):
    action = extract_context_string(html, "loginAction")
    if not action:
        raise OAuthError("Volvo sign-in page did not contain a login action")
    return action


def extract_page_id(html):
    return extract_context_string(html, "pageId")


def authorization_params(challenge, state):
    return {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "acr_values": "urn:volvoid:aal:bronze:2sv",
    }


def is_callback_url(url):
    parsed = urlparse(url)
    expected = urlparse(REDIRECT_URI)
    return (
        parsed.scheme == expected.scheme
        and parsed.netloc == expected.netloc
        and parsed.path == expected.path
    )


def validate_identity_url(url):
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        hostname == "volvocars.com" or hostname.endswith(".volvocars.com")
    ):
        raise OAuthError("Unexpected Volvo identity URL: " + url)


def extract_authorization_code(callback_url, expected_state):
    parsed = urlparse(callback_url)
    if not is_callback_url(callback_url):
        raise OAuthError("Unexpected Volvo authorization callback URL")
    values = parse_qs(parsed.query)
    if values.get("error"):
        raise OAuthError(values.get("error_description", values["error"])[0])
    code = values.get("code", [None])[0]
    if not code:
        raise OAuthError("Volvo authorization callback did not contain a code")
    state = values.get("state", [None])[0]
    if not state or not secrets.compare_digest(state, expected_state):
        raise OAuthError("Volvo authorization callback state did not match")
    return code


def follow_redirects_to_callback(auth_session, response, max_redirects=10):
    for _ in range(max_redirects + 1):
        DebugResponse(response, "Follow redirect")
        location = response.headers.get("location")
        if not location:
            raise OAuthError("Volvo sign-in did not return an authorization callback")
        location = urljoin(response.url, location)
        if is_callback_url(location):
            return location
        validate_identity_url(location)
        response = auth_session.get(location, timeout=30, allow_redirects=False)
    raise OAuthError("Too many redirects while completing Volvo sign-in")


def start_login(auth_session):
    verifier, challenge = create_pkce_pair()
    state = secrets.token_urlsafe(32)
    response = auth_session.get(
        AUTH_URL,
        params=authorization_params(challenge, state),
        timeout=30,
    )
    DebugResponse(response, "Start login")
    response.raise_for_status()
    return verifier, state, extract_login_action(response.text)


def submit_credentials(auth_session, action, username, password):
    validate_identity_url(action)
    response = auth_session.post(
        action,
        data={
            "username": username,
            "password": password,
            "rememberMe": "on",
            "credentialId": "",
            "login": "Sign in",
        },
        timeout=30,
    )
    DebugResponse(response, "Submit credentials")
    response.raise_for_status()
    page_id = extract_page_id(response.text)
    if page_id != "login-otp-email":
        raise OAuthError("Volvo sign-in did not advance to email verification")
    return extract_login_action(response.text)


def submit_otp(auth_session, action, otp):
    validate_identity_url(action)
    response = auth_session.post(
        action,
        data={"otp": otp, "login": "Verify"},
        timeout=30,
        allow_redirects=False,
    )
    DebugResponse(response, "Submit OTP")
    return follow_redirects_to_callback(auth_session, response)


def exchange_code(auth_session, callback_url, verifier, state):
    response = auth_session.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": extract_authorization_code(callback_url, state),
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
        headers={"Accept": "application/json"},
        timeout=30,
    )
    DebugResponse(response, "Exchange authorization code")
    response.raise_for_status()
    token_response = _safe_json(response)
    if token_response is None:
        raise OAuthError("Volvo token endpoint did not return JSON")
    return token_response


print("Starting VOC login with OTP")

# Read existing credentials from token.ini if available
_config = configparser.ConfigParser()
_config.read("token.ini")
_creds = _config["CREDENTIALS"] if "CREDENTIALS" in _config else {}

vccapikey = _creds.get("voc_api_key", "").strip()
if not vccapikey:
    vccapikey = input("Enter your VOC API Key: ")

username = _creds.get("voc_user", "").strip()
if not username:
    username = input("Enter your VOC Username: ")

password = _creds.get("voc_pass", "").strip()
if not password:
    password = getpass.getpass("Enter your VOC Password: ")

# Remember whether credentials came from the file
_save_credentials = bool(_creds)

while True:
    auth_session = requests.session()
    auth_session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json",
            "Accept-Encoding": "gzip",
        }
    )

    try:
        verifier, state, login_action = start_login(auth_session)
        otp_action = submit_credentials(auth_session, login_action, username, password)
        print("OTP verification required (email/SMS from Volvo).")
        otp = input("Enter your OTP: ")
        callback_url = submit_otp(auth_session, otp_action, otp)
        token_response = exchange_code(auth_session, callback_url, verifier, state)
    except requests.HTTPError as exc:
        response = exc.response
        if response is not None:
            print("HTTP error during Volvo authentication: " + str(response.status_code))
            payload = _safe_json(response)
            if payload is not None:
                print(json.dumps(payload, indent=4))
            else:
                print(response.text)
        else:
            print("HTTP error during Volvo authentication: " + str(exc))
        break
    except OAuthError as exc:
        print("Authentication flow error: " + str(exc))
        print("Incorrect username/password or Volvo flow issue. Please try again.")
        vccapikey = input("Enter your VOC API Key: ")
        username = input("Enter your VOC Username: ")
        password = getpass.getpass("Enter your VOC Password: ")
        _save_credentials = False
        continue
    except requests.RequestException as exc:
        print("Network error during Volvo authentication: " + str(exc))
        break

    # Credentials were typed in this session (not from ini): ask if user wants to save them
    if not _save_credentials:
        print("")
        print("WARNING: the password will be stored as plaintext in token.ini.")
        answer = input(
            "Do you want to save your credentials (API key, username, password) in token.ini? (y/n): "
        ).strip().lower()
        if answer in ("y", "yes"):
            _save_credentials = True

    config = configparser.ConfigParser()
    config.read("token.ini")
    config["TOKEN"] = {
        "access_token": token_response["access_token"],
        "refresh_token": token_response["refresh_token"],
        "expirytimestamp": str(time.time() + int(token_response["expires_in"])),
    }
    if _save_credentials:
        config["CREDENTIALS"] = {
            "voc_api_key": vccapikey,
            "voc_user": username,
            "voc_pass": password,
        }
    with open("token.ini", "w") as configfile:
        config.write(configfile)
    print("token.ini created, restart your Volvo plugin to use the new token.")
    break
