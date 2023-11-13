# Volvo Recharge (Full EV) plugin
#
# Author: akamming
#
"""
<plugin key="VolvoEV" name="Volvo Recharge (Full EV)" author="akamming" version="0.1.0" wikilink="http://www.domoticz.com/wiki/plugins/plugin.html" externallink="https://github.com/akamming/Domoticz_VolvoRecharge_Plugin">
    <description>
        <h2>Volvo Recharge (Full EV) plugin</h2><br/>
        domoticzwrapper around Volvo API (https://developer.volvocars.com/apis/) so your car sensors can be integrated into your home automation use cases.
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>recharge status (https://developer.volvocars.com/apis/energy/endpoints/recharge-status/)</li>
            <li>doors, windows and lock status, including locking and unlocking of doors (https://developer.volvocars.com/apis/connected-vehicle/endpoints/doors-windows-locks/)</li>
            <li>start/stop climatisation (https://developer.volvocars.com/apis/connected-vehicle/endpoints/climate/)</li>
        </ul>
        <h3>Devices</h3>
        pls look at the above links in API, Volvo does a much better deal describing it than i can
        <h3>Configuration</h3>
        <ul style="list-style-type:square">
            <li>Use your Volvo on Call Username/password, which is linked to your vehicle.</li>
            <li>Register an app on https://developer.volvocars.com/apis/docs/getting-started/ and copy/past the primary app key in the config below</li>
            <li>Optional: Set a VIN if you connected more than one car to your volvo account. If empty the plugin will use the 1st car attached to your Volvo account</li>
            <li>Optional: Set the size of your battery pack if you want the plugin to calculate your estimated efficiency in kWh/100km</li>
            <li>Set an update interval. If you don't pay Volvo for the API, you're only allowed to do 10.000 calls per day.. so make sure not to set the update interval too high. The plugin does several calles per interval.</li>
        </ul>
    </description>
    <params>
        <param field="Username" label="Volvo On Call Username" required="true"/>
        <param field="Password" label="Volvo On Call Password" required="true" password="true"/>
        <param field="Mode1" label="Primary VCC API Key" required="true"/>
        <param field="Mode2" label="update interval in secs" required="true" default="900"/>
        <param field="Mode3" label="VIN (optional)"/>
        <param field="Mode5" label="ABRP apikey:token (optional)"/>
        <param field="Mode4" label="Battery Pakc Size (optional)" default="67"/>
        <param field="Mode6" label="Debug" width="150px">
            <options>
                <option label="None" value="0"  default="true" />
                <option label="Python Only" value="2"/>
                <option label="Basic Debugging" value="62"/>
                <option label="Basic+Messages" value="126"/>
                <option label="Queue" value="128"/>
                <option label="Connections Only" value="16"/>
                <option label="Connections+Queue" value="144"/>
                <option label="All" value="-1"/>
            </options>
        </param>
    </params>

</plugin>
"""
#needed modules
import DomoticzEx as Domoticz
import requests
import json
import datetime
from datetime import timezone
import time
from math import sin, cos, sqrt, atan2, radians

#global vars
abrp_api_key=None
abrp_token=None
vocuser=None
vocpass=None
vccapikey=None
access_token=None
refresh_token=None
expirytimestamp=None
updateinterval=None
lastupdate=None
vin=None
debugging=False
info=False
climatizationactionid=None
climatizationstoptimestamp=time.time()

#Constants
TIMEOUT=10 #timeout for API requests

#Device Numbers
REMAININGRANGE=1
FULLRANGE=2
BATTERYCHARGELEVEL=3
CHARGINGCONNECTIONSTATUS=4
CHARGINGSYSTEMSTATUS=5
ESTIMATEDCHARGINGTIME=6
CLIMATIZATION=7
CARLOCKED=8
HOOD=9
TAILGATE=10
FRONTLEFTDOOR=11
FRONTRIGHTDOOR=12
REARLEFTDOOR=13
REARRIGHTDOOR=14
FRONTLEFTWINDOW=15
FRONTRIGHTWINDOW=16
REARLEFTWINDOW=17
REARRIGHTWINDOW=18
ESTIMATEDEFFICIENCY=19
ABRPSYNC=20
ODOMETER=21
TANKLID=22
SUNROOF=23
FRONTRIGHTTYREPRESSURE=24
FRONTLEFTTYREPRESSURE=25
REARLEFTTYREPRESSURE=26
REARRIGHTTYREPRESSURE=27
SERVICESTATUS=28
ENGINEHOURSTOSERVICE=29
KMTOSERVICE=30
MONTHSTOSERVICE=31
LONGITUDE=32
LATTITUDE=33
ALTITUDE=34
HEADING=35
DISTANCE2HOME=36
ENGINERUNNING=37
OILLEVEL=38
ENGINECOOLANTLEVEL=39

def Debug(text):
    if debugging:
        Domoticz.Log("DEBUG: "+str(text))

def Error(text):
    Domoticz.Log("ERROR: "+str(text))

def Info(text):
    if info or debugging:
        Domoticz.Log("INFO: "+str(text))

def LoginToVOC():
    global access_token,refresh_token,expirytimestamp

    Debug("LoginToVOC() called")
    
    try:
        response = requests.post(
            "https://volvoid.eu.volvocars.com/as/token.oauth2",
            headers = {
                'authorization': 'Basic aDRZZjBiOlU4WWtTYlZsNnh3c2c1WVFxWmZyZ1ZtSWFEcGhPc3kxUENhVXNpY1F0bzNUUjVrd2FKc2U0QVpkZ2ZJZmNMeXc=',
                'content-type': 'application/x-www-form-urlencoded',
                'user-agent': 'okhttp/4.10.0'
            },
            data = {
                'username': vocuser,
                'password': vocpass,
                'access_token_manager_id': 'JWTh4Yf0b',
                'grant_type': 'password',
                'scope': 'openid email profile care_by_volvo:financial_information:invoice:read care_by_volvo:financial_information:payment_method care_by_volvo:subscription:read customer:attributes customer:attributes:write order:attributes vehicle:attributes tsp_customer_api:all conve:brake_status conve:climatization_start_stop conve:command_accessibility conve:commands conve:diagnostics_engine_status conve:diagnostics_workshop conve:doors_status conve:engine_status conve:environment conve:fuel_status conve:honk_flash conve:lock conve:lock_status conve:navigation conve:odometer_status conve:trip_statistics conve:tyre_status conve:unlock conve:vehicle_relation conve:warnings conve:windows_status energy:battery_charge_level energy:charging_connection_status energy:charging_system_status energy:electric_range energy:estimated_charging_time energy:recharge_status vehicle:attributes'
            },
            timeout = TIMEOUT
        )
        if response.status_code!=200:
            Error("VolvoAPI failed calling https://volvoid.eu.volvocars.com/as/token.oauth2, HTTP Statuscode "+str(response.status_code))
            Error("Response: "+str(response.json()))
            access_token=None
            refresh_token=None
        else:
            Debug(response.content)
            try:
                resp=response.json()
                if resp==None or "error" in resp.keys():
                    Error("Login Failed, check your config, Response from Volvo: "+str(response.content))
                    refresh_token=None
                    access_token=None
                else:
                    Info("Login successful!")

                    #retrieve tokens
                    access_token = resp['access_token']
                    refresh_token = resp['refresh_token']
                    expirytimestamp=time.time()+resp['expires_in']

                    #after login: Get Vin
                    GetVin()
            except ValueError as exc:
                Error("Login Failed: unable to process json response from https://volvoid.eu.volvocars.com/as/token.oauth2 : "+str(exc))

    except Exception as error:
        Error("Login failed, check internet connection:")
        Error(error)

def RefreshVOCToken():
    global access_token,refresh_token,expirytimestamp

    Debug("RefreshToken() called")
    
    try:
        response = requests.post(
            "https://volvoid.eu.volvocars.com/as/token.oauth2",
            headers = {
                'authorization': 'Basic aDRZZjBiOlU4WWtTYlZsNnh3c2c1WVFxWmZyZ1ZtSWFEcGhPc3kxUENhVXNpY1F0bzNUUjVrd2FKc2U0QVpkZ2ZJZmNMeXc=',
                'content-type': 'application/x-www-form-urlencoded',
                'user-agent': 'okhttp/4.10.0'
            },
            data = {
                'access_token_manager_id': 'JWTh4Yf0b',
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token
            }, 
            timeout=TIMEOUT
        )
        if response.status_code!=200:
            Error("VolvoAPI failed calling https://volvoid.eu.volvocars.com/as/token.oauth2, HTTP Statuscode "+str(response.status_code))
            access_token=None
            refresh_token=None
        else:
            Info("Refreshed token successful!")
            Debug("Volvo responded: "+str(response.json()))

            #retrieve tokens
            access_token = response.json()['access_token']
            refresh_token = response.json()['refresh_token']
            expirytimestamp=time.time()+response.json()['expires_in']

    except Exception as error:
        Error("Refresh failed:")
        Error(error)


def CheckRefreshToken():
    if refresh_token:
        if expirytimestamp-time.time()<60:  #if expires in 60 seconds: refresh
            RefreshVOCToken()
        else:
            Debug("Not refreshing token, expires in "+str(expirytimestamp-time.time())+" seconds")
    else:
        LoginToVOC()

def GetVin():
    global vin

    Debug("GetVin called")
    try:
        vin=None
        vehicles = requests.get(
            "https://api.volvocars.com/connected-vehicle/v2/vehicles",
            headers= {
                "accept": "application/json",
                "vcc-api-key": vccapikey,
                "Authorization": "Bearer " + access_token
            },
            timeout=TIMEOUT
        )
        Debug("Succeeded")
        Debug(vehicles)
        vjson=vehicles.json()

        vehiclesjson = json.dumps(vehicles.json(), indent=4)
        Debug("Result JSON:")
        Debug(vehiclesjson)
        if vehicles.status_code!=200:
            Error("VolvoAPI failed calling https://api.volvocars.com/connected-vehicle/v2/vehicles, HTTP Statuscode "+str(vehicles.status_code))
            return None
        else:
            if (("data") in vjson.keys()) and (len(vjson["data"])>0):
                Info(str(len(vjson["data"]))+" car(s) attached to your Volvo ID account: ")
                for x in vjson["data"]:
                    Info("     "+x["vin"])
                if len(Parameters["Mode3"])==0:
                    vin = vjson["data"][0]["vin"]
                    Info("No VIN in plugin config, selecting the 1st one ("+vin+") in your Volvo ID")
                else:
                    for x in vjson["data"]:
                        if x["vin"]==Parameters["Mode3"]:
                            vin=Parameters["Mode3"]
                            Info("Using configured VIN "+str(vin))
                        else:
                            Debug("Ignoring VIN "+x["vin"])
                    if vin==None:
                        Error("manually configured VIN "+Parameters["Mode3"]+" does not exist in your Volvo id account, check your config")
            else:
                Error ("no cars configured for this volvo id")
                vin=None

    except Exception as error:
        Debug("Get vehicles failed:")
        Debug(error)
        vin=None


def VolvoAPI(url,mediatype):
    Debug("VolvoAPI("+url+","+mediatype+") called")
    try:
        status = requests.get(
            url,
            headers= {
                "accept": mediatype,
                "vcc-api-key": vccapikey,
                "Authorization": "Bearer " + access_token
            },
            timeout=TIMEOUT
        )

        Debug("\nResult:")
        Debug(status)
        if status.status_code!=200:
            Error("VolvoAPI failed calling "+url+", HTTP Statuscode "+str(status.status_code))
            Error("Reponse: "+str(status.json()))
            return None
        else:
            sjson=status.json()
            sjson = json.dumps(status.json(), indent=4)
            Debug("\nResult JSON:")
            Debug(sjson)
            return status.json()

    except Exception as error:
        Error("VolvoAPI failed calling "+url+" with mediatype "+mediatype+" failed")
        Error(error)
        return None

def UpdateSensor(vn,idx,name,tp,subtp,options,nv,sv):
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=tp, Subtype=subtp, DeviceID=vn, Options=options, Used=True).Create()
    Debug("Changing from + "+str(Devices[vin].Units[idx].nValue)+","+str(Devices[vin].Units[idx].sValue)+" to "+str(nv)+","+str(sv))
    if str(sv)!=Devices[vin].Units[idx].sValue:
        Devices[vin].Units[idx].nValue = nv
        Devices[vin].Units[idx].sValue = sv
        Devices[vin].Units[idx].Update(Log=True)
        Domoticz.Log("General/Custom Sensor ("+Devices[vin].Units[idx].Name+")")
    else:
        Debug("not updating General/Custom Sensor ("+Devices[vin].Units[idx].Name+")")

def UpdateSelectorSwitch(vn,idx,name,options,nv,sv):
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, TypeName="Selector Switch", DeviceID=vn, Options=options, Used=True).Create()
    if nv!=Devices[vin].Units[idx].nValue:
        Devices[vin].Units[idx].nValue = nv
        Devices[vin].Units[idx].sValue = sv
        Devices[vin].Units[idx].Update(Log=True)
        Domoticz.Log("Selector Switch ("+Devices[vin].Units[idx].Name+")")
    else:
        Debug("Not Updating Selector Switch ("+Devices[vin].Units[idx].Name+")")


def UpdateSwitch(vn,idx,name,nv,sv):
    Debug ("UpdateSwitch("+str(vn)+","+str(idx)+","+str(name)+","+str(nv)+","+str(sv)+" called")
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=244, Subtype=73, DeviceID=vn, Used=True).Create()
    if (Devices[vin].Units[idx].nValue==nv and Devices[vin].Units[idx].sValue==sv):
        Debug("Switch status unchanged, not updating "+Devices[vin].Units[idx].Name)
    else:
        Debug("Changing from + "+str(Devices[vin].Units[idx].nValue)+","+Devices[vin].Units[idx].sValue+" to "+str(nv)+","+str(sv))
        Devices[vin].Units[idx].nValue = nv
        Devices[vin].Units[idx].sValue = sv
        Devices[vin].Units[idx].Update(Log=True)
        Domoticz.Log("On/Off Switch ("+Devices[vin].Units[idx].Name+")")


def UpdateDoorOrWindow(vin,idx,name,value):
    Debug ("UpdateDoorOrWindow("+str(vin)+","+str(idx)+","+str(name)+","+str(value)+") called")
    if (not vin in Devices) or (not idx in Devices[vin].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=244, Subtype=73, Switchtype=11, DeviceID=vin, Used=True).Create()
    if value=="OPEN" and Devices[vin].Units[idx].nValue==0:
        Devices[vin].Units[idx].nValue = 1
        Devices[vin].Units[idx].sValue = "Open"
        Devices[vin].Units[idx].Update(Log=True)
        Domoticz.Log("Door/Window Contact ("+Devices[vin].Units[idx].Name+")")
    elif value=="CLOSED" and Devices[vin].Units[idx].nValue==1:
        Devices[vin].Units[idx].nValue = 0
        Devices[vin].Units[idx].sValue = "Closed"
        Devices[vin].Units[idx].Update(Log=True)
        Domoticz.Log("Door/Window Contact ("+Devices[vin].Units[idx].Name+")")
    else:
        Debug("Door/Windows status unchanged not updating "+Devices[vin].Units[idx].Name)
    

def UpdateLock(vin,idx,name,value):
    Debug ("UpdateLock("+str(vin)+","+str(idx)+","+str(name)+","+str(value)+") called")
    if (not vin in Devices) or (not idx in Devices[vin].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=244, Subtype=73, Switchtype=19, DeviceID=vin, Used=True).Create()
    if value=="LOCKED" and Devices[vin].Units[idx].nValue==0:
        Devices[vin].Units[idx].nValue = 1
        Devices[vin].Units[idx].sValue = "Locked"
        Devices[vin].Units[idx].Update(Log=True)
        Domoticz.Log("Door Lock ("+Devices[vin].Units[idx].Name+")")
    elif value=="UNLOCKED" and Devices[vin].Units[idx].nValue==1:
        Devices[vin].Units[idx].nValue = 0
        Devices[vin].Units[idx].sValue = "Unlocked"
        Devices[vin].Units[idx].Update(Log=True)
        Domoticz.Log("Door Lock ("+Devices[vin].Units[idx].Name+")")
    else:
        Debug("Lock status unchanged, not updating "+Devices[vin].Units[idx].Name)
    

def UpdateOdoMeter(vn,idx,name,value):
    options = {"ValueQuantity": "Custom", "ValueUnits": "km"}
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=113, Switchtype=3, DeviceID=vin, Options=options,Used=True).Create()
    Debug("Changing from + "+str(Devices[vin].Units[idx].nValue)+","+Devices[vin].Units[idx].sValue+" to "+str(value))
    if value!=Devices[vin].Units[idx].nValue:
        Devices[vin].Units[idx].nValue = value 
        Devices[vin].Units[idx].sValue = value
        Devices[vin].Units[idx].Update(Log=True)
        Domoticz.Log("Counter ("+Devices[vin].Units[idx].Name+")")
    else:
        Debug("not updating Counter ("+Devices[vin].Units[idx].Name+")")

def GetOdoMeter():
    Debug("GetOdoMeter() Called")
    
    odometer=VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin+"/odometer","application/json")
    if odometer:
        Debug(json.dumps(odometer))
        value=int(odometer["data"]["odometer"]["value"])
        Debug("odometer="+str(value))
        UpdateOdoMeter(vin,ODOMETER,"Odometer",value)


def GetDoorWindowAndLockStatus():
    Debug("GetDoorAndLockStatus() Called")
    
    doors=VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin+"/doors","application/json")
    if doors:
        Debug(json.dumps(doors))
        UpdateDoorOrWindow(vin,HOOD,"Hood",doors["data"]["hood"]["value"])
        UpdateDoorOrWindow(vin,TAILGATE,"Tailgate",doors["data"]["tailgate"]["value"])
        UpdateDoorOrWindow(vin,FRONTLEFTDOOR,"FrontLeftDoor",doors["data"]["frontLeftDoor"]["value"])
        UpdateDoorOrWindow(vin,FRONTRIGHTDOOR,"FrontRightDoor",doors["data"]["frontRightDoor"]["value"])
        UpdateDoorOrWindow(vin,REARLEFTDOOR,"RearLeftDoor",doors["data"]["rearLeftDoor"]["value"])
        UpdateDoorOrWindow(vin,REARRIGHTDOOR,"RearRightDoor",doors["data"]["rearRightDoor"]["value"])
        UpdateDoorOrWindow(vin,TANKLID,"TankLid",doors["data"]["tankLid"]["value"])
        UpdateLock(vin,CARLOCKED,"centralLock",doors["data"]["centralLock"]["value"])
    else:
        Error("Updating Doors failed")

    windows=VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin+"/windows","application/json")
    if windows:
        Debug(json.dumps(windows))
        UpdateDoorOrWindow(vin,FRONTLEFTWINDOW,"FrontLeftWindow",windows["data"]["frontLeftWindow"]["value"])
        UpdateDoorOrWindow(vin,FRONTRIGHTWINDOW,"FrontRightWindow",windows["data"]["frontRightWindow"]["value"])
        UpdateDoorOrWindow(vin,REARLEFTWINDOW,"RearLeftWindow",windows["data"]["rearLeftWindow"]["value"])
        UpdateDoorOrWindow(vin,REARRIGHTWINDOW,"RearRightWindow",windows["data"]["rearRightWindow"]["value"])
        UpdateDoorOrWindow(vin,SUNROOF,"SunRoof",windows["data"]["sunroof"]["value"])
    else:
        Error("Updating Windows failed")

def UpdateTyrePressure(status,idx,name):
    #Calculate Charging Connect Status value
    newValue=0
    if status=="LOW":
        newValue=0
    elif status=="NORMAL":
        newValue=10
    elif status=="HIGH":
        newValue=20
    elif status=="LOWSOFT":
        newValue=30
    elif status=="LOWHARD":
        newValue=40
    elif status=="NOSENSOR":
        newValue=50
    elif status=="SYSTEMFAULT":
        newValue=60
    else:
        newValue=70

    #update selector switch for Charging Connection Status
    options = {"LevelActions": "|||",
              "LevelNames": "Low|Normal|High|LowSoft|LowHard|NoSensor|SystemFault|Unspecified",
              "LevelOffHidden": "false",
              "SelectorStyle": "1"}
    UpdateSelectorSwitch(vin,idx,name,options,
                 int(newValue),
                 float(newValue))

def GetTyreStatus():
    Debug("GetTyreStatus() called")
    TyreStatus=VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin+"/tyres","application/json")
    if TyreStatus:
        Debug(json.dumps(TyreStatus))
        UpdateTyrePressure(TyreStatus["data"]["frontRight"]["value"],FRONTRIGHTTYREPRESSURE,"FrontRightTyrePressure")
        UpdateTyrePressure(TyreStatus["data"]["frontLeft"]["value"],FRONTLEFTTYREPRESSURE,"FrontLeftTyrePressure")
        UpdateTyrePressure(TyreStatus["data"]["rearRight"]["value"],REARRIGHTTYREPRESSURE,"RearRightTyrePressure")
        UpdateTyrePressure(TyreStatus["data"]["rearLeft"]["value"],REARLEFTTYREPRESSURE,"RearLeftTyrePressure")
    else:
        Error("Updating Tyre Status failed")

def UpdateLevel(status,idx,name):
    #Calculate Charging Connect Status value
    newValue=0
    if status=="VERY_LOW":
        newValue=0
    elif status=="LOW":
        newValue=10
    elif status=="NORMAL":
        newValue=20
    elif status=="HIGH":
        newValue=30
    elif status=="VERY_HIGH":
        newValue=40
    else:
        newValue=50

    #update selector switch for Charging Connection Status
    options = {"LevelActions": "|||",
              "LevelNames": "Very Low|Low|Normal|High|Very High|Unspecified",
              "LevelOffHidden": "false",
              "SelectorStyle": "1"}
    UpdateSelectorSwitch(vin,idx,name,options,
                 int(newValue),
                 float(newValue))

def GetEngineStatus():
    Debug("GetEngineStatus() called")
    EngineStatus=VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin+"/engine-status","application/json")
    if EngineStatus:
        Debug(json.dumps(EngineStatus))
        if EngineStatus["data"]["engineStatus"]["value"]=="STOPPED":
            UpdateSwitch(vin,ENGINERUNNING,"engineStatus",0,"Off")
        else:
            UpdateSwitch(vin,ENGINERUNNING,"engineStatus",1,"On")
    else:
        Error("Updating Engine Status failed")

def GetEngine():
    Debug("GetEngine() called")
    EngineStatus=VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin+"/engine","application/json")
    if EngineStatus:
        Debug(json.dumps(EngineStatus))
        UpdateLevel(EngineStatus["data"]["engineCoolantLevelWarning"]["value"],ENGINECOOLANTLEVEL,"engineCoolantLevel")
        UpdateLevel(EngineStatus["data"]["oilLevelWarning"]["value"],OILLEVEL,"oilLevel")
    else:
        Error("Updating Engine failed")

def GetDiagnostics():
    Debug("GetDiagnostics() called")
    Diagnostics=VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin+"/diagnostics","application/json")
    if Diagnostics:
        Debug(json.dumps(Diagnostics))
        
        #update engineHoursToService
        UpdateSensor(vin,ENGINEHOURSTOSERVICE,"EngineHoursToService",243,31,{'Custom':'1;hrs'},
                     int(Diagnostics["data"]["engineHoursToService"]["value"]),
                     float(Diagnostics["data"]["engineHoursToService"]["value"]))

        #update kmToService
        UpdateSensor(vin,KMTOSERVICE,"KmToService",243,31,{'Custom':'1;km'},
                     int(Diagnostics["data"]["distanceToService"]["value"]),
                     float(Diagnostics["data"]["distanceToService"]["value"]))

        #update monthsToService
        UpdateSensor(vin,MONTHSTOSERVICE,"MonthsToService",243,31,{'Custom':'1;months'},
                     int(Diagnostics["data"]["timeToService"]["value"]),
                     float(Diagnostics["data"]["timeToService"]["value"]))

        #update selector switch for Charging Connection Status
        options = {"LevelActions": "|||",
                  "LevelNames": "Normal|AlmostTimeForService|TimeForService|TimeExceeded|Unspecified",
                  "LevelOffHidden": "false",
                  "SelectorStyle": "1"}
        status=Diagnostics["data"]["serviceWarning"]["value"]
        newValue=0
        if status=="NORMAL":
            newValue=0
        elif status=="ALMOST_TIME_FOR_SERVICE":
            newValue=10
        elif status=="TIME_FOR_SERVICE":
            newValue=20
        elif status=="TIME_EXCEEDED":
            newValue=30
        else:
            newValue=40
        UpdateSelectorSwitch(vin,SERVICESTATUS,"ServiceStatus",options, int(newValue), float(newValue)) 
    else:
        Error("Updating Diagnostics failed")

def GetRechargeStatus():
    Debug("GetRechargeStatus() called")
    RechargeStatus=VolvoAPI("https://api.volvocars.com/energy/v1/vehicles/"+vin+"/recharge-status","application/vnd.volvocars.api.energy.vehicledata.v1+json")
    if RechargeStatus:
        Debug(json.dumps(RechargeStatus))

        #update Remaining Range Device
        UpdateSensor(vin,REMAININGRANGE,"electricRange",243,31,{'Custom':'1;km'},
                     int(RechargeStatus["data"]["electricRange"]["value"]),
                     float(RechargeStatus["data"]["electricRange"]["value"]))


        #update Percentage Device
        UpdateSensor(vin,BATTERYCHARGELEVEL,"batteryChargeLevel",243,6,None,
                     float(RechargeStatus["data"]["batteryChargeLevel"]["value"]),
                     float(RechargeStatus["data"]["batteryChargeLevel"]["value"]))

        #update Fullrange Device
        CalculatedRange=float(RechargeStatus["data"]["electricRange"]["value"]) * 100 / float(RechargeStatus["data"]["batteryChargeLevel"]["value"])
        UpdateSensor(vin,FULLRANGE,"fullRange",243,31,{'Custom':'1;km'},
                     int(CalculatedRange),
                     "{:.1f}".format(CalculatedRange))

        #update EstimatedEfficiency Device
        if (len(Parameters["Mode4"])>0) and (int(Parameters["Mode4"])>0):
            estimatedEfficiency=(float(Parameters["Mode4"])*float(RechargeStatus["data"]["batteryChargeLevel"]["value"]))  / float(RechargeStatus["data"]["electricRange"]["value"])
            UpdateSensor(vin,ESTIMATEDEFFICIENCY,"estimatedEfficiency",243,31,{'Custom':'1;kWh/100km'},
                         int(estimatedEfficiency),
                         "{:.1f}".format(estimatedEfficiency))
        else:
            Info("No battery pack size specified in config, not calculating estimated efficiency")


        #update Remaining ChargingTime Device
        UpdateSensor(vin,ESTIMATEDCHARGINGTIME,"estimatedChargingTime",243,31,{'Custom':'1;min'},
                     int(RechargeStatus["data"]["estimatedChargingTime"]["value"]),
                     float(RechargeStatus["data"]["estimatedChargingTime"]["value"]))
     
        #Calculate Charging Connect Status value
        connstatus=RechargeStatus["data"]["chargingConnectionStatus"]["value"] 
        newValue=0
        if connstatus=="CONNECTION_STATUS_DISCONNECTED":
            newValue=0
        elif connstatus=="CONNECTION_STATUS_CONNECTED_AC":
            newValue=10
        elif connstatus=="CONNECTION_STATUS_CONNECTED_DC":
            newValue=20
        elif connstatus=="CONNECTION_STATUS_UNSPECIFIED":
            newValue=30
        else:
            newValue=30

        #update selector switch for Charging Connection Status
        options = {"LevelActions": "|||",
                  "LevelNames": "Disconnected|ACConnected|DCConnected|Unspecified",
                  "LevelOffHidden": "false",
                  "SelectorStyle": "1"}
        UpdateSelectorSwitch(vin,CHARGINGCONNECTIONSTATUS,"chargingConnectionStatus",options,
                     int(newValue),
                     float(newValue))

        #Calculate Charging system Status value
        chargestatus=RechargeStatus["data"]["chargingSystemStatus"]["value"] 
        newValue=0
        if chargestatus=="CHARGING_SYSTEM_IDLE":
            newValue=0
        elif chargestatus=="CHARGING_SYSTEM_CHARGING":
            newValue=10
        elif chargestatus=="CHARGING_SYSTEM_FAULT":
            newValue=20
        elif chargestatus=="CHARGING_SYSTEM_UNSPECIFIED":
            newValue=30
        else:
            newValue=30

        #update selector switch for Charging Connection Status
        options = {"LevelActions": "|||",
                  "LevelNames": "Idle|Charging|Fault|Unspecified",
                  "LevelOffHidden": "false",
                  "SelectorStyle": "1"}
        UpdateSelectorSwitch(vin,CHARGINGSYSTEMSTATUS,"chargingSystemStatus",options, int(newValue), float(newValue))
    else:
        Error("Updating Recharge Status failed")

def DistanceBetweenCoords(coords1,coords2):
    # Approximate radius of earth in km
    R = 6373.0

    lat1 = radians(float(coords1[0]))
    lon1 = radians(float(coords1[1]))
    lat2 = radians(float(coords2[0]))
    lon2 = radians(float(coords2[1]))

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = R * c

    Debug=("Result: ", distance)
    return distance

def GetLocation():
    Debug("GetLocation() called")
    Location=VolvoAPI("https://api.volvocars.com/location/v1/vehicles/"+vin+"/location","application/json")
    if Location:
        Debug(json.dumps(Location))
        Debug("Location is " + str(Location["data"]["geometry"]["coordinates"][0]))
        UpdateSensor(vin,LONGITUDE,"Longitude",243,31,{'Custom':'1;lon'}, int(Location["data"]["geometry"]["coordinates"][0]), Location["data"]["geometry"]["coordinates"][0])
        UpdateSensor(vin,LATTITUDE,"Lattitude",243,31,{'Custom':'1;lat'}, int(Location["data"]["geometry"]["coordinates"][1]), Location["data"]["geometry"]["coordinates"][1])
        UpdateSensor(vin,ALTITUDE,"Altitude",243,31,{'Custom':'1;alt'}, int(Location["data"]["geometry"]["coordinates"][2]), Location["data"]["geometry"]["coordinates"][2])
        UpdateSensor(vin,HEADING,"Heading",243,31,{'Custom':'1;degrees'}, int(Location["data"]["properties"]["heading"]), str(Location["data"]["properties"]["heading"]))
        if len(Settings["Location"])>0:
            Debug ( "Domoticz location is "+Settings["Location"])
            DomoticzLocation=Settings["Location"].split(";")
            if len(DomoticzLocation)==2:
                VolvoLocation=(Location["data"]["geometry"]["coordinates"][1],Location["data"]["geometry"]["coordinates"][0])
                Distance2Home=DistanceBetweenCoords(DomoticzLocation, VolvoLocation)
                Debug("Distance to volvo is "+str(Distance2Home))
                UpdateSensor(vin,DISTANCE2HOME,"Distance2Home",243,31,{'Custom':'1;km'}, int(Distance2Home), str(Distance2Home))
            else:
                Debug("Invalid location entered in domoticz config")
        else:
            Debug("No location entered in domoticz config")


    else:
        Error("GetLocation failed")



def UpdateABRP():
    try:
        #get params

        #utc
        dt = datetime.datetime.now(timezone.utc)
        utc_time = dt.replace(tzinfo=timezone.utc)
        utc_timestamp = utc_time.timestamp()

        #chargelevel
        chargelevel=Devices[vin].Units[BATTERYCHARGELEVEL].nValue
        
        #check if we are charging (dnd if so whiuch type)
        is_charging=0
        is_dcfc=0
        if Devices[vin].Units[CHARGINGSYSTEMSTATUS].nValue==10:
            if Devices[vin].Units[CHARGINGCONNECTIONSTATUS].nValue==10:
                is_charging=1
            elif Devices[vin].Units[CHARGINGCONNECTIONSTATUS].nValue==20:
                is_charging=1
                is_dcfc=1

        #odometer
        odometer=Devices[vin].Units[ODOMETER].nValue;

        #Remaining
        RemainingRange=Devices[vin].Units[REMAININGRANGE].nValue;

        #make the call
        url='http://api.iternio.com/1/tlm/send?api_key='+abrp_api_key+'&token='+abrp_token+'&tlm={"utc":'+str(utc_timestamp)+',"soc":'+str(chargelevel)+',"is_charging":'+str(is_charging)+',"is_dcfc":'+str(is_dcfc)+',"est_battery_range":'+str(RemainingRange)+',"odometer":'+str(odometer)+'}'
        Debug("ABRP url = "+url)
        response=requests.get(url,timeout=TIMEOUT)
        Debug(response.text)
        if response.status_code==200 and response.json()["status"]=="ok":
            Debug("ABRP call succeeded")
        else:
            Error("ABRP call failed")

    except Exception as error:
        Error("Error updating ABRP SOC")
        Error(error)


def Heartbeat():
    global lastupdate

    Debug("Heartbeat() called")
    CheckRefreshToken()

    if vin:
        #handle climatization logic
        if (not vin in Devices) or (not CLIMATIZATION in Devices[vin].Units):
            #no Climate device, let's create
            UpdateSwitch(vin,CLIMATIZATION,"Climatization",0,"Off")
        else:
            Debug("Already exists")

        if Devices[vin].Units[CLIMATIZATION].nValue==1:
            if time.time()>climatizationstoptimestamp:
                Info("Switch off climatization, timer expired")
                UpdateSwitch(vin,CLIMATIZATION,"Climatization",0,"Off")
            else:
                Debug("Climatization on, will stop in "+str(climatizationstoptimestamp-time.time())+" seconds")
        else:
            Debug("Climatization switched off, do nothing")


        #handle updates
        if time.time()-lastupdate>=updateinterval:
            # do updates
            Info("Updating Devices")
            lastupdate=time.time()
            GetRechargeStatus()
            GetDoorWindowAndLockStatus()
            GetOdoMeter()
            GetTyreStatus()
            GetDiagnostics()
            GetLocation()
            GetEngineStatus() 
            GetEngine()
        else:
            Debug("Not updating, "+str(updateinterval-(time.time()-lastupdate))+" to update")
        
        #update ABRP SOC
        if abrp_api_key and abrp_token:
            #Check if synmc device exists.
            if (not vin in Devices) or (not ABRPSYNC in Devices[vin].Units):
                UpdateSwitch(vin,ABRPSYNC,"Connect to ABRP",1,"On")

            #Check if we have to sync
            if Devices[vin].Units[ABRPSYNC].nValue==1:
                UpdateABRP()
            else:
                Debug("ABRPSyncing switched off")
        else:
            Debug("No ABRP token and/or apikey, ignoring")

    else:
        Debug("No vin, do nothing")

def HandleClimatizationCommand(vin,idx,command):
    global climatizationstoptimestamp,climatizationoperationid

    if refresh_token:
        url = "https://api.volvocars.com/connected-vehicle/v2/vehicles/" + vin + '/commands/climatization-start'
        climatizationstoptimestamp=time.time()+30*60  #make sure we switch off after 30 mins
        nv=1
        
        if command=='Off':
            url = "https://api.volvocars.com/connected-vehicle/v2/vehicles/" + vin + '/commands/climatization-stop'
            nv=0
        


        try:
            Debug("URL: {}".format(url))
            status = requests.post(
                url,
                headers= {
                    "Content-Type": "application/json",
                    "vcc-api-key": vccapikey,
                    "Authorization": "Bearer " + access_token
                },
                timeout=TIMEOUT
            )

            Debug("\nResult:")
            Debug(status)

            sjson = json.dumps(status.json(), indent=4)
            Debug("\nResult JSON:")
            Debug(sjson)
            if status.status_code==200:
                if (status.json()["data"]["invokeStatus"]=="COMPLETED"):
                    UpdateSwitch(vin,CLIMATIZATION,"Climatization",nv,command)
                else:
                    Error("climatization did not start/stop, API returned code "+status.json()["data"]["invokeStatus"])
            else:
                Error("climatizatation did not start/stop, webserver returned "+str(status.status_code)+", result: "+sjson)

        except Exception as err:
            Error("handleclimatization command failed:")
            Error(err)


def HandleLockCommand(vin,idx,command):
    global climatizationstoptimestamp,climatizationoperationid

    if refresh_token:
        url = "https://api.volvocars.com/connected-vehicle/v2/vehicles/" + vin + '/commands/lock'
        cmd = "LOCKED"
        
        if command=='Off':
            url = "https://api.volvocars.com/connected-vehicle/v2/vehicles/" + vin + '/commands/unlock'
            cmd = "UNLOCKED"

        try:
            Debug("URL: {}".format(url))
            status = requests.post(
                url,
                headers= {
                    "Content-Type": "application/json",
                    "vcc-api-key": vccapikey,
                    "Authorization": "Bearer " + access_token
                },
                timeout=TIMEOUT
            )

            Debug("\nResult:")
            Debug(status)
            sjson = json.dumps(status.json(), indent=4)
            Debug("\nResult JSON:")
            Debug(sjson)
            if status.status_code==200:
                if (status.json()["data"]["invokeStatus"]=="COMPLETED"):
                    UpdateLock(vin,CARLOCKED,"CarLocked",cmd)
                else:
                    Error("Car did not lock/unlock, API returned code "+status.json()["data"]["invokeStatus"])
            else:
                Error("car did not lock/unlock, webserver returned "+str(status.status_code)+", result: "+sjson)

        except Exception as error:
            Error("lock/unlock command failed:")
            Error(error)


class BasePlugin:
    enabled = False
    def __init__(self):
        #self.var = 123
        return

    def onStart(self):
        global vocuser,vocpass,vccapikey,debugging,info,lastupdate,updateinterval,expirytimestamp,abrp_api_key,abrp_token
        Debug("OnStart called")
        
        #read params
        if Parameters["Mode6"] in {"-1","126"}:
            Domoticz.Debugging(int(Parameters["Mode6"]))
            DumpConfigToLog()
            debugging=True
            info=True
        elif Parameters["Mode6"] in {"62"}:
            Domoticz.Debugging(int(Parameters["Mode6"]))
            info=True
            debugging=False
        else:
            debugging=False
            info=True


        #initiate vars
        values=Parameters["Mode5"].split(":")
        if len(values)==2:
            Debug("We have a valid ABRP config")
            abrp_api_key=values[0]
            abrp_token=values[1]
            Debug("ABRP api key="+abrp_api_key+", token="+abrp_token)
        else:
            Debug("len="+str(len(values)))

        vocuser=Parameters["Username"]
        vocpass=Parameters["Password"]
        vccapikey=Parameters["Mode1"]
        updateinterval=int(Parameters["Mode2"])
        if (updateinterval<80):
            Info("Updateinterval too low, correcting to 80 secs")
            updateinterval=79 # putting is too exact 80 might sometimes lead to update after 90 secs 
        lastupdate=time.time()-updateinterval-1 #force update
        expirytimestamp=time.time()-1 #force update


        #1st pass
        Heartbeat()

    def onStop(self):
        Debug("onStop called")

    def onConnect(self, Connection, Status, Description):
        Debug("onConnect called")

    def onMessage(self, Connection, Data):
        Debug("onMessage called")

    def onCommand(self, DeviceID, Unit, Command, Level, Color):
        Debug("onCommand called for Device " + str(DeviceID) + " Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

        if Unit==CLIMATIZATION:
            Debug("Handle climatization")
            HandleClimatizationCommand(DeviceID,Unit,Command)
        elif Unit==CARLOCKED:
            Debug("Handle CarLock")
            HandleLockCommand(DeviceID,Unit,Command)
        elif Unit==ABRPSYNC:
            if Command=='On':
                UpdateSwitch(vin,ABRPSYNC,"ABRPSYNC",1,Command)
            else:
                UpdateSwitch(vin,ABRPSYNC,"ABRPSYNC",0,Command)
        else:
            Debug("uknown command")

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Debug("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Debug("onDisconnect called")

    def onHeartbeat(self):
        Debug("onHeartbeat called")
        Heartbeat()

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(DeviceID, Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(DeviceID, Unit, Command, Level, Color)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Debug("Device count: " + str(len(Devices)))
    for DeviceName in Devices:
        Device = Devices[DeviceName]
        Debug("Device ID:       '" + str(Device.DeviceID) + "'")
        Debug("--->Unit Count:      '" + str(len(Device.Units)) + "'")
        for UnitNo in Device.Units:
            Unit = Device.Units[UnitNo]
            Debug("--->Unit:           " + str(UnitNo))
            Debug("--->Unit Name:     '" + Unit.Name + "'")
            Debug("--->Unit nValue:    " + str(Unit.nValue))
            Debug("--->Unit sValue:   '" + Unit.sValue + "'")
            Debug("--->Unit LastLevel: " + str(Unit.LastLevel))
    return
