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
            }
        )
        if response.status_code!=200:
            Error("VolvoAPI failed calling https://volvoid.eu.volvocars.com/as/token.oauth2, HTTP Statuscode "+str(response.status_code))
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

    except requests.exceptions.RequestException as error:
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
            }
        )
        if response.status_code!=200:
            Error("VolvoAPI failed calling https://volvoid.eu.volvocars.com/as/token.oauth2, HTTP Statuscode "+str(response.status_code))
            access_token=None
            refresh_token=None
        else:
            Info("Refreshed token successful!")
            Debug(response.json())

            #retrieve tokens
            access_token = response.json()['access_token']
            refresh_token = response.json()['refresh_token']
            expirytimestamp=time.time()+response.json()['expires_in']

    except requests.exceptions.RequestException as error:
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
            "https://api.volvocars.com/extended-vehicle/v1/vehicles",
            headers= {
                "accept": "application/json",
                "vcc-api-key": vccapikey,
                "Authorization": "Bearer " + access_token
            }
        )
        Debug("\nResult:")
        Debug(vehicles)
        vjson=vehicles.json()

        vehiclesjson = json.dumps(vehicles.json(), indent=4)
        Debug("\nResult JSON:")
        Debug(vehiclesjson)
        if vehicles.status_code!=200:
            Error("VolvoAPI failed calling https://api.volvocars.com/extended-vehicle/v1/vehicles, HTTP Statuscode "+str(vehicles.status_code))
            return None
        else:
            if (("vehicles") in vjson.keys()) and (len(vjson["vehicles"])>0):
                Info(str(len(vjson["vehicles"]))+" car(s) attached to your Volvo ID account: ")
                for x in vjson["vehicles"]:
                    Info("     "+x["id"])
                if len(Parameters["Mode3"])==0:
                    vin = vjson["vehicles"][0]["id"]
                    Info("No VIN in plugin config, selecting the 1st one ("+vin+") in your Volvo ID")
                else:
                    for x in vjson["vehicles"]:
                        if x["id"]==Parameters["Mode3"]:
                            vin=Parameters["Mode3"]
                            Info("Using configured VIN "+str(vin))
                        else:
                            Debug("Ignoring VIN "+x["id"])
                    if vin==None:
                        Error("manually configured VIN "+Parameters["Mode3"]+" does not exist in your Volvo id account, check your config")
            else:
                Error ("no cars configured for this volvo id")
                vin=None

    except requests.exceptions.RequestException as error:
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
            }
        )

        Debug("\nResult:")
        Debug(status)
        if status.status_code!=200:
            Error("VolvoAPI failed calling "+url+", HTTP Statuscode "+str(status.status_code))
            return None
        else:
            sjson=status.json()
            sjson = json.dumps(status.json(), indent=4)
            Debug("\nResult JSON:")
            Debug(sjson)
            return status.json()

    except requests.exceptions.RequestException as error:
        Error("VolvoAPI failed calling "+url+" with mediatype "+mediatype+" failed")
        Error(error)
        return None

def UpdateSensor(vn,idx,name,tp,subtp,options,nv,sv):
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=tp, Subtype=subtp, DeviceID=vn, Options=options, Used=True).Create()
    Devices[vin].Units[idx].nValue = nv
    Devices[vin].Units[idx].sValue = sv
    Devices[vin].Units[idx].Update(Log=True)
    Domoticz.Log("General/Custom Sensor ("+Devices[vin].Units[idx].Name+")")

def UpdateSelectorSwitch(vn,idx,name,options,nv,sv):
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, TypeName="Selector Switch", DeviceID=vn, Options=options, Used=True).Create()
    Devices[vin].Units[idx].nValue = nv
    Devices[vin].Units[idx].sValue = sv
    Devices[vin].Units[idx].Update(Log=True)
    Domoticz.Log("Selector Switch ("+Devices[vin].Units[idx].Name+")")

def UpdateSwitch(vn,idx,name,nv,sv):
    Debug ("UpdateSwitch("+str(vn)+","+str(idx)+","+str(name)+","+str(nv)+","+str(sv)+" called")
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=244, Subtype=73, DeviceID=vn, Used=True).Create()
    Devices[vin].Units[idx].nValue = nv
    Devices[vin].Units[idx].sValue = sv
    Devices[vin].Units[idx].Update(Log=True)
    Domoticz.Log("On/Off Switch ("+Devices[vin].Units[idx].Name+")")


def UpdateDoorOrWindow(vin,idx,name,value):
    Debug ("UpdateDoorOrWindow("+str(vin)+","+str(idx)+","+str(name)+","+str(value)+") called")
    if (not vin in Devices) or (not idx in Devices[vin].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=244, Subtype=73, Switchtype=11, DeviceID=vin, Used=True).Create()

    if value=="OPEN":
        Devices[vin].Units[idx].nValue = 1
        Devices[vin].Units[idx].sValue = "Open"
    else:
        Devices[vin].Units[idx].nValue = 0
        Devices[vin].Units[idx].sValue = "Closed"
    
    Devices[vin].Units[idx].Update(Log=True)
    Domoticz.Log("Door Contact ("+Devices[vin].Units[idx].Name+")")

def UpdateLock(vin,idx,name,value):
    Debug ("UpdateLock("+str(vin)+","+str(idx)+","+str(name)+","+str(value)+") called")
    if (not vin in Devices) or (not idx in Devices[vin].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=244, Subtype=73, Switchtype=19, DeviceID=vin, Used=True).Create()

    if value=="LOCKED":
        Devices[vin].Units[idx].nValue = 1
        Devices[vin].Units[idx].sValue = "Locked"
    else:
        Devices[vin].Units[idx].nValue = 0
        Devices[vin].Units[idx].sValue = "Unlocked"
    
    Devices[vin].Units[idx].Update(Log=True)
    Domoticz.Log("Door Lock ("+Devices[vin].Units[idx].Name+")")

def UpdateOdoMeter(vn,idx,name,value):
    options = {"ValueQuantity": "Custom", "ValueUnits": "km"}
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        #Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=113, Switchtype=3, DeviceID=vin, Options="{'ValueQuantity': 'Custom','ValueUnits': 'km'}",Used=True).Create()
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=113, Switchtype=3, DeviceID=vin, Options=options,Used=True).Create()
    Devices[vin].Units[idx].nValue = value 
    Devices[vin].Units[idx].sValue = value
    Devices[vin].Units[idx].Update(Log=True)
    Domoticz.Log("Counter ("+Devices[vin].Units[idx].Name+")")

def GetOdoMeter():
    Debug("GetOdoMeter() Called")
    
    odometer=VolvoAPI("https://api.volvocars.com/connected-vehicle/v1/vehicles/"+vin+"/odometer","application/vnd.volvocars.api.connected-vehicle.vehicledata.v1+json")
    if odometer:
        Debug(json.dumps(odometer))
        value=int(odometer["data"]["odometer"]["value"])*10
        Debug("odometer="+str(value))
        UpdateOdoMeter(vin,ODOMETER,"Odometer",value)


def GetDoorWindowAndLockStatus():
    Debug("GetDoorAndLockStatus() Called")
    
    doors=VolvoAPI("https://api.volvocars.com/connected-vehicle/v1/vehicles/"+vin+"/doors","application/vnd.volvocars.api.connected-vehicle.vehicledata.v1+json")
    if doors:
        Debug(json.dumps(doors))
        UpdateDoorOrWindow(vin,HOOD,"Hood",doors["data"]["hoodOpen"]["value"])
        UpdateDoorOrWindow(vin,TAILGATE,"Tailgate",doors["data"]["tailGateOpen"]["value"])
        UpdateDoorOrWindow(vin,FRONTLEFTDOOR,"FrontLeftDoor",doors["data"]["frontLeftDoorOpen"]["value"])
        UpdateDoorOrWindow(vin,FRONTRIGHTDOOR,"FrontRightDoor",doors["data"]["frontRightDoorOpen"]["value"])
        UpdateDoorOrWindow(vin,REARLEFTDOOR,"RearLeftDoor",doors["data"]["rearLeftDoorOpen"]["value"])
        UpdateDoorOrWindow(vin,REARRIGHTDOOR,"RearRightDoor",doors["data"]["rearRightDoorOpen"]["value"])
        UpdateLock(vin,CARLOCKED,"CarLocked",doors["data"]["carLocked"]["value"])
    else:
        Error("Updating Doors failed")

    windows=VolvoAPI("https://api.volvocars.com/connected-vehicle/v1/vehicles/"+vin+"/windows","application/vnd.volvocars.api.connected-vehicle.vehicledata.v1+json")
    if windows:
        Debug(json.dumps(windows))
        UpdateDoorOrWindow(vin,FRONTLEFTWINDOW,"FrontLeftWindow",windows["data"]["frontLeftWindowOpen"]["value"])
        UpdateDoorOrWindow(vin,FRONTRIGHTWINDOW,"FrontRightWindow",windows["data"]["frontRightWindowOpen"]["value"])
        UpdateDoorOrWindow(vin,REARLEFTWINDOW,"RearLeftWindow",windows["data"]["rearLeftWindowOpen"]["value"])
        UpdateDoorOrWindow(vin,REARRIGHTWINDOW,"RearRightWindow",windows["data"]["rearRightWindowOpen"]["value"])
    else:
        Error("Updating Windows failed")

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

        #url='http://api.iternio.com/1/tlm/send?api_key='+abrp_api_key+'&token='+abrp_token+'&tlm={"utc":'+str(utc_timestamp)+',"soc":'+str(chargelevel)+',"is_charging":0}'
        url='http://api.iternio.com/1/tlm/send?api_key='+abrp_api_key+'&token='+abrp_token+'&tlm={"utc":'+str(utc_timestamp)+',"soc":'+str(chargelevel)+',"is_charging":'+str(is_charging)+',"is_dcfc":'+str(is_dcfc)+',"est_battery_range":'+str(RemainingRange)+',"odometer":'+str(odometer)+'}'
        Debug("ABRP url = "+url)
        response=requests.get(url)
        Debug(response.text)
        if response.status_code==200 and response.json()["status"]=="ok":
            Debug("ABRP call succeeded")
        else:
            Error("ABRP call failed")

    except requests.exceptions.RequestException as error:
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
                }
            )

            Debug("\nResult:")
            Debug(status)
            sjson=status.json()

            sjson = json.dumps(status.json(), indent=4)
            Debug("\nResult JSON:")
            Debug(sjson)
            if status.json()["status"]==200:
                climatizationoperationid=status.json()["operationId"]
                if (status.json()["data"]["invokeStatus"]=="COMPLETED"):
                    UpdateSwitch(vin,CLIMATIZATION,"Climatization",nv,command)
                else:
                    Error("climatization did not start/stop, API returned code "+status.json()["data"]["invokeStatus"])
            else:
                Error("climatizatation did not start/stop, webserver returned "+status.json()["status"])

        except requests.exceptions.RequestException as error:
            Error("handleclimatization command failed:")
            Error(error)


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
                }
            )

            Debug("\nResult:")
            Debug(status)
            sjson=status.json()

            sjson = json.dumps(status.json(), indent=4)
            Debug("\nResult JSON:")
            Debug(sjson)
            if status.json()["status"]==200:
                if (status.json()["data"]["invokeStatus"]=="COMPLETED"):
                    UpdateLock(vin,CARLOCKED,"CarLocked",cmd)
                else:
                    Error("Car did not lock/unlock, API returned code "+status.json()["data"]["invokeStatus"])
            else:
                Error("car did not lock/unlock, webserver returned "+str(status.json()["status"]))

        except requests.exceptions.RequestException as error:
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
        if (updateinterval<60):
            Info("Updateinterval too low, correcting to 60 secs")
            updateinterval=59 # putting is too exact 60 might sometimes lead to update after 70 secs 
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
