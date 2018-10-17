#!/bin/bash

todays_date=`date "+%Y-%m-%d"`
dbfile=~/adsb-playground/resources/BaseStation.sqb

read -p "ModeS: " modes

SELECT_RESPONSE=`sqlite3 $dbfile "SELECT * FROM Aircraft WHERE ModeS = '$modes'"`

if [ -n "$SELECT_RESPONSE" ] ; then
    echo -e "\nThere is already a record in the database:"

    IFS='|' read -ra AIRCRAFT <<< "$SELECT_RESPONSE"    #Convert string to array

    echo -e "\tModeS:        ${AIRCRAFT[3]}"
    echo -e "\tRegistration: ${AIRCRAFT[6]}"
    echo -e "\tIcao Type:    ${AIRCRAFT[13]}"
    echo -e "\tType:         ${AIRCRAFT[14]}"    
    echo -e "\tOperator:     ${AIRCRAFT[21]}"
    exit
fi

read -p "Icao Type: " icaoType
read -p "Type: " type
read -p "Registration: " registration
read -p "Operator: " operator

modes=`echo $modes | xargs`
icaoType=`echo $icaoType | xargs`
type=`echo $type | xargs`
registration=`echo $registration | xargs`
operator=`echo $operator | xargs`

sql="INSERT INTO Aircraft (ModeS,ICAOTypeCode,Type,Registration,RegisteredOwners,FirstCreated,LastModified) VALUES"
sql="$sql ('$modes','$icaoType','$type','$registration','$operator','$todays_date','$todays_date');"

sqlite3 $dbfile "${sql}"

if [ $? -ne 0 ]; then
    echo "Insert failed"
fi
