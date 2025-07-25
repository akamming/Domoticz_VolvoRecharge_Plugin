# Volvo Recharge (Full EV or PHEV) plugin
#
# Author: akamming
#
"""
<plugin key="VolvoEV" name="Volvo Recharge (Full EV or PHEV)" author="akamming" version="0.1.0" wikilink="http://www.domoticz.com/wiki/plugins/plugin.html" externallink="https://github.com/akamming/Domoticz_VolvoRecharge_Plugin">
    <description>
        <h2>Volvo Recharge (Full EV or PHEV) plugin</h2><br/>
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
            <li>Register an app on https://developer.volvocars.com/apis/docs/getting-started/ and copy/past the primary app key in the config below</li>
            <li>Run the authorize.py script to create a valid token.ini file</li>
            <li>Optional: Set a VIN if you connected more than one car to your volvo account. If empty the plugin will use the 1st car attached to your Volvo account</li>
            <li>Optional: Set Openweather API: Will also get temperature around the car (if your domoticz location settings are set)</li>
            <li>Optional: Set ABRP APIkey/token: Will link you car to ABRP, so ABRP has the actual battery percentage</li>
            <li>Optional: Set Google API key: sets friendly names in the triplog</li>
            <li>Set an update interval. If you don't pay Volvo for the API, you're only allowed to do 10.000 calls per day.. so make sure not to set the update interval too high. The plugin does several calles per interval.</li>
        </ul>
    </description>
    <params>
        <param field="Mode1" label="Primary VCC API Key" required="true"/>
        <param field="Mode2" label="update interval in secs" required="true" default="900"/>
        <param field="Mode3" label="VIN (optional)"/>
        <param field="Mode4" label="Openwheater API (optional)"/>
        <param field="Mode5" label="ABRP apikey:token (optional)"/>
        <param field="Username" label="Google Maps Token (optional)"/>
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
import configparser
import os.path
#import sys, traceback

#Constants
TIMEOUT=60 #timeout for API requests
CLIMATIZATIONTIMEOUT=60 #can take longer when car is in deepsleep
LOCKTIMEOUT=60 #can take longer when car is in deepsleep
MINTIMEBETWEENLOGINATTEMPTS=600 #10 mins
HOMECHARGINGRADIUS=0.050 # 50 meter (assume the car is using the home charger when with 25 meters)
MINDIFFBETWEENCOORDS=0.025 # Only record new trip if new destination is further away than this distance from the previous location
MAXUPDATEINTERVAL=24*3600 # Max number of seconds every sensor has to update when value has not changed, defaults to once per day
TIMETOSETKWHMETERTOZERO=300 #Report 0 usage if no more updates
APISTATUSNAME="API Status" #Default devicename of APIStatus device

#global vars
abrp_api_key=None
abrp_token=None
google_api_key=None
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
lastloginattempttimestamp=time.time()-MINTIMEBETWEENLOGINATTEMPTS
ACCharging=True; #if unknown, assume AC charger at the beginning

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
WASHERFLUIDLEVEL=40
BRAKELIGHTCENTERWARNING=41
BRAKELIGHTLEFTWARNING=42
BRAKELIGHTRIGHTWARNING=43
FOGLIGHTFRONTWARNING=44
FOGLIGHTREARWARNING=45
POSITIONLIGHTFRONTLEFTWARNING=46
POSITIONLIGHTFRONTRIGHTWARNING=47
POSITIONLIGHTREARLEFTWARNING=48
POSITIONLIGHTREARRIGHTWARNING=49
HIGHBEAMLEFTWARNING=50
HIGHBEAMRIGHTWARNING=51
LOWBEAMLEFTWARNING=52
LOWBEAMRIGHTWARNING=53
DAYTIMERUNNINGLIGHTLEFTWARNING=54
DAYTIMERUNNINGLIGHTRIGHTWARNING=55
TURNINDICATIONFRONTLEFTWARNING=56
TURNINDICATIONFRONTRIGHTWARNING=57
TURNINDICATIONREARLEFTWARNING=58
TURNINDICATIONREARRIGHTWARNING=59
REGISTRATIONPLATELIGHTWARNING=60
SIDEMARKLIGHTSWARNING=61
HAZARDLIGHTSWARNING=62
REVERSELIGHTSWARNING=63
CHARGEDATHOME=64
CHARGEDPUBLICAC=65
CHARGEDPUBLICDC=66
CHARGEDPUBLIC=67
CHARGEDTOTAL=68
USEDKWH=69
CHARGINGATHOME=70
CHARGINGPUBLIC=71
AVAILABILITYSTATUS=72
UNAVAILABLEREASON=73
OUTSIDETEMP=74
HONK=75
FLASH=76
HONKFLASH=77
LOCKREDUCEDGUARD=78
LASTKNOWNLOCATION=79
LASTTRIP=80
CURRENTLOCATION=81
UPDATENOW=82
OUTSIDEWIND=83
CARHASMOVED=84
EVCCCONNECTEDSTATUS=85
CHARGINGTYPE=86
CHARGERPOWERSTATUS=87
CHARGINGCURRENTLIMIT=88
TARGETBATTERYLEVEL=89
CHARGINGPOWER=90
APISTATUS=91


def Debug(text):
    if debugging:
        Domoticz.Log("DEBUG: "+str(text))

def Error(text):
    Domoticz.Log("ERROR: "+str(text))

def Info(text):
    if info or debugging:
        Domoticz.Log("INFO: "+str(text))

def ReadTokenFromIniFile():
    global access_token,refresh_token,expirytimestamp

    Debug("ReadTokenFromIniFile() called")

    try:
        config=configparser.ConfigParser()
        config.read(Parameters["HomeFolder"]+'token.ini')
        access_token=config["TOKEN"]["access_token"]
        refresh_token=config["TOKEN"]["refresh_token"]
        expirytimestamp=float(config["TOKEN"]["expirytimestamp"])
        Debug("Token read from file")
        return True

    except KeyError as exc:
        Error("Unable to read token from inifile, run authorize.py"+str(exc))
        return False


def WriteTokenToIniFile():
    global access_token,refresh_token,expirytimestamp

    Debug("WriteTokenToIniFile() called")

    config=configparser.ConfigParser()
    config["TOKEN"]={
            'access_token' : access_token,
            'refresh_token' : refresh_token,
            'expirytimestamp' : expirytimestamp }

    with open(Parameters["HomeFolder"]+'token.ini','w') as configfile:
        config.write(configfile)


def RefreshVOCToken():
    global access_token,refresh_token,expirytimestamp

    Debug("RefreshVOCToken() called")
    
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
            Error(json.dumps(response.json(),indent=4))
            access_token=None
            refresh_token=None
        else:
            Debug(json.dumps(response.json(),indent=4))
            Info("Refreshed token successful!")
            Debug("Volvo responded: "+str(response.json()))

            #retrieve tokens
            resp_json = response.json()
            access_token = resp_json.get('access_token')
            if resp_json.get('refresh_token'):
                Debug("refresh token exists")
                refresh_token = resp_json.get('refresh_token')
            else:
                Debug("No refresh_token")

            if access_token and refresh_token:
                Debug("Access token: "+access_token)
                Debug("Refresh token: "+refresh_token)
                expirytimestamp = time.time() + resp_json.get('expires_in')
            else:
                Error("Unable to retrieve access or refresh token from Volvo response")
                access_token=None
                refresh_token=None        

            #save tokens in case of restarts
            WriteTokenToIniFile()

    except Exception as error:
        Error("Refresh failed:")
        Error(error)


def CheckRefreshToken():
    global lastloginattempttimestamp

    if refresh_token:
        if expirytimestamp-time.time()<60:  #if expires in 60 seconds: refresh
            RefreshVOCToken()
        else:
            Debug("Not refreshing token, expires in "+str(expirytimestamp-time.time())+" seconds")

        #get a vin if we don't have one
        if access_token:
            if vin:
                Debug("We already have a vin")
            else:
                GetVin()
    else:
        if time.time()-lastloginattempttimestamp>=MINTIMEBETWEENLOGINATTEMPTS:
            Debug("Nog logged in, attempting to login")
            lastloginattempttimestamp=time.time()
            # Try from file
            ReadTokenFromIniFile()
            if refresh_token:
                GetVin()
            else:
                Error("Unable to login to Volvo, run authorize.py to re-establish connection")
                UpdateTextSensor(Parameters["Name"],APISTATUS,APISTATUSNAME,"Disconnected, run authorize.py to (re)establish connection")
        else:
            Debug("Not logged in, retrying in "+str(MINTIMEBETWEENLOGINATTEMPTS-(time.time()-lastloginattempttimestamp))+" seconds")

def VolvoAPI(url,mediatype):
    global vin

    Debug("VolvoAPI("+url+","+mediatype+") called")
    try:
        starttime=datetime.datetime.now()
        status = requests.get(
            url,
            headers= {
                "accept": mediatype,
                "vcc-api-key": vccapikey,
                "Authorization": "Bearer " + access_token
            },
            timeout=TIMEOUT
        )
        endtime=datetime.datetime.now()

        Debug("\nResult:")
        Debug(status)
        Debug("Result took "+str(endtime-starttime))

        try:
            resp_json = status.json()
        except Exception as json_error:
            Error("Response from "+url+" is not valid JSON: "+str(json_error))
            output=status.text
            Error("Raw response: "+output)
            UpdateTextSensor(Parameters["Name"],APISTATUS,APISTATUSNAME,f"API Error: {output}")
            return None

        if status.status_code != 200:
            Error("VolvoAPI failed calling "+url+", HTTP Statuscode "+str(status.status_code))
            Error("Response: "+json.dumps(resp_json, indent=4))
            output=status.text
            UpdateTextSensor(Parameters["Name"],APISTATUS,APISTATUSNAME,f"API Error: {output}")
        else:
            Debug("\nResult JSON:")
            Debug(json.dumps(resp_json, indent=4))
            UpdateTextSensor(Parameters["Name"],APISTATUS,APISTATUSNAME,"Connected")
            return resp_json

    except Exception as error:
        output=status.text
        UpdateTextSensor(Parameters["Name"],APISTATUS,APISTATUSNAME,f"API Error: {output}")
        Error("VolvoAPI failed calling "+url+" with mediatype "+mediatype+" failed")
        Error(str(error))
        return None

def CheckVehicleDetails():
    global batteryPackSize
    global vin

    Debug("CheckVehicleDetails called")
    try:
        vehicle = VolvoAPI( "https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin, "application/json")
        Info("retreived a "+str(vehicle["data"]["descriptions"]["model"])+", color "+str(vehicle["data"]["externalColour"])+", model year "+str(vehicle["data"]["modelYear"]))
        if vehicle:
            try:
                batteryPackSize=vehicle["data"]["batteryCapacityKWH"]
                Info("Setting BatteryCapacity to "+str(vehicle["data"]["batteryCapacityKWH"]))
            except:
                Info("Selected vin is not an EV, disabling EV features")
                batteryPackSize=None

    except Exception as error:
        Debug("CheckVehicleDEtails failed:")
        Debug(error)
        #vin=None

def GetVin():
    global vin

    Debug("GetVin called")
    try:
        vin=None
        vehicles = VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles", "application/json")
        if vehicles:
            if (("data") in vehicles.keys()) and (len(vehicles["data"])>0):
                Info(str(len(vehicles["data"]))+" car(s) attached to your Volvo ID account: ")
                for x in vehicles["data"]:
                    Info("     "+x["vin"])
                if len(Parameters["Mode3"])==0:
                    vin = vehicles["data"][0]["vin"]
                    Info("No VIN in plugin config, selecting the 1st one ("+vin+") in your Volvo ID")
                else:
                    for x in vehicles["data"]:
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

            if vin:
                CheckVehicleDetails()

    except Exception as error:
        Debug("Get vehicles failed:")
        Debug(error)
        vin=None

def TimeElapsedSinceLastUpdate(timestring):
        TimeElapsedSinceLastUpdate=None
        try:
            TimeElapsedSinceLastUpdate=datetime.datetime.now()-datetime.datetime.strptime(timestring, '%Y-%m-%d %H:%M:%S')
        except TypeError:
            TimeElapsedSinceLastUpdate=datetime.datetime.now()-datetime.datetime.fromtimestamp(time.mktime(time.strptime(timestring, '%Y-%m-%d %H:%M:%S')))
        return TimeElapsedSinceLastUpdate

def UpdateSensor(vn,idx,name,tp,subtp,options,nv,sv):
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=tp, Subtype=subtp, DeviceID=vn, Options=options, Used=False).Create()
    try:
        Debug("Changing from + "+str(Devices[vin].Units[idx].nValue)+","+str(Devices[vin].Units[idx].sValue)+" to "+str(nv)+","+str(sv))
        if (str(sv)==Devices[vin].Units[idx].sValue and TimeElapsedSinceLastUpdate(Devices[vin].Units[idx].LastUpdate).total_seconds()<MAXUPDATEINTERVAL):
            Debug("not updating General/Custom Sensor ("+Devices[vin].Units[idx].Name+")")
        else:
            if (nv != None):
                Devices[vin].Units[idx].nValue = int(nv)
            Devices[vin].Units[idx].sValue = sv
            Devices[vin].Units[idx].Update(Log=True)
            Domoticz.Log("General/Custom Sensor ("+Devices[vin].Units[idx].Name+")")
    except KeyError:
        Error("Unable to update sensor ("+name+"), is the  \"accept new devices\" toggle switched  on in your config?")

def SafeUpdateSensor(vn,idx,name,tp,subtp,options,struct,key):
    Debug("SafeUpdateSensor("+str(vn)+","+str(idx)+","+str(name)+","+str(tp)+","+str(subtp)+","+str(struct)+","+str(key))
    try:
        UpdateSensor(vn,idx,name,tp,subtp,options,
                    int(struct["data"][key]["value"]),
                    float(struct["data"][key]["value"]))
    except KeyError:
        Debug("Car does not support "+str(key)+" in JSON Output")

def IncreaseKWHMeter(vn,idx,name,percentage):

    #increase KWH meter based on the diff of the batterypercentage 
    global batteryPackSize
    
    #Create Device if it does not exist
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=243, Subtype=29, DeviceID=vn, Used=False).Create()

    try:
        #init values
        newkwh=0
        currentkwh=0
        power=0
        values=Devices[vin].Units[idx].sValue.split(";")
        if len(values)==2:
            #we have a current value
            currentkwh=float(values[1])
            #power=(batteryPackSize*67/69)/100*percentage*1000*3600/TimeElapsedSinceLastUpdate(Devices[vin].Units[idx].LastUpdate).total_seconds()

        #calculate new kwh value
        newkwh=currentkwh+(batteryPackSize*67.0/69.452)/100*percentage*1000

        #update the device
        Debug("Changing from + "+str(Devices[vin].Units[idx].nValue)+","+str(Devices[vin].Units[idx].sValue)+" to "+str(int(power))+";"+str(newkwh))
        Devices[vin].Units[idx].nValue = 0
        Devices[vin].Units[idx].sValue = str(int(power))+";"+str(newkwh)
        Devices[vin].Units[idx].Update(Log=True)
        Domoticz.Log("KWH Meter ("+Devices[vin].Units[idx].Name+")")
    except KeyError:
        Error("Unable to update KWH device ("+name+"), is the  \"accept new devices\" toggle switched  on in your config?")

def UpdateTextSensor(vn,idx,name,text):
    Debug(f"UpdateTextSensor({vn},{idx},{name},{text})")
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=243, Subtype=19, DeviceID=vn, Used=False).Create()

    try:
        if text!=Devices[vn].Units[idx].sValue or TimeElapsedSinceLastUpdate(Devices[vn].Units[idx].LastUpdate).total_seconds()>MAXUPDATEINTERVAL :
            Devices[vn].Units[idx].sValue=text 
            Devices[vn].Units[idx].Type=243
            Devices[vn].Units[idx].SubType=19
            Devices[vn].Units[idx].Update(Log=True)
            Domoticz.Log("TextSensor ("+Devices[vn].Units[idx].Name+")")
        else:
            Debug("Not updating TextSensor ("+Devices[vn].Units[idx].Name+")")
    except KeyError:
        Error("Unable to update Text Sensor ("+name+"), is the  \"accept new devices\" toggle switched  on in your config?")

def UpdateSelectorSwitch(vn,idx,name,options,nv,sv):
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, TypeName="Selector Switch", DeviceID=vn, Options=options, Used=False).Create()

    try:
        if nv!=Devices[vn].Units[idx].nValue or TimeElapsedSinceLastUpdate(Devices[vn].Units[idx].LastUpdate).total_seconds()>MAXUPDATEINTERVAL :
            Devices[vn].Units[idx].nValue = int(nv)
            Devices[vn].Units[idx].sValue = sv
            Devices[vn].Units[idx].Update(Log=True)
            Domoticz.Log("Selector Switch ("+Devices[vn].Units[idx].Name+")")
        else:
            Debug("Not Updating Selector Switch ("+Devices[vn].Units[idx].Name+")")
    except KeyError:
        Error("Unable to update Selector device ("+name+"), is the  \"accept new devices\" toggle switched  on in your config?")

def CreatePushButton(vn,idx,name):
    Debug ("CreatePushButton("+str(vn)+","+str(idx)+","+str(name)+") called")
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=244, Subtype=73, Switchtype=1, DeviceID=vn, Used=False).Create()


def UpdateSwitch(vn,idx,name,nv,sv,ForceUpdate=False):
    Debug ("UpdateSwitch("+str(vn)+","+str(idx)+","+str(name)+","+str(nv)+","+str(sv)+" called")
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=244, Subtype=73, DeviceID=vn, Used=False).Create()

    try:
        if (Devices[vin].Units[idx].nValue==nv and Devices[vin].Units[idx].sValue==sv and TimeElapsedSinceLastUpdate(Devices[vin].Units[idx].LastUpdate).total_seconds()<MAXUPDATEINTERVAL and ForceUpdate==False):
            Debug("Switch status unchanged, not updating "+Devices[vin].Units[idx].Name)
        else:
            Debug("Changing from + "+str(Devices[vin].Units[idx].nValue)+","+Devices[vin].Units[idx].sValue+" to "+str(nv)+","+str(sv))
            Devices[vin].Units[idx].nValue = int(nv)
            Devices[vin].Units[idx].sValue = sv
            Devices[vin].Units[idx].Update(Log=True)
            Domoticz.Log("On/Off Switch ("+Devices[vin].Units[idx].Name+")")
    except KeyError:
        Error("Unable to update switch ("+name+"), is the  \"accept new devices\" toggle switched  on in your config?")

def ReverseSwitch(vn,idx):
    Debug("ReverseSwitch() called")
    if (vn in Devices) and (idx in Devices[vn].Units):
        #Flip values
        if Devices[vn].Units[idx].nValue==1:
            Devices[vn].Units[idx].nValue=0
            Devices[vn].Units[idx].sValue='Off'
        else:
            Devices[vn].Units[idx].nValue=1
            Devices[vn].Units[idx].sValue='On'

        #update the device
        Devices[vn].Units[idx].Update(Log=True)
        Domoticz.Log("On/Off Switch ("+Devices[vin].Units[idx].Name+")")
    else:
        Error("Device does not exist")

            
def UpdateDoorOrWindow(vin,idx,name,value):
    Debug ("UpdateDoorOrWindow("+str(vin)+","+str(idx)+","+str(name)+","+str(value)+") called")
    if (not vin in Devices) or (not idx in Devices[vin].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=244, Subtype=73, Switchtype=11, DeviceID=vin, Used=False).Create()

    try:
        if value=="OPEN" and (Devices[vin].Units[idx].nValue==0 or TimeElapsedSinceLastUpdate(Devices[vin].Units[idx].LastUpdate).total_seconds()>MAXUPDATEINTERVAL):
            Devices[vin].Units[idx].nValue = 1
            Devices[vin].Units[idx].sValue = "Open"
            Devices[vin].Units[idx].Update(Log=True)
            Domoticz.Log("Door/Window Contact ("+Devices[vin].Units[idx].Name+")")
        elif value=="CLOSED" and (Devices[vin].Units[idx].nValue==1 or TimeElapsedSinceLastUpdate(Devices[vin].Units[idx].LastUpdate).total_seconds()>MAXUPDATEINTERVAL):
            Devices[vin].Units[idx].nValue = 0
            Devices[vin].Units[idx].sValue = "Closed"
            Devices[vin].Units[idx].Update(Log=True)
            Domoticz.Log("Door/Window Contact ("+Devices[vin].Units[idx].Name+")")
        else:
            Debug("Door/Windows status unchanged not updating "+Devices[vin].Units[idx].Name)
    except KeyError:
        Error("Unable to update door or window contact: ("+name+"), is the  \"accept new devices\" toggle switched  on in your config?")

def UpdateLock(vin,idx,name,value):
    Debug ("UpdateLock("+str(vin)+","+str(idx)+","+str(name)+","+str(value)+") called")
    if (not vin in Devices) or (not idx in Devices[vin].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=244, Subtype=73, Switchtype=19, DeviceID=vin, Used=False).Create()

    try:
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
    except KeyError:
        Error("Unable to update Lock ("+name+"), is the  \"accept new devices\" toggle switched  on in your config?")

def ReverseLock(vin,idx):
    Debug("ReverseLock() called")
    if (vin in Devices) and (idx in Devices[vin].Units):
        #Reverse the value
        if Devices[vin].Units[idx].nValue==1:
            Devices[vin].Units[idx].nValue = 0
            Devices[vin].Units[idx].sValue = "Unlocked"
        else:
            Devices[vin].Units[idx].nValue = 1
            Devices[vin].Units[idx].sValue = "Locked"
        #Update the value
        Devices[vin].Units[idx].Update(Log=True)
        Domoticz.Log("Door Lock ("+Devices[vin].Units[idx].Name+")")
    else:
        Error("Lock does not exist")

def UpdateOdoMeter(vn,idx,name,value):
    options = {"ValueQuantity": "Custom", "ValueUnits": "km"}
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=Parameters["Name"]+"-"+name, Unit=idx, Type=113, Switchtype=3, DeviceID=vin, Options=options,Used=False).Create()

    try:
        Debug("Changing from + "+str(Devices[vin].Units[idx].nValue)+","+Devices[vin].Units[idx].sValue+" to "+str(value))
        if value!=Devices[vin].Units[idx].nValue or TimeElapsedSinceLastUpdate(Devices[vin].Units[idx].LastUpdate).total_seconds()>MAXUPDATEINTERVAL:
            Devices[vin].Units[idx].nValue = int(value) 
            Devices[vin].Units[idx].sValue = value
            Devices[vin].Units[idx].Update(Log=True)
            Domoticz.Log("Counter ("+Devices[vin].Units[idx].Name+")")
        else:
            Debug("not updating Counter ("+Devices[vin].Units[idx].Name+")")
    except KeyError:
        Error("Unable to update Counter ("+name+"), is the  \"accept new devices\" toggle switched  on in your config?")

def GetOdoMeter():
    Debug("GetOdoMeter() Called")
    odometer = VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/" + vin + "/odometer", "application/json")
    if odometer:
        Debug(json.dumps(odometer))
        value = odometer.get("data", {}).get("odometer", {}).get("value")
        if value is not None:
            Debug("odometer=" + str(value))
            try:
                UpdateOdoMeter(vin, ODOMETER, "Odometer", int(value))
            except (TypeError, ValueError):
                Error("Odometer value is not a valid integer: " + str(value))
        else:
            Error("Odometer value missing in response")
    else:
        Error("Getting Odometer data failed")

def GetWindowStatus():
    Debug("GetWindowstatus() Called")
    windows=VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin+"/windows","application/json")
    if windows:
        Debug(json.dumps(windows))
        data = windows.get("data", {})
        UpdateDoorOrWindow(vin,FRONTLEFTWINDOW,"FrontLeftWindow", data.get("frontLeftWindow", {}).get("value", "UNKNOWN"))
        UpdateDoorOrWindow(vin,FRONTRIGHTWINDOW,"FrontRightWindow", data.get("frontRightWindow", {}).get("value", "UNKNOWN"))
        UpdateDoorOrWindow(vin,REARLEFTWINDOW,"RearLeftWindow", data.get("rearLeftWindow", {}).get("value", "UNKNOWN"))
        UpdateDoorOrWindow(vin,REARRIGHTWINDOW,"RearRightWindow", data.get("rearRightWindow", {}).get("value", "UNKNOWN"))
        UpdateDoorOrWindow(vin,SUNROOF,"SunRoof", data.get("sunroof", {}).get("value", "UNKNOWN"))
    else:
        Error("Updating Windows failed")

def GetDoorAndLockStatus():
    doors=VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin+"/doors","application/json")
    if doors:
        Debug(json.dumps(doors))
        data = doors.get("data", {})
        UpdateDoorOrWindow(vin,HOOD,"Hood", data.get("hood", {}).get("value", "UNKNOWN"))
        UpdateDoorOrWindow(vin,TAILGATE,"Tailgate", data.get("tailgate", {}).get("value", "UNKNOWN"))
        UpdateDoorOrWindow(vin,FRONTLEFTDOOR,"FrontLeftDoor", data.get("frontLeftDoor", {}).get("value", "UNKNOWN"))
        UpdateDoorOrWindow(vin,FRONTRIGHTDOOR,"FrontRightDoor", data.get("frontrightDoor", data.get("frontRightDoor", {})).get("value", "UNKNOWN"))
        UpdateDoorOrWindow(vin,REARLEFTDOOR,"RearLeftDoor", data.get("rearLeftDoor", {}).get("value", "UNKNOWN"))
        UpdateDoorOrWindow(vin,REARRIGHTDOOR,"RearRightDoor", data.get("rearRightDoor", {}).get("value", "UNKNOWN"))
        UpdateDoorOrWindow(vin,TANKLID,"TankLid", data.get("tankLid", {}).get("value", "UNKNOWN"))
        UpdateLock(vin,CARLOCKED,"centralLock", data.get("centralLock", {}).get("value", "UNKNOWN"))
    else:
        Error("Updating Doors failed")

def UpdateTyrePressure(status,idx,name):
    UpdateTextSensor(vin,idx,name,status)

def GetTyreStatus():
    Debug("GetTyreStatus() called")
    TyreStatus=VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin+"/tyres","application/json")
    if TyreStatus:
        Debug(json.dumps(TyreStatus))
        data = TyreStatus.get("data", {})
        UpdateTyrePressure(data.get("frontRight", {}).get("value", "UNKNOWN"),FRONTRIGHTTYREPRESSURE,"FrontRightTyrePressure")
        UpdateTyrePressure(data.get("frontLeft", {}).get("value", "UNKNOWN"),FRONTLEFTTYREPRESSURE,"FrontLeftTyrePressure")
        UpdateTyrePressure(data.get("rearRight", {}).get("value", "UNKNOWN"),REARRIGHTTYREPRESSURE,"RearRightTyrePressure")
        UpdateTyrePressure(data.get("rearLeft", {}).get("value", "UNKNOWN"),REARLEFTTYREPRESSURE,"RearLeftTyrePressure")
    else:
        Error("Updating Tyre Status failed")

def UpdateWarning(status,idx,name):
    UpdateTextSensor(vin,idx,name,status)

def GetWarnings():
    Debug("GetWarningStatus() called")
    WarningStatus=VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin+"/warnings","application/json")
    if WarningStatus:
        Debug(json.dumps(WarningStatus))
        data = WarningStatus.get("data", {})
        UpdateWarning(data.get("brakeLightCenterWarning", {}).get("value", "UNKNOWN"),BRAKELIGHTCENTERWARNING,"BrakeLightCenterWarning")
        UpdateWarning(data.get("brakeLightLeftWarning", {}).get("value", "UNKNOWN"),BRAKELIGHTLEFTWARNING,"BrakeLightLeftWarning")
        UpdateWarning(data.get("brakeLightRightWarning", {}).get("value", "UNKNOWN"),BRAKELIGHTRIGHTWARNING,"BrakeLightRightWarning")
        UpdateWarning(data.get("fogLightFrontWarning", {}).get("value", "UNKNOWN"),FOGLIGHTFRONTWARNING,"fogLightFrontWarning")
        UpdateWarning(data.get("fogLightRearWarning", {}).get("value", "UNKNOWN"),FOGLIGHTREARWARNING,"fogLightRearWarning")
        UpdateWarning(data.get("positionLightFrontLeftWarning", {}).get("value", "UNKNOWN"),POSITIONLIGHTFRONTLEFTWARNING,"positionLightFrontLeftWarning")
        UpdateWarning(data.get("positionLightFrontRightWarning", {}).get("value", "UNKNOWN"),POSITIONLIGHTFRONTRIGHTWARNING,"positionLightFrontRightWarning")
        UpdateWarning(data.get("positionLightRearLeftWarning", {}).get("value", "UNKNOWN"),POSITIONLIGHTREARLEFTWARNING,"positionLightRearLeftWarning")
        UpdateWarning(data.get("positionLightRearRightWarning", {}).get("value", "UNKNOWN"),POSITIONLIGHTREARRIGHTWARNING,"positionLightRearRightWarning")
        UpdateWarning(data.get("highBeamLeftWarning", {}).get("value", "UNKNOWN"),HIGHBEAMLEFTWARNING,"highBeamLeftWarning")
        UpdateWarning(data.get("highBeamRightWarning", {}).get("value", "UNKNOWN"),HIGHBEAMRIGHTWARNING,"highBeamRightWarning")
        UpdateWarning(data.get("lowBeamLeftWarning", {}).get("value", "UNKNOWN"),LOWBEAMLEFTWARNING,"lowBeamLeftWarning")
        UpdateWarning(data.get("lowBeamRightWarning", {}).get("value", "UNKNOWN"),LOWBEAMRIGHTWARNING,"lowBeamRightWarning")
        UpdateWarning(data.get("daytimeRunningLightLeftWarning", {}).get("value", "UNKNOWN"),DAYTIMERUNNINGLIGHTLEFTWARNING,"daytimeRunningLightLeftWarning")
        UpdateWarning(data.get("daytimeRunningLightRightWarning", {}).get("value", "UNKNOWN"),DAYTIMERUNNINGLIGHTRIGHTWARNING,"daytimeRunningLightRightWarning")
        UpdateWarning(data.get("turnIndicationFrontLeftWarning", {}).get("value", "UNKNOWN"),TURNINDICATIONFRONTLEFTWARNING,"turnIndicationFrontLeftWarning")
        UpdateWarning(data.get("turnIndicationFrontRightWarning", {}).get("value", "UNKNOWN"),TURNINDICATIONFRONTRIGHTWARNING,"turnIndicationFrontRightWarning")
        UpdateWarning(data.get("turnIndicationRearLeftWarning", {}).get("value", "UNKNOWN"),TURNINDICATIONREARLEFTWARNING,"turnIndicationRearLeftWarning")
        UpdateWarning(data.get("turnIndicationRearRightWarning", {}).get("value", "UNKNOWN"),TURNINDICATIONREARRIGHTWARNING,"turnIndicationRearRightWarning")
        UpdateWarning(data.get("registrationPlateLightWarning", {}).get("value", "UNKNOWN"),REGISTRATIONPLATELIGHTWARNING,"registrationPlateLightWarning")
        UpdateWarning(data.get("sideMarkLightsWarning", {}).get("value", "UNKNOWN"),SIDEMARKLIGHTSWARNING,"sideMarkLightsWarning")
        UpdateWarning(data.get("hazardLightsWarning", {}).get("value", "UNKNOWN"),HAZARDLIGHTSWARNING,"hazardMarkLightsWarning")
        UpdateWarning(data.get("reverseLightsWarning", {}).get("value", "UNKNOWN"),REVERSELIGHTSWARNING,"reverseMarkLightsWarning")
    else:
        Error("Updating Tyre Status failed")

def GetEngineStatus():
    Debug("GetEngineStatus() called")
    EngineStatus=VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin+"/engine-status","application/json")
    if EngineStatus:
        Debug(json.dumps(EngineStatus))
        data = EngineStatus.get("data", {})
        if data.get("engineStatus", {}).get("value", "STOPPED") == "STOPPED":
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
        data = EngineStatus.get("data", {})
        UpdateTextSensor(vin,ENGINECOOLANTLEVEL,"engineCoolantLevel", data.get("engineCoolantLevelWarning", {}).get("value", "UNKNOWN"))
        UpdateTextSensor(vin,OILLEVEL,"oilLevel", data.get("oilLevelWarning", {}).get("value", "UNKNOWN"))
    else:
        Error("Updating Engine failed")

def GetDiagnostics():
    try:
        Debug("GetDiagnostics() called")
        Diagnostics=VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/"+vin+"/diagnostics","application/json")
        if Diagnostics:
            Debug(json.dumps(Diagnostics))
            data = Diagnostics.get("data", {})
            #update selector switch for Washerfluidlevel
            UpdateTextSensor(vin,WASHERFLUIDLEVEL,"WasherFluidLevel", data.get("washerFluidLevelWarning", {}).get("value", "UNKNOWN"))
            #update engineHoursToService
            SafeUpdateSensor(vin,ENGINEHOURSTOSERVICE,"EngineHoursToService",243,31,{'Custom':'1;hrs'},Diagnostics,"engineHoursToService")
            #update kmToService
            SafeUpdateSensor(vin,KMTOSERVICE,"KmToService",243,31,{'Custom':'1;km'},Diagnostics,"kmToService")
            #update monthsToService
            SafeUpdateSensor(vin,MONTHSTOSERVICE,"MonthsToService",243,31,{'Custom':'1;months'},Diagnostics,"timeToService")
            #update selector switch for ServiceStatus
            UpdateTextSensor(vin,SERVICESTATUS,"ServiceStatus", data.get("serviceWarning", {}).get("value", "UNKNOWN"))
        else:
            Error("Updating Diagnostics failed")
    except Exception as error:
        Debug("Diagnostics call not (fully) supported")
        Debug(error)

def GetCommandAccessabilityStatus():
    Debug("GetCommandAccessibilityStatus() called")
    CAStatus = VolvoAPI("https://api.volvocars.com/connected-vehicle/v2/vehicles/" + vin + "/command-accessibility", "application/json")
    if CAStatus:
        Debug(json.dumps(CAStatus))
        # Veilig ophalen van availabilityStatus en unavailableReason
        data = CAStatus.get("data", {})
        availability = data.get("availabilityStatus", {})
        availability_value = availability.get("value", "UNKNOWN")
        unavailable_reason = availability.get("unavailableReason", "Online")

        UpdateTextSensor(vin, AVAILABILITYSTATUS, "availabilityStatus", availability_value)
        UpdateTextSensor(vin, UNAVAILABLEREASON, "unavailableReason", unavailable_reason)

        if unavailable_reason == "CAR_IN_USE":
            Debug("Car is driving, set current location to unknown")
            UpdateTextSensor(vin, CURRENTLOCATION, "Current Location", "Unknown (Car is in use)")
            UpdateSwitch(vin, CARHASMOVED, "Car is moving or moved", 1, "On")

        if (Devices[vin].Units[AVAILABILITYSTATUS].sValue != "AVAILABLE" and Devices[vin].Units[UNAVAILABLEREASON].sValue != "CAR_IN_USE"):
            Error("Car unavailable, check AVAILABILTYSTATUS sensor to see why the car is unavailable")
        else:
            Debug("Car is available")
    else:
        Error("Updating Command Accessability failed")

def GetRechargeSensorValue(json, sensorName):
    """
    Safely retrieves the value from data[sensorName]["value"].
    If any part of the path is missing or invalid, returns None.
    
    Parameters:
        data (dict): The dictionary containing sensor data (e.g., RechargeStatus["data"]).
        sensorName (str): The name of the sensor to retrieve.

    Returns:
        The value of data[sensorName]["value"], or None if not available.
    """
    data=json.get(sensorName)
    if data is None:
        Debug(sensorName+" not present in json")
        return None
    else:
        value=data.get("value")
        if value is None:
            Debug("Value field not present for "+sensorName)
        else:
            return value

def GetRechargeStatus():
    global batteryPackSize
    global ACCharging

    Debug("GetRechargeStatus() called")
    #RechargeStatus=VolvoAPI(f"https://api.volvocars.com/energy/v1/vehicles/{vin}/recharge-status","application/vnd.volvocars.api.energy.vehicledata.v1+json")
    RechargeStatus=VolvoAPI(f"https://api.volvocars.com/energy/v2/vehicles/{vin}/state","application/json")
    if RechargeStatus:
        Debug(json.dumps(RechargeStatus))

        #Get values from json in safe way
        electricRange=GetRechargeSensorValue(RechargeStatus,"electricRange")
        batteryChargeLevel=GetRechargeSensorValue(RechargeStatus,"batteryChargeLevel")
        chargerConnectionStatus=GetRechargeSensorValue(RechargeStatus,"chargerConnectionStatus")
        chargingStatus=GetRechargeSensorValue(RechargeStatus,"chargingStatus")
        chargingType=GetRechargeSensorValue(RechargeStatus,"chargingType")
        chargerPowerStatus=GetRechargeSensorValue(RechargeStatus,"chargerPowerStatus")
        estimatedChargingTimeToTargetBatteryChargeLevel=GetRechargeSensorValue(RechargeStatus,"estimatedChargingTimeToTargetBatteryChargeLevel")
        chargingCurrentLimit=GetRechargeSensorValue(RechargeStatus,"chargingCurrentLimit")
        targetBatteryChargeLevel=GetRechargeSensorValue(RechargeStatus,"targetBatteryChargeLevel")
        chargingPower=GetRechargeSensorValue(RechargeStatus,"chargingPower")

        if batteryChargeLevel is None:
            Debug("Vehicle not reporting batterychargelevel")
        else:
            if electricRange is None:
                Debug("Vehicle not reporting electricRange")
            else:
                #update Remaining Range Device
                Debug("Update Electric Range")
                UpdateSensor(vin,REMAININGRANGE,"electricRange",243,31,{'Custom':'1;km'},int(electricRange),float(electricRange))

                #update Fullrange Device
                CalculatedRange=float(electricRange) * 100 / float(batteryChargeLevel)
                UpdateSensor(vin,FULLRANGE,"fullRange",243,31,{'Custom':'1;km'},
                             int(CalculatedRange),
                             "{:.1f}".format(CalculatedRange))

                #update EstimatedEfficiency Device
                if float(electricRange>0): 
                    estimatedEfficiency=batteryPackSize*float(batteryChargeLevel)  / float(electricRange)
                    UpdateSensor(vin,ESTIMATEDEFFICIENCY,"estimatedEfficiency",243,31,{'Custom':'1;kWh/100km'},
                                 int(estimatedEfficiency),
                                 "{:.1f}".format(estimatedEfficiency))

            #check if we have an existing batterypercentage
            if (vin in Devices) and (BATTERYCHARGELEVEL in Devices[vin].Units):
                Debug("We have previous batterychargelevelupdates, so we can caculate the diffence")

                #Update kwh counters
                DeltaPercentageBattery=int(float(batteryChargeLevel)-float(Devices[vin].Units[BATTERYCHARGELEVEL].sValue))
                Debug("Battery percentage = "+str(DeltaPercentageBattery))

                if DeltaPercentageBattery!=0 and Devices[vin].Units[CARHASMOVED].nValue==0:
                    Debug("SOC is changing while car is not moving, Updating battery percentage in last known location")
                    UpdateBatteryChargeLevelInLastKnownLocation(float(batteryChargeLevel))
                else:
                    Debug("No need to update SOC in last known location")
                
                if DeltaPercentageBattery<0:
                    Debug("Car is using Energy, we should increase the used energy counter")
                    IncreaseKWHMeter(vin,USEDKWH, "usedKWH", -DeltaPercentageBattery) 
                    IncreaseKWHMeter(vin,CHARGEDTOTAL, "chargedTotal", 0) 
                elif DeltaPercentageBattery>0:
                    Debug("Car is is gaining Energy, we should update the total charged counter")
                    IncreaseKWHMeter(vin,CHARGEDTOTAL, "chargedTotal", DeltaPercentageBattery) 
                    IncreaseKWHMeter(vin,USEDKWH, "usedKWH", 0)

                    #Check if we are charging near home or public charging
                    try:
                        distance2home=float(Devices[vin].Units[DISTANCE2HOME].sValue)
                        if distance2home<=HOMECHARGINGRADIUS: #if the car is within the home charging radius, assume it is charging usiung the homecharger
                            Debug ("Charging at home")
                            IncreaseKWHMeter(vin,CHARGEDATHOME,"chargedAtHome",DeltaPercentageBattery)
                            IncreaseKWHMeter(vin,CHARGEDPUBLIC,"chargedPublic",0)
                            IncreaseKWHMeter(vin,CHARGEDPUBLICAC, "chargedPublicAC", 0)
                            IncreaseKWHMeter(vin,CHARGEDPUBLICDC, "chargedPublicDC", 0)
                        else:
                            Debug("Public Charging")
                            IncreaseKWHMeter(vin,CHARGEDPUBLIC,"chargedPublic",DeltaPercentageBattery)
                            IncreaseKWHMeter(vin,CHARGEDATHOME,"chargedAtHome",0)

                            if chargingType=="AC":
                                IncreaseKWHMeter(vin,CHARGEDPUBLICAC, "chargedPublicAC", DeltaPercentageBattery)
                                IncreaseKWHMeter(vin,CHARGEDPUBLICDC, "chargedPublicDC", 0)
                            else:
                                IncreaseKWHMeter(vin,CHARGEDPUBLICDC, "chargedPublicDC", DeltaPercentageBattery)
                                IncreaseKWHMeter(vin,CHARGEDPUBLICAC, "chargedPublicAC", 0)
                                
                    except KeyError:
                        Error("No Distance 2 home device, also not creating/updating athome/public charging kwh counters")
                else:
                    Debug("Delta Battery Percentage=0")
                    #reset powerlevel if batterlevel has not changed for  5 mins
                    #if TimeElapsedSinceLastUpdate(Devices[vin].Units[BATTERYCHARGELEVEL].LastUpdate).total_seconds()>=TIMETOSETKWHMETERTOZERO or not (vin in Devices and USEDKWH in Devices[vin].Units in CHARGEDTOTAL not in Devices[vin].Units):
                    if TimeElapsedSinceLastUpdate(Devices[vin].Units[BATTERYCHARGELEVEL].LastUpdate).total_seconds()>=TIMETOSETKWHMETERTOZERO:
                        Debug("Car is not using or charging energy")
                        IncreaseKWHMeter(vin,CHARGEDTOTAL, "chargedTotal", 0) 
                        IncreaseKWHMeter(vin,USEDKWH, "usedKWH", 0)

                        #If we know the distance to home, also reset chargedathome and chargedpublic
                        if DISTANCE2HOME in Devices[vin].Units:
                            IncreaseKWHMeter(vin,CHARGEDATHOME,"chargedAtHome",0)
                            IncreaseKWHMeter(vin,CHARGEDPUBLIC,"chargedPublic",0)
                            IncreaseKWHMeter(vin,CHARGEDPUBLICAC, "chargedPublicAC",0)
                            IncreaseKWHMeter(vin,CHARGEDPUBLICDC, "chargedPublicDC",0)
                        else:
                            Debug("Not updating chargedathome and chargedpublic, cause distance2home not known")
                    else:
                        Debug("timeout not expired yet, not resetting counters")
            else:
                Debug("No previous batterypercentagemeasurement, ignoring the updates to KWH meters")

                #Do create the kwhmeters (if not present) to prevent errors on stattup
                IncreaseKWHMeter(vin,CHARGEDTOTAL, "chargedTotal", 0) 
                IncreaseKWHMeter(vin,USEDKWH, "usedKWH", 0)
                IncreaseKWHMeter(vin,CHARGEDATHOME,"chargedAtHome",0)
                IncreaseKWHMeter(vin,CHARGEDPUBLIC,"chargedPublic",0)
                IncreaseKWHMeter(vin,CHARGEDPUBLICAC, "chargedPublicAC",0)
                IncreaseKWHMeter(vin,CHARGEDPUBLICDC, "chargedPublicDC",0)

            
            #update Percentage Device
            UpdateSensor(vin,BATTERYCHARGELEVEL,"batteryChargeLevel",243,6,None,int(batteryChargeLevel),float(batteryChargeLevel))

        if chargingType is None:
            Debug("chargingType not supported")
        else:
            UpdateTextSensor(vin,CHARGINGTYPE,"chargingType",chargingType)

        if chargerPowerStatus is None:
            Debug("chargerPowerStatus not supported")
        else:
            UpdateTextSensor(vin,CHARGERPOWERSTATUS,"chargerPowerStatus",chargerPowerStatus)

        if chargingCurrentLimit is None:
            Debug("chargingCurrentLimit is not supported")
        else:
            UpdateSensor(vin,CHARGINGCURRENTLIMIT,"chargingCurrentLimit",243,23,None,int(chargingCurrentLimit),float(chargingCurrentLimit))

        if targetBatteryChargeLevel is None:
            Debug("targetBatteryChargeLevel is not supported")
        else:
            UpdateSensor(vin,TARGETBATTERYLEVEL,"targetBatteryChargeLevel",243,6,None,int(targetBatteryChargeLevel),float(targetBatteryChargeLevel))

        if chargingPower is None:
            UpdateSensor(vin,CHARGINGPOWER,"chargingPower",248,1,None,0,"0.0")
        else:
            UpdateSensor(vin,CHARGINGPOWER,"chargingPower",248,1,None,int(chargingPower),float(chargingPower))



        #update Remaining ChargingTime Device
        if estimatedChargingTimeToTargetBatteryChargeLevel is None:
            Debug("estimatedChargingTimeToTargetBatteryLevel is not supported")
        else:
            UpdateSensor(vin,ESTIMATEDCHARGINGTIME,"estimatedChargingTime",243,31,{'Custom':'1;min'},int(estimatedChargingTimeToTargetBatteryChargeLevel),float(estimatedChargingTimeToTargetBatteryChargeLevel))

        #Calculate Charging Connect Status value
        if chargerConnectionStatus is None:
            Debug("chargingConnectionStatus is not supported")
        else:
            UpdateTextSensor(vin,CHARGINGCONNECTIONSTATUS,"chargingConnectionStatus", chargerConnectionStatus)

        #Calculate Charging system Status value
        if chargingStatus is None:
            Debug("chargingSystemStatus is not supported")
        else:
            UpdateTextSensor(vin,CHARGINGSYSTEMSTATUS,"chargingSystemStatus", chargingStatus)

        # Determine EVCC connected status (A-F)
        if chargerConnectionStatus is None:
            Debug("ChargerConnectionStatus is not supported")
        else:
            if chargerConnectionStatus=="DISCONNECTED":
                UpdateTextSensor(vin,EVCCCONNECTEDSTATUS,"evccConnectedStatus", "A")
            elif chargerConnectionStatus=="CONNECTED":
                if chargingStatus=="CHARGING":
                    UpdateTextSensor(vin,EVCCCONNECTEDSTATUS,"evccConnectedStatus", "C")
                else:
                    UpdateTextSensor(vin,EVCCCONNECTEDSTATUS,"evccConnectedStatus", "B")
            elif chargerConnectionStatus=="FAULT":
                UpdateTextSensor(vin,EVCCCONNECTEDSTATUS,"evccConnectedStatus", "D")
            else:
                Error("ChargerConnectionStatus not supported, setting EVCCConnectedStatus to E")
                UpdateTextSensor(vin,EVCCCONNECTEDSTATUS,"evccConnectedStatus", "E")

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
    Debug("Result: " + str(distance))
    return distance

def degToCompass(num):
    val=int((num/22.5)+.5)
    arr=["N","NNE","NE","ENE","E","ESE", "SE", "SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return arr[(val % 16)]

def getOutSideTemperature(longitude,latitude):
    global access_token,refresh_token,expirytimestamp

    Debug("GetOutsideTemperature() called")
    
    try:
        url="https://api.openweathermap.org/data/2.5/weather?lat="+str(latitude)+"&lon="+str(longitude)+"&appid="+str(openweather_token)+"&units=metric"
        response = requests.post(url , timeout=TIMEOUT) 
        if response.status_code!=200:
            Error("Error calling"+url+", HTTP Statuscode "+str(response.status_code))
        else:
            Debug("OpenWeather responded: "+str(response.json()))
            ow=response.json()
            UpdateSensor(vin,OUTSIDETEMP,"Outside Temperature",80,5,None,int(ow["main"]["temp"]),ow["main"]["temp"])
            WindValue=str(ow["wind"]["deg"])+";"+degToCompass(ow["wind"]["deg"])+";"+str(ow["wind"]["speed"])+";"+str(ow["wind"]["gust"])+";"+str(ow["main"]["temp"])+";"+str(ow["main"]["feels_like"])
            UpdateSensor(vin,OUTSIDEWIND,"Outside Wind",86,1,None,None,WindValue)
            
    except Exception as error:
        Error("Openweather call failed")
        Error(error)

def GetLocation():
    Debug("GetLocation() called")
    Location = VolvoAPI("https://api.volvocars.com/location/v1/vehicles/" + vin + "/location", "application/json")
    if Location:
        Debug(json.dumps(Location))
        data = Location.get("data", {})
        geometry = data.get("geometry", {})
        coordinates = geometry.get("coordinates", [])
        properties = data.get("properties", {})

        # Check if coordinates have at least 3 values
        if isinstance(coordinates, list) and len(coordinates) >= 3:
            longitude = coordinates[0]
            latitude = coordinates[1]
            altitude = coordinates[2]
            UpdateSensor(vin, LONGITUDE, "Longitude", 243, 31, {'Custom': '1;lon'}, int(longitude), longitude)
            UpdateSensor(vin, LATTITUDE, "Lattitude", 243, 31, {'Custom': '1;lat'}, int(latitude), latitude)
            UpdateSensor(vin, ALTITUDE, "Altitude", 243, 31, {'Custom': '1;alt'}, int(altitude), altitude)
        else:
            Error("Location coordinates missing or incomplete in response")

        # Heading
        heading = properties.get("heading")
        if heading is not None:
            UpdateSensor(vin, HEADING, "Heading", 243, 31, {'Custom': '1;degrees'}, int(heading), str(heading))
        else:
            Error("Heading missing in location response")

        # update temperature around car (if openweather token is present)
        if openweather_token and isinstance(coordinates, list) and len(coordinates) >= 2:
            getOutSideTemperature(coordinates[0], coordinates[1])

        # update distance to car
        if len(Settings["Location"]) > 0:
            Debug("Domoticz location is " + Settings["Location"])
            DomoticzLocation = Settings["Location"].split(";")
            if len(DomoticzLocation) == 2 and isinstance(coordinates, list) and len(coordinates) >= 2:
                VolvoLocation = (coordinates[1], coordinates[0])
                Distance2Home = DistanceBetweenCoords(DomoticzLocation, VolvoLocation)
                Debug("Distance to volvo is " + str(Distance2Home))
                UpdateSensor(vin, DISTANCE2HOME, "Distance2Home", 243, 31, {'Custom': '1;km'}, int(Distance2Home), str(Distance2Home))
            else:
                Debug("Invalid location entered in domoticz config or coordinates missing")
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
        RemainingRange=Devices[vin].Units[REMAININGRANGE].nValue

        #build the url
        url='http://api.iternio.com/1/tlm/send?api_key='+abrp_api_key+'&token='+abrp_token+'&tlm={"utc":'+str(utc_timestamp)+',"soc":'+str(chargelevel)+',"is_charging":'+str(is_charging)+',"is_dcfc":'+str(is_dcfc)+',"est_battery_range":'+str(RemainingRange)+',"odometer":'+str(odometer)+'}'
        if (vin in Devices) and (OUTSIDETEMP in Devices[vin].Units):
            #we can include the outsidetemp in the url
            outsideTemp=Devices[vin].Units[OUTSIDETEMP].sValue
            url='http://api.iternio.com/1/tlm/send?api_key='+abrp_api_key+'&token='+abrp_token+'&tlm={"utc":'+str(utc_timestamp)+',"soc":'+str(chargelevel)+',"is_charging":'+str(is_charging)+',"is_dcfc":'+str(is_dcfc)+',"est_battery_range":'+str(RemainingRange)+',"odometer":'+str(odometer)+',"ext_temp":'+str(outsideTemp)+'}'

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

def GetFriendlyAdress(lattitude,longitude):
    FriendlyAdress=str(lattitude)+","+str(longitude)
    if google_api_key:
        url="https://maps.googleapis.com/maps/api/geocode/json?latlng="+str(lattitude)+","+str(longitude)+"&key="+google_api_key
        Debug("Google url is "+url)
        response=requests.get(url,timeout=TIMEOUT)
        if response.status_code==200:
            try:
                if response.json()["status"]=="OK":
                    FriendlyAdress=response.json()["results"][0]["formatted_address"]
                else:
                    FriendlyAdress="Unknown Adress"
                    Error("Google Geo Code Error (Did you enter a valid Google Geo Code API key in the config?) : "+response.json()["status"])
                    Debug(json.dumps(response.json(),indent=4))
            except Exception as error:
                Error("Error getting friendly adress"+str(error))
                Error("Google response: "+response.text)
                FriendlyAdress+=" (unknown google maps response, check domoticz log for errors)"
        else:
            Error("Google Error "+str(response.status_code))
            Error(response.text)
            FriendlyAdress+=" (google http status error: "+str(response.status_code)+", check domoticz log for errors)"

    return FriendlyAdress

def UpdateLastLocationSensor(lattitude,longitude,friendlyadress,odometer,kwhmeter,percentage):
    CurrentLocation=str(lattitude)+";"+str(longitude)+";"+friendlyadress+";"+str(odometer)+";"+str(kwhmeter)+";"+str(percentage)
    Debug(CurrentLocation)
    UpdateTextSensor(vin,LASTKNOWNLOCATION,"Last Known Location",CurrentLocation)

def UpdateBatteryChargeLevelInLastKnownLocation(Percentage):
    Debug("Updating lastknown location with "+str(Percentage))

    #Get Current Values
    Values=Devices[vin].Units[LASTKNOWNLOCATION].sValue.split(";")
    Lattitude=float(Values[0])
    Longitude=float(Values[1])
    FriendlyAdress=Values[2]
    Odometer=int(Values[3])
    KWHmeter=float(Values[4])

    #Update the Device with the new Percentage
    UpdateLastLocationSensor(Lattitude,Longitude,FriendlyAdress,Odometer,KWHmeter,int(Percentage))

def updateCarHasMoved():
    carhasmoved=False

    try:
        if (vin in Devices and CARHASMOVED in Devices[vin].Units):
            Debug("CARHASMOVED button exists")
            if Devices[vin].Units[CARHASMOVED].nValue==1:
                carhasmoved=True
            else:
                carhasmoved=False

        #read old values
        oldLocation=Devices[vin].Units[LASTKNOWNLOCATION].sValue.split(";")
        oldLattitude=float(oldLocation[0])
        oldLongitude=float(oldLocation[1])
        oldOdometer=int(oldLocation[3])

        #get Current Values
        currentLattitude=float(Devices[vin].Units[LATTITUDE].sValue)
        currentLongitude=float(Devices[vin].Units[LONGITUDE].sValue)
        currentOdometer=Devices[vin].Units[ODOMETER].nValue

        #Check if location has changed
        distance2lastknownlocation=DistanceBetweenCoords((oldLattitude,oldLongitude),(currentLattitude,currentLongitude))
        if distance2lastknownlocation>MINDIFFBETWEENCOORDS:
            Debug("distance2lastknownlocation more than "+str(distance2lastknownlocation)+" km")
            if Devices[vin].Units[CARHASMOVED].nValue==0:
                carhasmoved=True

        #check if odometer has changed
        odoMeterDelta=currentOdometer-oldOdometer
        if odoMeterDelta>0:
            Debug("Car drove "+str(odoMeterDelta)+" km")
            if Devices[vin].Units[CARHASMOVED].nValue==0:
                carhasmoved=True
    
    except Exception as error:
        Debug("Exception updating carhasmoved status: "+str(error))
    
    #pdate the switch
    if carhasmoved:
        Debug("Setting CARHASMOVED to on")
        UpdateSwitch(vin,CARHASMOVED,"Car is moving or moved",1,"On")
    else:
        Debug("Setting CARHASMOVED to off")
        UpdateSwitch(vin,CARHASMOVED,"Car is moving or moved",0,"Off",True)

    
def UpdateLastKnownLocation():
    Debug("UpdateLastKnownLocation() called")
    try:
        #build up line
        currentLattitude=float(Devices[vin].Units[LATTITUDE].sValue)
        currentLongitude=float(Devices[vin].Units[LONGITUDE].sValue)
        currentOdometer=Devices[vin].Units[ODOMETER].nValue
        usedkwh=Devices[vin].Units[USEDKWH].sValue.split(";")
        currentKWHMeter=float(usedkwh[1])
        currentPercentage=Devices[vin].Units[BATTERYCHARGELEVEL].nValue
        currentDatetime = datetime.datetime.now().strftime('%Y/%m/%d %X') # in excel readable format
        currentWind="Unknown"

        if (vin in Devices) and (OUTSIDEWIND in Devices[vin].Units):
            currentWind=Devices[vin].Units[OUTSIDEWIND].sValue

        if (not vin in Devices) or (not LASTKNOWNLOCATION in Devices[vin].Units):
            Debug("LastKnownLocation sensor not there, creating")
            UpdateLastLocationSensor(currentLattitude,currentLongitude,GetFriendlyAdress(currentLattitude,currentLongitude),currentOdometer,currentKWHMeter,currentPercentage)
        else:
            Debug("LastKnownLocation present, checking if we have to update and / or record a trip")

            if Devices[vin].Units[CARHASMOVED].nValue==1:
                Debug("Car moved, calculate difference and write to triplog.csv")

                #Get old values
                oldLocation=Devices[vin].Units[LASTKNOWNLOCATION].sValue.split(";")
                oldLattitude=float(oldLocation[0])
                oldLongitude=float(oldLocation[1])
                oldFriendlyAdress=oldLocation[2]
                oldOdometer=int(oldLocation[3])
                oldKWHmeter=float(oldLocation[4])
                oldPercentage=0
                if len(oldLocation)>5:
                    oldPercentage=float(oldLocation[5])

                #calculate new location and differences
                Triplength=currentOdometer-oldOdometer
                TripUsage=round((currentKWHMeter-oldKWHmeter)/1000,2)
                TripPercentage=int(oldPercentage-currentPercentage)
                currentFriendlyAdress=GetFriendlyAdress(currentLattitude,currentLongitude)
                TripDurationPrecise=TimeElapsedSinceLastUpdate(Devices[vin].Units[CARHASMOVED].LastUpdate)
                TripDuration=datetime.timedelta(seconds=TripDurationPrecise.seconds) #strip the microseconds
                TripSpeed=int(((Triplength*1000.0)/TripDuration.total_seconds())*3.6)

                #Update the sensros
                UpdateSwitch(vin,CARHASMOVED,"Car is moving or moved",0,"Off") #Reset flag to prevent duplicate entries
                UpdateLastLocationSensor(currentLattitude,currentLongitude,currentFriendlyAdress,currentOdometer,currentKWHMeter,currentPercentage)
                UpdateTextSensor(vin,CURRENTLOCATION,"Current Location",currentFriendlyAdress)

                #Log to the triplog
                Tripline=currentDatetime+";"+oldFriendlyAdress+";"+currentFriendlyAdress+";"+str(Triplength)+";"+str(TripUsage)+";"+str(currentOdometer)+";"+str(TripPercentage)+"%;"+currentWind+";"+str(TripDuration)+";"+str(TripSpeed)+"\n"
                filename=Parameters["HomeFolder"]+"triplog.csv"
                if os.path.exists(filename):
                    Debug("existing file, append line")
                    f=open(filename,"a")
                    f.write(Tripline)
                    f.close()
                else:
                    Debug("New file, include header")
                    f=open(filename,"w")
                    f.write("Datetime;From;To;Distance;kwh;OdoMeter;UsedPercentage;WindDirDegrees;WindDirText;WindSpeed;WindGust;Temp;Temp_feels_like;TripDuration;TripSpeed\n")
                    f.write(Tripline)
                    f.close()

                #UpdateLastTripSensor
                LastTrip =  "Date/Time: "+str(datetime.datetime.now())+"\nFrom: "+oldFriendlyAdress+"\nTo: "+currentFriendlyAdress+"\nDistance: "+str(Triplength)+" km, Usage: "+str(TripUsage)+" kwh, Battery:  "+str(TripPercentage)+" %\nTemperature: "+currentWind+"\nDuration: "+str(TripDuration)+"\nSpeed: "+str(TripSpeed)+" km/h"
                UpdateTextSensor(vin,LASTTRIP,"Last Trip",LastTrip)
            else:
                Debug("Car did not move, ignoring")
    
    except KeyError as error:
        Debug("don't update triplog/last known location, not all devices are available yet: "+repr(error))
        #Debug("Exception: "+repr(traceback.format_tb(error.__traceback__)))

def UpdateDevices():
    global lastupdate

    # do updates
    Debug("UpdateDevices() Called")
    lastupdate=time.time()
    GetCommandAccessabilityStatus() # check if we can update
    GetOdoMeter() #Odometer must be known before GetRechargeStatus to detect if car has moved
    GetLocation() #Location must be known before GetRechargeStatus te detect local charging and to detect if carhasmoved
    updateCarHasMoved() #Check if the carhasmoved
    GetDoorAndLockStatus() 
    GetWindowStatus() 
    if batteryPackSize:
        GetRechargeStatus()
    else:
        Debug("No (Partial) EV features, don't call GetRechargeStatus")
    GetTyreStatus()
    GetDiagnostics()
    GetEngineStatus() 
    GetEngine()
    GetWarnings()

    # update calculated sensors
    if Devices[vin].Units[AVAILABILITYSTATUS].sValue=="AVAILABLE":
        UpdateLastKnownLocation()
    else:
        Debug("Car in use, don't try to update location")

def Heartbeat():
    global lastupdate
    global batteryPackSize

    Debug("Heartbeat() called")
    CheckRefreshToken()

    if vin:
        #Make sure we have the control buttons
        CreatePushButton(vin,FLASH,"Flash")
        CreatePushButton(vin,HONK,"Honk")
        CreatePushButton(vin,HONKFLASH,"Honk and Flash")
        CreatePushButton(vin,LOCKREDUCEDGUARD,"Lock with Reduced Guard")
        CreatePushButton(vin,UPDATENOW,"Force Update")

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
            UpdateDevices()
        else:
            Debug("Not updating, "+str(updateinterval-(time.time()-lastupdate))+" to update")
        
        #update ABRP SOC
        if abrp_api_key and abrp_token and batteryPackSize:
            #Check if synmc device exists.
            if (not vin in Devices) or (not ABRPSYNC in Devices[vin].Units):
                UpdateSwitch(vin,ABRPSYNC,"Connect to ABRP",1,"On")

            #Check if we have to sync
            if Devices[vin].Units[ABRPSYNC].nValue==1:
                UpdateABRP()
            else:
                Debug("ABRPSyncing switched off")
        else:
            Debug("No ABRP token and/or apikey or no EV features detected, ignoring")

    else:
        Debug("No vin, do nothing")

def InvokeCommand(url,message,invoketimeout):
    global lastupdate

    Debug("InvokeCommand("+url+","+str(message)+","+str(invoketimeout)+" called")
    starttime=datetime.datetime.now()
    status = requests.post(
        url,
        headers= {
            "Content-Type": "application/json",
            "vcc-api-key": vccapikey,
            "Authorization": "Bearer " + access_token
        },
        data=message,
        timeout=invoketimeout
    )
    endtime=datetime.datetime.now()

    Debug("Invoke Command duration: "+str(endtime-starttime))

    sjson = json.dumps(status.json(), indent=4)
    Debug("Result JSON: "+str(sjson))
    if status.status_code==200:
        if (status.json()["data"]["invokeStatus"]=="COMPLETED"):
            Debug("Command succesfully completed") 
            return True
        else:
            Error("Invoke command failed, API returned code "+status.json()["data"]["invokeStatus"])
            return False
    else:
        Error("InvokeCommand failed, webserver returned "+str(status.status_code)+", result: "+sjson)
        #TODO: handle returncode 429
        if status.status_code==429:
            # Determine Sleep time
            Delay=60-(time.time()-lastupdate)+5
            Error("Retrying command in "+str(Delay)+" seconds")
            time.sleep(Delay)
            Debug("Retrying command "+str(url))

            #try again
            starttime=datetime.datetime.now()
            status = requests.post(
                url,
                headers= {
                    "Content-Type": "application/json",
                    "vcc-api-key": vccapikey,
                    "Authorization": "Bearer " + access_token
                },
                timeout=invoketimeout
            )
            endtime=datetime.datetime.now()

            Debug("Invoke Command retry duration: "+str(endtime-starttime))

            sjson = json.dumps(status.json(), indent=4)
            Debug("\nResult JSON: "+str(sjson))
            if status.status_code==200:
                if (status.json()["data"]["invokeStatus"]=="COMPLETED"):
                    Debug("Invoke command succesfully completed") 
                    return True
                else:
                    Error("Invoke command failed, API returned code "+status.json()["data"]["invokeStatus"])
                    return False
            else:
                Error("InvokeCommand failed again, webserver returned "+str(status.status_code)+", result: "+sjson)
                return False
        else:
            Debug("Returning False")
            return False

def HandleClimatizationCommand(vin,idx,command):
    global climatizationstoptimestamp

    if refresh_token:
        url = "https://api.volvocars.com/connected-vehicle/v2/vehicles/" + vin + '/commands/climatization-start'
        climatizationstoptimestamp=time.time()+30*60  #make sure we switch off after 30 mins
        nv=1
        
        if command=='Off':
            url = "https://api.volvocars.com/connected-vehicle/v2/vehicles/" + vin + '/commands/climatization-stop'
            nv=0
        
        # Set switch to give feedback to UI
        UpdateSwitch(vin,CLIMATIZATION,"Climatization",nv,command)

        if InvokeCommand(url,None,CLIMATIZATIONTIMEOUT): 
            Debug("Climatization Command succesfully completed") 
        else:
            Error("climatization did not start/stop")
            #reverse switch again
            ReverseSwitch(vin,CLIMATIZATION)

def HandleLockCommand(vin,idx,command):
    if refresh_token:
        url = "https://api.volvocars.com/connected-vehicle/v2/vehicles/" + vin + '/commands/lock'
        cmd = "LOCKED"
        message = None
        
        if command=='Off':
            url = "https://api.volvocars.com/connected-vehicle/v2/vehicles/" + vin + '/commands/unlock'
            cmd = "UNLOCKED"
            message = '{ "unlockDuration": 120 }'

        UpdateLock(vin,CARLOCKED,"CarLocked",cmd)

        if InvokeCommand(url,message,LOCKTIMEOUT): 
            Debug("Lock Command succesfully completed") 
        else:
            Error("Lock command failed")
            #reverse switch again
            ReverseLock(vin,CARLOCKED)

def HandleCommand(vin,command):
    if refresh_token:
        url = "https://api.volvocars.com/connected-vehicle/v2/vehicles/" + vin + '/commands/' + command

        if InvokeCommand(url,None,LOCKTIMEOUT): 
            Debug("Command "+command+" succesfully completed") 
        else:
            Error("Command "+command+" failed")
        
class BasePlugin:
    enabled = False
    def __init__(self):
        #self.var = 123
        return

    def onStart(self):
        global google_api_key,vccapikey,debugging,info,lastupdate,updateinterval,expirytimestamp,abrp_api_key,abrp_token,openweather_token
        Debug("OnStart called")

        #read params
        if Parameters["Mode6"] in {"-1","126"}:
            Domoticz.Debugging(int(Parameters["Mode6"]))
            debugging=True
            info=True
        elif Parameters["Mode6"] in {"62"}:
            Domoticz.Debugging(int(Parameters["Mode6"]))
            info=True
            debugging=False
        else:
            debugging=False
            info=True

        if debugging:
            DumpConfigToLog()

        #get openweather token
        openweather_token =Parameters["Mode4"]
        Debug("Openweather token = "+openweather_token)

       #get abrp_token 
        values=Parameters["Mode5"].split(":")
        if len(values)==2:
            Debug("We have a valid ABRP config")
            abrp_api_key=values[0]
            abrp_token=values[1]
            Debug("ABRP api key="+abrp_api_key+", token="+abrp_token)
        else:
            Debug("len="+str(len(values)))

        google_api_key=Parameters["Username"]
        vccapikey=Parameters["Mode1"]
        updateinterval=int(Parameters["Mode2"])
        if (updateinterval<100):
            Info("Updateinterval too low, correcting to 100 secs")
            updateinterval=99 # putting it too exact 100 might sometimes lead to update after 110 secs 
        lastupdate=time.time()-updateinterval-1 #force update
        expirytimestamp=time.time()-1 #force update

        #try to get token from file
        ReadTokenFromIniFile()

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
        elif Unit==CARHASMOVED:
            if debugging:
                if Command=='On':
                    UpdateSwitch(vin,CARHASMOVED,"Car has moved or is moving",1,Command)
                else:
                    UpdateSwitch(vin,CARHASMOVED,"Car has moved or is moving",0,Command)
        elif Unit==HONK:
            Debug("Send Honk command")
            HandleCommand(DeviceID,"honk")
        elif Unit==FLASH:
            Debug("Send Flash command")
            HandleCommand(DeviceID,"flash")
        elif Unit==HONKFLASH:
            Debug("Send Honk command")
            HandleCommand(DeviceID,"honk-flash")
        elif Unit==LOCKREDUCEDGUARD:
            Debug("Send Lock Reduced Guard command")
            HandleCommand(DeviceID,"lock-reduced-guard")
        elif Unit==UPDATENOW:
            Debug("Force Update")
            UpdateDevices()
        else:
            Debug("unknown command")

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
