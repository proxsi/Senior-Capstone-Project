#!/usr/bin/env python3
# Legacy launcher bound to the original Linux deployment directory.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Legacy shell-style launcher kept as a record of the original deployment command."""
import subprocess
import os

# Run from the deployment directory so relative log and data paths resolve there.
os.chdir('/home/devbox/project')
subprocess.run(['/home/devbox/project/bin/python', '-m', 'api_server.server'])