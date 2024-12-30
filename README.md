# Domoticz VolvoRecharge Plugin
domoticz plugin for Volvo vehicles
domoticzwrapper around Volvo API (https://developer.volvocars.com/apis/) so your car sensors can be integrated into your home automation use cases.

NEW: Triplog support (Still experimental)


## Features

### Volvo API
- availability status (https://developer.volvocars.com/apis/connected-vehicle/v2/endpoints/commands/#get-accessibility-status)
- recharge status (https://developer.volvocars.com/apis/energy/endpoints/recharge-status/)
- doors, windows and lock status, including locking and unlocking of doors (https://developer.volvocars.com/apis/connected-vehicle/endpoints/doors-windows-locks/)
- tyrepressure status (https://developer.volvocars.com/apis/connected-vehicle/endpoints/tyres/)
- service status (https://developer.volvocars.com/apis/connected-vehicle/endpoints/diagnostics/#get-diagnostic-values)
- start/stop climatisation (https://developer.volvocars.com/apis/connected-vehicle/endpoints/climate/)
- Retrieve Vehicle location (https://developer.volvocars.com/apis/location/v1/endpoints/location/#get-location)
- Retrieves Vehicle warnings (https://developer.volvocars.com/apis/connected-vehicle/v2/endpoints/warnings/)
- Honk/Flash commands commands (https://developer.volvocars.com/apis/connected-vehicle/v2/endpoints/lights-sound/), this requires AAOS cars to be at least on OTA 3.3.16

### Other
- syncs SOC and charging status to ABRP (https://documenter.getpostman.com/view/7396339/SWTK5a8w)
- Estimates the number of kwh's used and charged (since the api only reports differences in battery percentage, this is only an estimation and not very accurate)
- Retrieves outsidetemp from openweather (if openweather token configured)
- Logs all trips in triplog.csv (located in the directory of the plugin), requires configuring a Google API key in the settings (https://support.google.com/googleapi/answer/6158862?hl=en)

### Devices
pls look at the above links to API for device descriptions

There are 2 devices which can send commands to the volvo
- The CarLock switch can lock and unlock your car
- The climatization switch can start and stop climatizion.  
This last switch has a very simple implementatiation. If you start climatisation the switch will go off after 30 mins. This is just a timer and during this 30 mins you can stop the climatisation which was started by the plugin. The switch will not detect climatisation status when it was started using the app or the car itself (Limitation by the API: There is no API to check for climatisation status..)

And then there are several energy devices. Since the API does not allow reading the used or charged energy, these are just estimations: If the battery percentage rises or drops, the plugin assumes charging or using and so updates the kwh devices accordingly. homecharging is assumed if the battery percentage is rising and the location is within 25 meters from home.

## Setup and Update instructions

### Installations instructions: 
- go to the plugin directory
- give the command git clone https://github.com/akamming/Domoticz_VolvoRecharge_Plugin  
- restart domoticz
- (if you don't have a volco on call account) Create a Volvo on Call Username/password, which is linked to your vehicle. (basically: install the follow on call app on your handset and follow instructions)
- follow instructions on https://developer.volvocars.com/apis/docs/getting-started/ to register an app and copy/past the primary app vcc key in the plugin config
- Enter your username/password in the plugin config. (This seems to be depracated, currently Volvo enforces 2FA, see sector 2Factor authentication)
- Optional: 
   - Set a VIN if you connected more than one car to your volvo account. If empty the plugin will use the 1st car attached to your Volvo account
   - Set an update interval. If you don't pay Volvo for the API, you're only allowed to do 10.000 calls per day.. so make sure not to set the update interval too low. The plugin does 4 calls on every interval.
   - Set API_KEY and token of ABRP (format api_key:token) Token can be obtained from ABRP app (selecting Generic method at "live data" will give you the token). API_Key can bet obtained by contacting ABRP developer (see instructions at this link:  https://documenter.getpostman.com/view/7396339/SWTK5a8w )
   - Set a Google API Key for friendly names in the triplog
   - if in the domoticz settings the Longitude and Lattitude are correctly entered, the plugin will calculate the absolute distance to your car in km
   - Set openweather token (can be obtained by creating an account on this url https://home.openweathermap.org/users/sign_up )
   - Copy the lua script to your scripts/dzVents/scripts editor for some basic fun with this plugin (notifying on charging status, notifying on open window status, notifying on forgot to lock)

### 2 Factor Authentication
The plugin already supports 2FA as 2nd way of authentication. 

For this you will have to run the authorize.py script in the plugin directory (give the command "python authorize.py"). The script will request  your username/password, your vcc key and your One Time Password which will be sent to your email or SMS during the process. This script will create a token.ini file, after which the plugin can be restarted to use the new connection setting.

NOTE: In normal operations this has to be done only once, and after that the connection will remain. However is the token expires and on that moment domoticz is down, it will not renew in time and you have to re-authenticate using the authorize.py script. 

### Update instructions
- go the directory of your volvo plugin
- give the "git pull" command

### Security Considerations
This is a normal domoticz plugin, so as secure as every other one. But there are 2 addtional things to consider:
- With this plugin you can lock and unlock your car, so check your if your domoticz install, especially if it's connected to the internet, if it is really secure. You don't want someone to hack your domoticz and then also have access to your car.
- The tokens for connections with your car are stored in a token.ini file in the plugin directory. Make sure this file is only accessible by the user which runs domoticz. With the tokens in this file you can lock and unlock your car, find out where the car is parked, etc...

## Supported cars

### (Semi)Electric vehicles

This car was developed for recharge cars. Every car which is supported by the Volvo Energy API should theoretically work. This support can be found here: https://developer.volvocars.com/apis/energy/v1/overview/#availability

The plugin has been reported to work for
- Volvo EX30 (although climate and (un)lock commands don't work yet)
- Volvo XC40 Pure Electric
- Volco XC40 Pure Electric Twin
- Volco C40 Pure Electric
- Volvo C40 Pure Electric Twin
- Volvo XC60 PHEV
- V60 CC -22 with B4 engine

### Non electric Vehicles

Experimental support was added for non electric cars, for which the plugin only uses  the Connected Vehicle API. Theoretically this should work for all Volvo car models model years as of 2015, but not in all countries, for details: See https://developer.volvocars.com/apis/connected-vehicle/v2/overview/#availability

If you own a non electric vehicle and the API works, pls me know by registring an "issue"

## TODO
(requires update of the API on Volvo side, but if they are there i would like to add)
- Check Climatization status 
- Open/Close Open windows
- Set Charging Limits (Amperage/Percentage)
- Start/Stop Charging
- Honk/Flash (API is there, but doesn't work)
