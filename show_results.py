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
#  PURPOSE: Shows the SLS tests execution status.
#           1. Reads latest_log from SLS DIR
#           2. Reads REPORT.json file from SLS log directory 
#           3. Prints the results and status based on arguments
#
#  SETUP:   1. Create or Edit ./sls_config file with test inputs
#           2. Install SLS: ./install_sls.py
#           3. Start SLS: ./start_sls.py <options>
#           4. ./show_results.py <options> : shows tests results
#

import os
import sys
import re
import datetime
import fcntl
import time
import json
import argparse
from common_sls import *

#Parse Arguments
parser = argparse.ArgumentParser(description='Show LTP Results')
parser.add_argument('-c', action="store_true", dest="c", help='Show CPU Usage')
parser.add_argument('-m', action="store_true", dest="m", help='Show Memory Usage')
parser.add_argument('-s', action="store_true", dest="s", help='Show Test Scenarios')
parser.add_argument('-t', action="store_true", dest="t", help='Show Tests')
parser.add_argument('-i', action="store_true", dest="i", help='Show In Progress Tests')
parser.add_argument('-d', action="store_true", dest="d", help='Show Details of In Progress Tests')
args = parser.parse_args()

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

if not os.path.exists('%s/latest_log' % logdir):
	print("%s/latest_log is not present" % logdir)
	exit(1)

f = open('%s/latest_log' % logdir, "r")
MASTER_FILE = "%s/REPORT.json" % f.read().strip()
f.close()

if not os.path.exists(MASTER_FILE):
	print("Not Found: %s" % MASTER_FILE)
	exit(1)

lock_file = open('%s/ltp.lock' % logdir, "w")
while True:
	try:
		fcntl.lockf(lock_file.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
	except IOError:
		print("Please wait, trying read REPORT.json")
		time.sleep(GetRandom(10))
	else:
		break

with open(MASTER_FILE, 'r') as g:
	REPORT = json.load(g)
g.close()

tlog = '%s/ltp_show_results.log' % logdir
command = "ps -eaf|grep go_sls|grep -v grep|wc -l"
if int(RunCommand(command, tlog, 2, 0)) == 0 and REPORT['RESULTS']['STATUS'] == 'In Progress':
	REPORT['RESULTS']['STATUS'] = 'ABORTED'

print('------------------------------------------------------')
print(MASTER_FILE.replace('//','/'))
print('------------------------------------------------------')
print("STATUS   : %s" % REPORT['RESULTS']['STATUS'])
print("RUNTIME  : %s" % REPORT['RESULTS']['RUNTIME'])
print("PASS%%    : %s" % REPORT['RESULTS']['PASS%'])
print("FAIL%%    : %s" % REPORT['RESULTS']['FAIL%'])
print("SKIP%%    : %s" % REPORT['RESULTS']['SKIP%'])
print("CONF%%    : %s" % REPORT['RESULTS']['CONF%'])
print("BROK%%    : %s" % REPORT['RESULTS']['BROK%'])

START_FILE = MASTER_FILE.replace('REPORT.json','START.LTP_log')
if args.c:
	if os.path.exists(START_FILE):
		command = "cat %s|grep 'Idle CPU: '|awk '{print $6}'|tr '\n' '^'" % START_FILE
		freecpu = RunCommand(command, tlog, 2, 0)
		if freecpu != "":
			cpu = freecpu.split('^')
			cpu = [x for x in cpu if x.strip()]
			cpu_usage = "Avg CPU Usage : %d%%" % (100 - (eval("+".join(cpu))/len(cpu)))
			print(cpu_usage)
	else:
		print("%s file is not present" % START_FILE)

if args.m:
	if os.path.exists(START_FILE):
		command = "free -m | awk '{print $2}' | grep -v [a-z] | head -n 1"
		totalmem = int(RunCommand(command, tlog, 2, 0))
		command = "cat %s|grep 'Available free memory '|awk '{print $7}'|tr '\n' '^'" % START_FILE
		freemem = RunCommand(command, tlog, 2, 0)
		if freemem != "":
			mem = freemem.split('^')
			mem = [x for x in mem if x.strip()]
			memused = 100 - ((eval("+".join(mem))/len(mem)) * 100)/totalmem
			mem_usage = "Avg Memory Usage : %d%%" % memused
			print(mem_usage)
	else:
		print("%s file is not present" % START_FILE)

print("OVERVIEW : %s" % REPORT['RESULTS']['OVERVIEW'])

if args.i or args.d:
	print("")
	INPROGRESS = MASTER_FILE.replace('REPORT.json','IN-PROGRESS-TEST')
	if os.path.exists(INPROGRESS):
		print("\nIn Progress Tests:")
		print("-------------------")
		with open(INPROGRESS,'r') as g:
			inprog = g.readlines()
		g.close()
		for test in inprog:
			if test == '' or test == ' ' or test == '\n':
				continue
			print(test)
			if args.d:
				tst = test.split(':')[0]
				command = "ls -t /opt/ltp/output/|grep %s|head -1" % tst
				outfile = RunCommand(command, tlog, 2, 0)
				outfile = outfile.strip()
				if outfile == '':
					print('Output file for %s not found under /opt/ltp/output/' % tst)
				else:
					outputfile = "/opt/ltp/output/%s" % outfile
					if not os.path.exists(outputfile):
						print("Output file for %s not found under /opt/ltp/output/" % tst)
					else:
						command = "tail -5 /opt/ltp/output/%s" % outfile
						print(RunCommand(command, tlog, 2, 0))
						print("")
	else:
		print("%s file is not present" % INPROGRESS)


if args.s:
	print("")
	SCEN_FILE = MASTER_FILE.replace('REPORT.json','SCENARIO_LIST')
	if os.path.exists(SCEN_FILE):
		with open(SCEN_FILE,'r') as g:
			scenarios = g.readlines()
		g.close()	
		for scn in scenarios:
			print(scn.strip())
	else:
		print("%s file is not present" % SCEN_FILE)
if args.t:
	print("")
	tests = REPORT['TESTS']
	if tests != '':
		print('TESTS:\n----------')
		for test in tests:
			print(test + " " + str(tests[test]))
	else:
		print("No test report generated yet")
print('------------------------------------------------------\n')

fcntl.flock(lock_file, fcntl.LOCK_UN)
