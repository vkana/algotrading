#!/bin/bash

# Run the Python script in the background with nohup
nohup python3 blshlimit.py > /dev/null 2>&1 &

# Optionally, save the process ID (PID) to a file
echo $! > scripts.pid

#nohup python3 avg_testaccount.py > /dev/null 2>&1 &
nohup python3 roth_strat.py >> roth.log 2>&1 &

echo $! >> scripts.pid

# You can also add a message or other commands
echo "Script started in the background."
pgrep python -af

