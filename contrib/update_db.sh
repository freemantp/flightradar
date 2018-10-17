#!/bin/bash
service modesmixer2 stop
sleep 5

rm /usr/share/modesmixer2/BaseStation2.sqb
mv /usr/share/modesmixer2/BaseStation.sqb /usr/share/modesmixer2/BaseStation2.sqb
cp /home/pi/adsb-playground/resources/BaseStation.sqb /usr/share/modesmixer2/BaseStation.sqb
chown modesmixer:modesmixer /usr/share/modesmixer2/BaseStation.sqb
chmod 644 /usr/share/modesmixer2/BaseStation.sqb
service modesmixer2 start
