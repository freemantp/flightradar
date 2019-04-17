#!/bin/bash

service modesmixer2 stop
sleep 5

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
dbfile="$(dirname $SCRIPT_DIR)/resources/BaseStation.sqb"

rm /usr/share/modesmixer2/BaseStation2.sqb
mv /usr/share/modesmixer2/BaseStation.sqb /usr/share/modesmixer2/BaseStation2.sqb
cp $dbfile /usr/share/modesmixer2/BaseStation.sqb
chown modesmixer:modesmixer /usr/share/modesmixer2/BaseStation.sqb
chmod 644 /usr/share/modesmixer2/BaseStation.sqb
service modesmixer2 start
