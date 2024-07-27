-- script for notifying open windows and charging status, based on devices created in https://github.com/akamming/Domoticz_VolvoRecharge_Plugin
-- place in your domticz/scripts/dzVents/scripts dir or copy paste to the events editor in domoticz.
-- Adjust names of devices in the script to match your devices


return {
	on = {
		devices = {
			'Volvo-CarLocked',  -- Lock Device of the volvo,
			'Volvo-chargingSystemStatus', -- device which contains the charging state
			-- 'test'  -- for testing purposes
 		},
 		timer = {
 		    'Every 15 minutes'  -- how often do you want to check if for open windows in combination with Buienradar predicting rain?
 	    },
 	    httpResponses = {
			'Volvo-Buienradar' -- must match with the callback passed to the openURL command
		},
	},
	logging = {
		level = domoticz.LOG_ERROR, -- adjust to the whatever loglevel you like
		marker = 'Volvo',
	},
	execute = function(domoticz, item)
	    
        -- function to dump a table (for debugging purposes)
        function dump(o)
           if type(o) == 'table' then
              local s = '{ '
              for k,v in pairs(o) do
                 if type(k) ~= 'number' then k = '"'..k..'"' end
                 s = s .. '['..k..'] = ' .. dump(v) .. ','
              end
              return s .. '} '
           else
              return tostring(o)
           end
        end
	    
	    -- function to check if any window is open
	    function CheckWindows(notificationMessage)
	        windowsOpen=false
	        if notificationMessage==nil then
    	        domoticz.log('CheckWindows()',domoticz.LOG_DEBUG)
	        else
    	        domoticz.log('CheckWindows('..notificationMessage..')',domoticz.LOG_DEBUG)
	        end
    		windowsToBeChecked = { -- make sures these names match the names in domoticz  
    		    'Volvo-SunRoof',
    		    'Volvo-FrontLeftWindow',
    		    'Volvo-FrontRightWindow',
    		    'Volvo-RearLeftWindow',
    		    'Volvo-RearRightWindow'
    	    }
    	    -- checking the devices
		    for key,window in pairs(windowsToBeChecked) do
    		    -- check if window is open
		        domoticz.log("Checking window "..window,domoticz.LOG_DEBUG)
    		    local WINDOW=domoticz.devices(window) 
    		    if (WINDOW.active) then
    		        domoticz.log(window.." is open",domoticz.LOG_DEBUG)
    		        windowsOpen=true
    		        if notificationMessage==nil then
    		            domoticz.log('open window, but notification message not defined',domoticz.LOG_DEBUG)
		            else
        		        notificationMessage = notificationMessage..' ('..window..')'
        		        domoticz.notify("Volvo",notificationMessage,domoticz.PRIORITY_HIGH)
        		        domoticz.log("Notification sent: "..notificationMessage,domoticz.LOG_FORCE)
	                end	                
    		    else
    		        domoticz.log(window.." is closed, no need for action",domoticz.LOG_DEBUG)
    		    end
	        end
	        return windowsOpen -- let the caller know wheter a window was open
	    end
	    
	    -- function which calls buienradar for the rain forecast for the current location of the car
	    function callBuienRadar()
            LAT=domoticz.devices('Volvo-Lattitude')
            LON=domoticz.devices('Volvo-Longitude')
            domoticz.openURL({
				url = 'https://gpsgadget.buienradar.nl/data/raintext/?lat='.. LAT.sValue ..'&lon='..LON.sValue,
				method = 'GET',
				callback = 'Volvo-Buienradar', -- see httpResponses above.
		    })
        end
        
	    -- main
	    if item.isDevice then
    		domoticz.log('Device ' .. item.name .. ' was changed to ' ..item.nValue..','..item.sValue, domoticz.LOG_DEBUG)
    		
    		-- code to handle the changing of the lock status
    		if (item.name=='Volvo-CarLocked')  then -- Lock device of the Volvo, make sure this is the same name on which the script triggers 
        		-- check if device was locked
        		if (item.active) then
        		    domoticz.log('Device was locked',domoticz.LOG_DEBUG)
        		    -- Which devices do you want to check?
        		    CheckWindows('Auto afgesloten met open raam')
        		else
        		    domoticz.log('Device was unlocked, no need to do anything',domoticz.LOG_DEBUG)
        		end

            -- code to handle the charging status
            elseif (item.name=='Volvo-chargingSystemStatus' ) then  -- Lock device of the Volvo, make sure this is the same name on which the script triggers
                domoticz.log("Charging system Status changed, check if we have to notify",domoticz.LOG_DEBUG)
                if (item.sValue=='Charging') then
                    domoticz.log("Charging started, sending notification",domoticz.LOG_FORCE)
                    domoticz.notify("Volvo","Laden is gestart",domoticz.PRIORITY_MODERATE)
                elseif(item.sValue=='Done') then
                    domoticz.log("Charging stopped, sending notification",domoticz.LOG_FORCE)
                    domoticz.notify("Volvo","Laden is gereed",domoticz.PRIORITY_MODERATE)
                elseif(item.sValue=='Fault') then
                    domoticz.log("Charging Èrror, sending notification",domoticz.LOG_FORCE)
                    domoticz.notify("Volvo","Laden is gestopt, laadfout!",domoticz.PRIORITY_HIGH)
                elseif(item.sValue=='Scheduled') then
                    domoticz.log("Charging Scheduled, sending notification",domoticz.LOG_FORCE)
                    domoticz.notify("Volvo","Laden is gepland",domoticz.PRIORITY_MODERATE)
                else
                    domoticz.log("charging status can be ignored: "..item.sValue,domoticz.LOG_DEBUG)
                end
--          elseif (item.name=='test') then
--              callBuienRadar()
        	else
        	    domoticz.log('Unknown device: '..item.name,domoticz.LOG_ERROR)
        	end
        	
        elseif item.isTimer then   -- handle events on the timer
            domoticz.log("Handling timer event",domoticz.LOG_DEBUG)
            AVAILABLE=domoticz.devices('Volvo-availabilityStatus') -- name of the device which check availability of the API
            domoticz.log("Availability status = "..AVAILABLE.sValue,domoticz.LOG_DEBUG)
            if AVAILABLE.sValue=='Available' then
                --- Check1: Do we have open windows and if so: Call buienradar
                if CheckWindows() then
                    domoticz.log("one or more windows open, checking buienradar for a rainshower",domoticz.LOG_DEBUG)
                    callBuienRadar()
    			else
    			    domoticz.log('All windows closed, do nothing',domoticz.LOG_DEBUG)
    			end
    			
    			-- Check2 Has the car been unlocked too long (while not moving)
                lock=domoticz.devices('Volvo-CarLocked') -- name of the device which check availability of the API
        			
        		if (lock.active) then
        		    domoticz.log('Car  was  locked '..lock.lastUpdate.minutesAgo..' minutes Ago',domoticz.LOG_DEBUG)
        		else
        		    domoticz.log('Car was unlocked'..lock.lastUpdate.minutesAgo..' minutes ago',domoticz.LOG_DEBUG)
        		    if lock.lastUpdate.minutesAgo>15 then
    		            domoticz.notify('Volvo','Auto staat al '..lock.lastUpdate.minutesAgo..' minuten stil maar is niet afgesloten',domoticz.PRIORITY_HIGH)
    		            domoticz.log('sent notification Auto staat stil maar is niet afgesloten',domoticz.LOG_FORCE)
        		    end
        		end
            else
                domoticz.log("Car unavailable, do nothing",domoticz.LOG_DEBUG)
            end
            
        elseif item.isHTTPResponse then -- we have a buienradar result, check for rainshower and notify if needed
    	    domoticz.log('Volvo script called for object '..dump(item),domoticz.LOG_DEBUG)
    	    domoticz.log('Number of lines '..#item.lines,domoticz.LOG_DEBUG)
            if item.hasLines then
                -- we have data
                if (#item.lines==24) then
                    NextRainShower=120  -- 100 is treated as no shower coming
                    for i=#item.lines,1,-1 do
                        domoticz.log("inspecting line "..i..' '..item.lines[i],domoticz.LOG_DEBUG)
                        if tonumber(string.sub(item.lines[i],1,3))>0 then
                            NextRainShower=(i-1)*5
                        end
                    end
                    if NextRainShower<120 then
                        -- Rain expected, check windows
            		    CheckWindows('Open raam en bui verwacht in '..NextRainShower..' minuten')
                    else
                        domoticz.log('No rain expected',domoticz.LOG_DEBUG)
                    end
                else
                    domoticz.log('weird answer from Buienradar', domoticz.LOG_ERROR)
                end
            else
                domoticz.log('Empty result by Buienradar',domoticz.LOG_ERROR)
            end
        else
            domoticz.log("Unknown event type",domoticz.LOG_ERROR)
        end
	end
}
