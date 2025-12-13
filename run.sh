#!/bin/bash
# Run script for NYC Subway Sign
# Make sure to run with sudo for GPIO access

cd "$(dirname "$0")"
sudo python3 src/main.py

