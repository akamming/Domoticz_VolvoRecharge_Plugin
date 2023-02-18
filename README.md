# Domoticz VolvoRechargexi Plugin
domoticz plugin for Volvo Recharge Full EV vehicles

domoticzwrapper around Volvo API (https://developer.volvocars.com/apis/) so your car sensors can be integrated into your home automation use cases.
##Features
- recharge status (https://developer.volvocars.com/apis/energy/endpoints/recharge-status/)
- doors, windows and lock status, including locking and unlocking of doors (https://developer.volvocars.com/apis/connected-vehicle/endpoints/doors-windows-locks/)
- start/stop climatisation (https://developer.volvocars.com/apis/connected-vehicle/endpoints/climate/)

## Devices
pls look at the above links to API for device descriptions

There are 2 devices which can send commands to the volvo
- The CarLock device can lock and unlock your car
- The climatisation device can start and stop navigation.  This switch works very simple. If you start climatisation the switch will go off after 30 mins. This is just a timer and during this 30 mins you can stop the climatisation which was started by the plugin. The switch will not detect climatisation status when it was started using the app or the car itself (Limitation by the API: There is no API to check for climatisation status..)

## Instructions
- go to the plugin 
- (if you don't have a volco on call account) Create a Volvo on Call Username/password, which is linked to your vehicle. (basically: install the follow on call app on your handset and follow instructions)
- Enter the username/password in the plugin config.
- follow instructions on https://developer.volvocars.com/apis/docs/getting-started/ to register an app and copy/past the primary app key in the plugin config
- Optional: 
   - Set a VIN if you connected more than one car to your volvo account. If empty the plugin will use the 1st car attached to your Volvo account
   - Set an update interval. If you don't pay Volvo for the API, you're only allowed to do 10.000 calls per day.. so make sure not to set the update interval too low. The plugin does 4 calls on every interval.

## Security
This is a normal domoticz plugin, so as secure as every other one. However since with this plugin you can lock and unlock your car, check your if your domoticz install, especially if it's connected to the internet, if it is really secure.You don't want someone to hack your domoticz and then also have access to your car 

## Testing
Reported to work for
- Volvo XC40 Pure Electric
- Volco XC40 Pure Electric Twin
- Volco C40 Pure Electric
- Volvo C40 Pure Electric Twin
If you tested with another vehicle, pls let me know by reporting an "issue" in this repository, i will add to the doc

## TODO
I would really like to add API calls like
- https://api.volvocars.com/connected-vehicle/v1/vehicles/{vin}/warnings
- https://api.volvocars.com/connected-vehicle/v1/vehicles/{vin}/tyres
- https://developer.volvocars.com/apis/connected-vehicle/endpoints/diagnostics/
However i noticed that the output values are strings (e.g. fronleft.value for a tyre) which are different thant the docs. And since i cannot force to test all values on my car: If anyone can help me on correct documenation, let me know (by reporting an "issue") 
