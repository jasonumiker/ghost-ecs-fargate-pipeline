#!/bin/bash

# Restart the docker-entrypoint.sh every 14 minutes to trigger a new DB password rotation
echo "*/14 * * * * supervisorctl restart docker-entrypoint" >> crons.conf
crontab crons.conf