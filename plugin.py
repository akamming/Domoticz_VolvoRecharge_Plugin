# Volvo Recharge (Full EV) plugin
#
# Author: akamming
#
"""
<plugin key="VolvoEV" name="Volvo Recharge (Full EV)" author="akamming" version="0.0.1" wikilink="http://www.domoticz.com/wiki/plugins/plugin.html" externallink="https://github.com/akamming/Domoticz_VolvoRecharge_Plugin">
    <description>
        <h2>Volvo Recharge (Full EV) plugin</h2><br/>
        Overview...
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>Feature one...</li>
            <li>Feature two...</li>
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>Device Type - What it does...</li>
        </ul>
        <h3>Configuration</h3>
        Configuration options...
    </description>
    <params>
        <param field="Username" label="Volvo On Call Username" required="true"/>
        <param field="Password" label="Volvo On Call Password" required="true" password="true"/>
        <param field="Mode1" label="Primary VCC API Key" required="true"/>
        <param field="Mode2" label="update interval in secs" required="true" default="900"/>
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
import time

#global vars
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

def Debug(text):
    if debugging:
        Domoticz.Log("DEBUG: "+str(text))

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
        Debug("Login successful!")
        Debug(response.json())

        #retrieve tokens
        access_token = response.json()['access_token']
        refresh_token = response.json()['refresh_token']
        expirytimestamp=time.time()+response.json()['expires_in']


        #after login: Get Vin
        GetVin()

    except requests.exceptions.RequestException as error:
        Debug("Login failed:")
        Debug(error)

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
        Debug("Refresh successful!")
        Debug(response.json())

        #retrieve tokens
        access_token = response.json()['access_token']
        refresh_token = response.json()['refresh_token']
        expirytimestamp=time.time()+response.json()['expires_in']

    except requests.exceptions.RequestException as error:
        Debug("Refresh failed:")
        Debug(error)


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

    except requests.exceptions.RequestException as error:
        Debug("Get vehicles failed:")
        Debug(error)

    vin = vjson["vehicles"][0]["id"]

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
        sjson=status.json()

        sjson = json.dumps(status.json(), indent=4)
        Debug("\nResult JSON:")
        Debug(sjson)
        return status.json()

    except requests.exceptions.RequestException as error:
        Debug("VolvoAPI failed:")
        Debug(error)

def UpdateSensor(vn,idx,name,tp,subtp,options,nv,sv):
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=name, Unit=idx, Type=tp, Subtype=subtp, DeviceID=vn, Options=options, Used=True).Create()
    Devices[vin].Units[idx].nValue = nv
    Devices[vin].Units[idx].sValue = sv
    Devices[vin].Units[idx].Update(Log=True)

def UpdateSelectorSwitch(vn,idx,name,options,nv,sv):
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=name, Unit=idx, TypeName="Selector Switch", DeviceID=vn, Options=options, Used=True).Create()
    Devices[vin].Units[idx].nValue = nv
    Devices[vin].Units[idx].sValue = sv
    Devices[vin].Units[idx].Update(Log=True)

def UpdateSwitch(vn,idx,name,nv,sv):
    Debug ("UpdateSwitch("+str(vn)+","+str(idx)+","+str(name)+","+str(nv)+","+str(sv)+" called")
    if (not vn in Devices) or (not idx in Devices[vn].Units):
        Domoticz.Unit(Name=name, Unit=idx, Type=244, Subtype=73, DeviceID=vn, Used=True).Create()
    Devices[vin].Units[idx].nValue = nv
    Devices[vin].Units[idx].sValue = sv
    Devices[vin].Units[idx].Update(Log=True)



def GetRechargeStatus():
    Debug("GetRechargeStatus() called")
    RechargeStatus=VolvoAPI("https://api.volvocars.com/energy/v1/vehicles/"+vin+"/recharge-status","application/vnd.volvocars.api.energy.vehicledata.v1+json")
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
                 float(CalculatedRange))

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
    elif connstatus=="CHARGING_SYSTEM_CHARGING":
        newValue=10
    elif connstatus=="CHARGING_SYSTEM_FAULT":
        newValue=20
    elif connstatus=="CHARGING_SYSTEM_UNSPECIFIED":
        newValue=30
    else:
        newValue=30

    #update selector switch for Charging Connection Status
    options = {"LevelActions": "|||",
              "LevelNames": "Idle|Charging|Fault|Unspecified",
              "LevelOffHidden": "false",
              "SelectorStyle": "1"}
    UpdateSelectorSwitch(vin,CHARGINGSYSTEMSTATUS,"chargingSystemStatus",options,
                 int(newValue),
                 float(newValue))


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
                Debug("Switch off climatization, timer expired")
                UpdateSwitch(vin,CLIMATIZATION,"Climatization",0,"Off")
            else:
                Debug("Climatization on, will stop in "+str(climatizationstoptimestamp-time.time())+" seconds")
        else:
            Debug("Climatization switched off, do nothing")


        #handle updates
        if time.time()-lastupdate>=updateinterval:
            # do updates
            Debug("Updating")
            lastupdate=time.time()
            GetRechargeStatus()
        else:
            Debug("Not updating, "+str(updateinterval-(time.time()-lastupdate))+" to update")
    else:
        Debug("No vin, do nothing")

def HandleClimatizationCommand(vin,idx,command):
    global climatizationstoptimestamp,climatizationoperationid

    if refresh_token:
        url = "https://api.volvocars.com/connected-vehicle/v2/vehicles/" + vin + '/commands/climatization-start'
        ct = "application/vnd.volvocars.api.connected-vehicle.climatizationstart.v2+json"
        climatizationstoptimestamp=time.time()+30*60  #make sure we switch off after 30 mins
        nv=1
        
        if command=='Off':
            url = "https://api.volvocars.com/connected-vehicle/v2/vehicles/" + vin + '/commands/climatization-stop'
            ct = "application/vnd.volvocars.api.connected-vehicle.climatizationstop.v2+json"
            nv=0
        


        try:
            Debug("URL: {}".format(url))
            status = requests.post(
                url,
                headers= {
                    "Content-Type": ct,
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
                    Debug("climatization did not start/stop, API returned code "+status.json()["data"]["invokeStatus"])
            else:
                Debug("climatizatation did not start/stop, webserver returned "+status.json()["status"])

        except requests.exceptions.RequestException as error:
            Debug("handleclimatization command failed:")
            Debug(error)


class BasePlugin:
    enabled = False
    def __init__(self):
        #self.var = 123
        return

    def onStart(self):
        global vocuser,vocpass,vccapikey,debugging,lastupdate,updateinterval,expirytimestamp

        Debug("OnStart Called")
        DumpConfigToLog()
        if Parameters["Mode6"]=="-1":
            Domoticz.Debugging(int(Parameters["Mode6"]))
            DumpConfigToLog()
            debugging=True
        else:
            debugging=False

        #initiate vars
        vocuser=Parameters["Username"]
        vocpass=Parameters["Password"]
        vccapikey=Parameters["Mode1"]
        updateinterval=int(Parameters["Mode2"])
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
        else:
            Debug("handle the rest")

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
            Domoticz.Log( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for DeviceName in Devices:
        Device = Devices[DeviceName]
        Domoticz.Log("Device ID:       '" + str(Device.DeviceID) + "'")
        Domoticz.Log("--->Unit Count:      '" + str(len(Device.Units)) + "'")
        for UnitNo in Device.Units:
            Unit = Device.Units[UnitNo]
            Domoticz.Log("--->Unit:           " + str(UnitNo))
            Domoticz.Log("--->Unit Name:     '" + Unit.Name + "'")
            Domoticz.Log("--->Unit nValue:    " + str(Unit.nValue))
            Domoticz.Log("--->Unit sValue:   '" + Unit.sValue + "'")
            Domoticz.Log("--->Unit LastLevel: " + str(Unit.LastLevel))
    return
