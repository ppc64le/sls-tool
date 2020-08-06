#!/usr/bin/env python
# Copyright (c) International Business Machines  Corp., 2020
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or (at your option) any later version.
#
# This program is distributed in the hope that it would be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details
#  AUTHORS: manjuhr1@in.ibm.com, chetjain@in.ibm.com
#  PURPOSE: Stops SLS execution.
#           1. Kills SLS related processes including LTP tests
#           2. Updates status as ABORTED in REPORT.json file
#
#  SETUP:   1. Create or Edit ./sls_config file with test inputs
#           2. Install SLS: ./install_sls.py
#           3. Start SLS: ./start_sls.py <options>
#           4. If tests need to be stopped at any time : ./stop_sls.py
#

import os
import sys
import re
import datetime
import fcntl
import time
import json
from common_sls import *

ltp_vars = GetVars()
if not ltp_vars:
	exit(1)

#Get Log file location
if 'SLS_DIR' not in ltp_vars:
	logdir='/var/log/sls'
elif ltp_vars['SLS_DIR'].strip() != '':
	logdir=ltp_vars['SLS_DIR'].strip()
else:
	ltp_vars['SLS_DIR']='/var/log/sls'
	logdir='/var/log/sls'

slog = "%s/stop_sls.log" % logdir
lg(slog, "Trying to kill SLS processes...")
command = "ps -eaf|grep -e go_sls -e run_test -e runltp -e ltp-pan -e ltp -e growfiles|grep -v grep |grep -v stop_sls|awk '{print $2}'|tr '\n' '^'"
pids = RunCommand(command, slog, 2, 0).split('^')
for p in pids:
	if p == '':
		continue
	command = "kill -9 %s" % p
	lg(slog, command,0)
	RunCommand(command, slog, 2, 0)

lg(slog,'Let us wait 10 seconds and kill SLS processes if any...')
time.sleep(10)
command = "ps -eaf|grep -e go_sls -e run_test -e runltp -e ltp-pan -e ltp -e growfiles|grep -v grep |grep -v stop_sls|awk '{print $2}'|tr '\n' '^'"
pids = RunCommand(command, slog, 2, 0).split('^')
for p in pids:
	if p == '':
		continue
	command = "kill -9 %s" % p
	lg(slog,command,0)
	RunCommand(command, slog, 2, 0)

if not os.path.exists('%s/latest_log' % logdir):
	lg(slog,"%s/latest_log is not present" % logdir)
	exit(1)

f = open('%s/latest_log' % logdir, "r")
MASTER_FILE = "%s/REPORT.json" % f.read().strip()
f.close()
if not os.path.exists(MASTER_FILE):
	lg(slog,"Not Found: %s" % MASTER_FILE)
	exit(1)

lg(slog,'Trying to update Report.json ...')

#Update Report.json
lock_file = open('%s/ltp.lock' % logdir, "w")
while True:
	try:
		fcntl.lockf(lock_file.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
	except IOError:
		time.sleep(GetRandom(10))
	else:
		break

with open(MASTER_FILE, 'r') as g:
	REPORT = json.load(g)

REPORT['RESULTS']['STATUS'] = "ABORTED"
with open(MASTER_FILE, "w") as g:
	json.dump(REPORT, g)

g.close()

fcntl.flock(lock_file, fcntl.LOCK_UN)
fcntl.flock(lock_file, fcntl.LOCK_UN)
fcntl.flock(lock_file, fcntl.LOCK_UN)

#Unmount IO filesystems if any
lg(slog, 'Trying to umount sls related filesystems, if any...')
command = "mount |grep -e '/tmp/ltp-' -e '/tmp/ltp_'|awk '{print $3}'|tr '\n' '^'"
mntpoints = RunCommand(command, slog, 2, 0).strip().split('^')
mntpoints = [x for x in mntpoints if x]
for mp in mntpoints:
	lg(slog, 'Unmounting : %s' % mp)	
	command = 'umount %s' % mp
	lg(slog,command)
	if int(RunCommand(command, slog, 0, 0)) != 0:
		command = 'umount -f %s' % mp
		lg(slog,command)	
		if int(RunCommand(command, slog, 0, 0)) != 0:
			command = 'umount -l %s' % mp
			lg(slog,command)	
			if int(RunCommand(command, slog, 0, 0)) != 0:
				lg(slog,'Failed to umount : %s, please umount manually' % mp)
