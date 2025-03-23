#!/bin/bash

# Check if wlan0 is up or down
if /sbin/ifconfig wlan0 | grep -q "inet "; then
    # If wlan0 is up, bring it down
    /sbin/ifconfig wlan0 down
    echo "wlan0 is down."
else
    # If wlan0 is down, bring it up
    /sbin/ifconfig wlan0 up
    echo "wlan0 is up."
fi
