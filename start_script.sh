#!/usr/bin/env bash
#Configure web server

cd /usr/src/app 

#TODO: start cron jobs
# change python environment
source activate emission-load

# launch the webapp
./e-mission-py.bash load_cal_data.py
