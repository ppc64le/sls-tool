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
#  PURPOSE: This script get called internally from start_sls.py
#           1. Parses the arguments.
#           2. Spawns a process to kill SLS processes if there is OOM
#           3. If start_sls.py is called with -r:
#              3.1 Parse scenario file given as input
#              3.2 Calls execute scenario for each line in scenario file
#           4. If start_sls.py is called to execute one more focus area:
#              4.1 Creates list of tests to execute
#              4.2 Creates a scenario with subset of tests to execute continously until TEST_HOURS reached
#              4.3 Calls execute scenario to execute a scenario
#              4.4 Waits for scenario to complete, if required.
#              4.5 Once TST_HOURS completes, concludes testing by updating REPORT.json
#
#  SETUP:   1. Create or Edit ./sls_config file with test inputs
#           2. Install SLS: ./install_sls.py
#           3. Start SLS: ./start_sls.py <options>
#           4. go_sls.py will get called by ./start_sls.py
#

import os
import sys
import re
import argparse
import datetime
import multiprocessing
import subprocess
import threading
import fcntl
import time
import json
import signal
from common_sls import *

def usage():
	print("\n--------------------------------------------------------------")
	print("Usage: ./start_sls.py  -b -i -n -t -s \"Test Suites\" -R <Scenario File>")
	print(" -b --> Runs Base Tests")
	print(" -i --> Runs IO Tests")
	print(" -n --> Runs NFS Tests")
	print(" -t --> Runs Network Tests")
	print(" -s --> Run with Test suites. ex:\"syscalls,commands,fs\"")
	print(" -r --> Run with Scenario File")
	print("----------------------------------------------------------------\n")
	exit(1)

def signal_handler(signum, frame):
    signal.signal(signum, signal.SIG_IGN)
    ltp_vars = GetVars()
    if not ltp_vars:
        exit(1)
    if 'SLS_DIR' not in ltp_vars:
        ltp_vars['SLS_DIR'] = '/var/log/sls/'
    elif ltp_vars['SLS_DIR'].strip() == '': 
        ltp_vars['SLS_DIR'] = '/var/log/sls/'
    sls_logdir = ltp_vars['SLS_DIR']
    tlog = "%s/go_sls.log" % sls_logdir
    log = os.environ['TC_OUTPUT'] + '/START.LTP_log'
    MASTER_FILE = os.environ['TC_OUTPUT'] + '/REPORT.json'  
    with open(MASTER_FILE, 'r') as g:
        REPORT = json.load(g)
    g.close()
    REPORT['RESULTS']['STATUS'] = 'ABORTED: STOPPED_BY_OS'
    with open(MASTER_FILE, 'w') as g:
        json.dump(REPORT, g)
    g.close()

    line = "Updated STATUS to ABORTED: STOPPED_BY_OS in signal handler"
    lg(log, line, 0)
    os.killpg(0, signal.SIGINT)
    cleanup(log,tlog)

START_TIME = datetime.datetime.now()
str_time = START_TIME.strftime('%Y%m%d%H%M%S')

def call_ltp(testcase, iterations, suite, dat, str_time, sls_logdir):
	command = "./run_test.py %s %d %s %s %s %s > %s/run_test.log 2>&1" % (testcase, iterations, suite, dat, str_time, sls_logdir, sls_logdir)
	os.system(command)

ltp_threads = []
test_pids = []
def execute_scenario(tests_scenario, sls_logdir):
	test_pids = []
	ltp_threads = []

	tcount = 0
	for test in tests_scenario:
		testcase = test.split('(')[0]
		suite = test.split('(')[1].split('|')[0]
		iterations = int(test.split('|')[1].replace(')',''))

		d = datetime.datetime.now()
		dat = "%s%s" % (d.strftime('%Y%m%d%H%M%S'), str(d.microsecond)[:3])
		dat2 = "%s/%s/%s,%s:%s:%s" % (d.strftime('%Y'),d.strftime('%m'),d.strftime('%d'),d.strftime('%H'),d.strftime('%M'),d.strftime('%S'))
		dat = dat.strip()

		in_progess_file = os.environ['TC_OUTPUT'] + '/IN-PROGRESS-TEST'
		f = open(in_progess_file, "a")
		line = "%s:%s:%d: %s\n" % (testcase, suite, iterations, dat2)
		f.write(line)
		f.close()

		th = threading.Thread(target=call_ltp, args=(testcase, iterations, suite, dat, str_time, sls_logdir,))
		th.start()

		ltp_threads.append(th)
		
	#Wait till this scenario completes
	if re.search('YES', os.environ['WAIT_SCENARIO'], re.M|re.I):
		line = "Waiting for scenario to complete"
		lg(log, line, 0)
		for th in ltp_threads:
			th.join()

	
#Read LTP variables from ./sls_config file
ltp_vars = GetVars()
if not ltp_vars:
	exit(1)
if 'SLS_DIR' not in ltp_vars:
	ltp_vars['SLS_DIR'] = '/var/log/sls/'
elif ltp_vars['SLS_DIR'].strip() == '':
	ltp_vars['SLS_DIR'] = '/var/log/sls/'
sls_logdir = ltp_vars['SLS_DIR']

log = os.environ['TC_OUTPUT'] + '/START.LTP_log'
parser = argparse.ArgumentParser(description='Start SLS program')

parser.add_argument('-t', action="store_true", dest="t", help='Network Tests')
parser.add_argument('-i', action="store_true", dest="i", help='IO Tests')
parser.add_argument('-b', action="store_true", dest="b", help='BASE Tests')
parser.add_argument('-n', action="store_true", dest="n", help='NFS Tests')
parser.add_argument('-s', action="store", dest="s", nargs="+", help='Test Suites')
parser.add_argument('-r', action="store", dest="r", nargs="+", help='Run with Sceanrio file')
parser.add_argument('-x', action="store", dest="x", nargs="+", help='Exclude Tests')

args = parser.parse_args()

b = args.b
i = args.i
t = args.t
n = args.n
r = args.r
s = args.s

if not ( t or b or i or n or r or s):
	usage()

#Export Omit list
omit_list = GetVars('./tc_group')
for k,v in omit_list.items():
	os.environ[str(k)] = str(v)	

#Get Machine Info
mlog = os.environ['TC_OUTPUT'] + '/MACHINE_INFO'
MachineInfo(mlog, ltp_vars)

#Set OOM Killer
lg(log, "[go_sls] Starting SLS OOM Monitor. Kills nasty OOM process", 0, 1)
olog = '%s/oom_debug' % sls_logdir
process = multiprocessing.Process(target=OOMKill, args=(olog,log))
process.start()

#write empty REPORT.json
MASTER_FILE=os.environ['TC_HTML_PATH'] + '/REPORT.json'
OUTPUT = {}
RESULTS = {}
RESULTS['PASS%'] = 0
RESULTS['FAIL%'] = 0
RESULTS['SKIP%'] = 0
RESULTS['CONF%'] = 0
RESULTS['BROK%'] = 0
RESULTS['STATUS'] = 'In Progress'
RESULTS['RUNTIME'] = '0:00:00'
RESULTS['OVERVIEW'] = ''

OUTPUT['RESULTS'] = RESULTS

TESTS = {}
OUTPUT['TESTS'] = TESTS
with open(MASTER_FILE, 'w') as outfile:
	json.dump(OUTPUT, outfile)
outfile.close()

tlog = '%s/go_sls.log' % sls_logdir
command = "rm -f %s/go_sls.log" % sls_logdir
RunCommand(command, None, 0, 0)
command = "echo '' > %s/run_test.log" % sls_logdir
RunCommand(command, tlog, 1, 0)
command = "echo '' > %s/oom_debug" % sls_logdir
RunCommand(command, tlog, 1, 0)

command = "echo '' > %s/sls_skip_conf_brok" % sls_logdir
RunCommand(command, tlog, 1, 0)

command = "rm -f %s/ltp-*/test.img" % sls_logdir
RunCommand(command, tlog, 0, 0)

command = "mkdir -p  /opt/ltp/results"
RunCommand(command, tlog, 1, 1)
command = "rm -rf /opt/ltp/results/*"
RunCommand(command, tlog, 1, 1)

command = "mkdir -p  /opt/ltp/output"
RunCommand(command, tlog, 1, 1)
command = "rm -rf /opt/ltp/output/*"
RunCommand(command, tlog, 1, 1)

RunCommand('ulimit -l unlimited', tlog, 0, 0)
RunCommand('ulimit -n 99999', tlog, 0, 0)

#Get SLS version
sls_version = RunCommand("cat ./sls_version |grep '^tag'|awk '{print $2}'", tlog, 2, 0).strip()
sls_version = "SLS VERSION: %s" % sls_version
lg(log, sls_version)

#Drop Cache memory
lg(log, "Executing sync command", 0)
RunCommand('sync', tlog, 0, 0)
lg(log, "Executing drop cache: echo 3 > /proc/sys/vm/drop_caches", 0)
RunCommand('echo 3 > /proc/sys/vm/drop_caches', tlog, 0, 0)

#Register kill signal handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)
signal.signal(signal.SIGABRT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

FOCUS_AREA=""
if t:
	FOCUS_AREA="%s %s" % (FOCUS_AREA, os.environ['NW1_LIST'])
if n:
	FOCUS_AREA="%s %s" % (FOCUS_AREA, os.environ['NFS_LIST'])
TCP_NFS_LIST = FOCUS_AREA

if b:
	FOCUS_AREA="%s %s" % (FOCUS_AREA, os.environ['BASE_LIST'])
if i:
	FOCUS_AREA="%s %s" % (FOCUS_AREA, os.environ['IO_LIST'])


ltp_bin = os.environ['ltp_bin']
full_omit_list = os.environ['FULL_OMIT_LIST']
ltp_path = os.environ['ltp_path']
ITR_NUM = []; TS = []; TCP_LIST=''; TCP_SUITE = ''; TCP_READY = ''; TWAIT = "None|None"

#Get total number of tests
command = "ls -1 %s| grep -v -E \"%s\" | grep -v \"^[1-9]\"|wc -l" % (ltp_bin, full_omit_list)
total_tests = int(RunCommand(command, tlog, 2, 0))
total_tests = total_tests - 1

#Get Tests List
lg(log, "Preparing all tests list ...", 0)
command = "ls -1 %s| grep -v -E \"%s\" | sort -R|grep -v \"^[1-9]\"|tr '\n' '^'" % (ltp_bin, full_omit_list)
output = RunCommand(command, tlog, 2, 0)
if FOCUS_AREA == '' and not s:
	test_suite = output.split('^')
	test_suite = [x for x in test_suite if x]
else:
	all_test_suite = output.split('^')
	all_test_suite = [x for x in all_test_suite if x]
	test_suite = []
	focus_suites = []
	if s:
		AREALIST = s[0].split(',')
	else:
		AREALIST = FOCUS_AREA.split(' ')
	AREALIST = [x for x in AREALIST if x]
	for fcs in AREALIST:
		if fcs != '':
			command = "ls /opt/ltp/runtest/|grep %s|wc -l" % fcs
			if int(RunCommand(command, tlog, 2, 0)) != 0:
				focus_suites.append('/opt/ltp/runtest/%s' % fcs)

	for tst in all_test_suite:
		command = "grep %s %s|wc -l" % (tst, " ".join(focus_suites))
		if int(RunCommand(command, tlog, 2, 0)) != 0:
			test_suite.append(tst)
	
	total_tests = len(test_suite) - 1

command = 'echo "ALL TESTS : %s" >> %s/go_sls.log' % (" ".join(test_suite),sls_logdir)
RunCommand(command, tlog, 0, 0)

#Check if wait is required for each scenario to complete
if ('WAIT_SCENARIO' not in ltp_vars):
	os.environ['WAIT_SCENARIO'] = 'YES'
	ltp_vars['WAIT_SCENARIO'] = 'YES'
elif ltp_vars['WAIT_SCENARIO'] == '':
	os.environ['WAIT_SCENARIO'] = 'YES'
else:
	os.environ['WAIT_SCENARIO'] = ltp_vars['WAIT_SCENARIO']

if t or n:
	if b or i:
		os.environ['WAIT_SCENARIO'] = ltp_vars['WAIT_SCENARIO']
	else:
		if ltp_vars['WAIT_SCENARIO'] == 'NO':
			lg(log, "Overriding WAIT_SCENARIO to YES")
		os.environ['WAIT_SCENARIO'] = 'YES'
net_or_nfs = 0
if s:
	tsuites = s[0].split(',')
	tsuites = [x for x in tsuites if x]
	tests_list = GetVars('./tc_group')
	NW1_TESTS = tests_list['NW1_LIST'].strip().split(' ')
	NW1_TESTS = [x for x in NW1_TESTS if x]
	NW2_TESTS = tests_list['NW2_LIST'].strip().split(' ')
	NW2_TESTS = [x for x in NW2_TESTS if x]
	NFS_TESTS = tests_list['NFS_LIST'].strip().split(' ')
	NFS_TESTS = [x for x in NFS_TESTS if x]
	for suite in tsuites:
		suite = suite.strip()
		if suite in NW1_TESTS or suite in NW2_TESTS or suite in NFS_TESTS:
			net_or_nfs = 1
			break
	if net_or_nfs == 1:
		os.environ['WAIT_SCENARIO'] = 'YES'

network_fail = 0

scen = 0
scenario_file = "%s/SCENARIO_LIST" % os.environ['TC_OUTPUT']
#If Scaenario file given as input
if r:
	rfile = r[0]
	with open(rfile) as fp:
		lines = fp.readlines()
	fp.close()

	#Check if network variables available to export
	lnum=1; network_testing = 0
	for l in lines:
		if re.search('HOST', l, re.M) and re.search('=', l, re.M):
			network_testing = 1
			if len(l.split('=')) != 2:
				line = "Wrong line number:%d  : %s" % (lnum,l)
				lg(log, line, 0)
				network_fail = 1
				process.terminate()
				os.killpg(0, signal.SIGINT)
				cleanup(log, tlog)
				exit(1)
			key = l.split('=')[0]
			val = l.split('=')[1]
			os.environ[key] = val
			ltp_vars[key] = val
			lg(scenario_file,l,0)	
		lnum += 1

	for l in lines:
		if re.search('HOST', l, re.M) and re.search('=', l, re.M):
			continue
		test_list = []
		if l == '' or l == ' ' or l.startswith('#'):
			continue
		for test in  l.split(':')[3].split(' '):
			if test == '':
				continue
			test_list.append(test.strip())	
			line = "Test : %s will be executed" % test.strip()
			lg(log, line, 0)

		d = datetime.datetime.now()
		dat = "%s/%s/%s,%s:%s:%s" % (d.strftime('%Y'),d.strftime('%m'),d.strftime('%d'),d.strftime('%H'),d.strftime('%M'),d.strftime('%S'))
		line = "[%s] [go_sls] [notice] Scenario_%d:  %s\n" % (dat,scen," ".join(test_list))
		f = open(scenario_file, "a")
		f.write(line)
		f.close()

		execute_scenario(test_list, sls_logdir)
		scen += 1

		lg(log, " ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ", 0)
		GetFreeCPU(log, tlog)
		GetFreeMem(log, tlog)
		GetFsSpace(log, tlog)
		if network_testing == 1 and CheckNw(log, tlog, ltp_vars) == 1:	
			lg(log, 'Network check failed, exiting...')
			network_fail = 1
			process.terminate()
			cleanup(log, tlog)
			os.killpg(0, signal.SIGINT)
			break
		time.sleep(2)
	lg(log, "Completed all test scenario execution.", 0)

	#Update STATUS in REPORT.json
	lock_file = open('%s/ltp.lock' % sls_logdir, "w")
	while True:
		line = "Trying to update STATUS to COMPLETE in REPORT.json"
		lg(log, line, 0)
		try:
			fcntl.lockf(lock_file.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
		except IOError:
			time.sleep(GetRandom(10))
		else:
			break
	with open(MASTER_FILE, 'r') as g:
		REPORT = json.load(g)
	g.close()
	if network_fail == 0:
		REPORT['RESULTS']['STATUS'] = 'Completed'
	else:
		REPORT['RESULTS']['STATUS'] = 'ABORTED: RHOST_DOWN'

	CURRENT_TIME = datetime.datetime.now()
	REPORT['RESULTS']['RUNTIME'] = str(CURRENT_TIME - START_TIME)
	with open(MASTER_FILE, 'w') as g:
		json.dump(REPORT, g)
	g.close()
	fcntl.flock(lock_file, fcntl.LOCK_UN)
	line = "Updated STATUS to COMPLETE in REPORT.json"
	lg(log, line, 0)
	lg(log, "Completed full suite, Thanks for using SLS Tool", 0)
	process.terminate() 
	cleanup(log, tlog)
	exit(0)

if 'TEST_HOURS' in ltp_vars:
	TEST_HOURS = int(ltp_vars['TEST_HOURS'].strip())
else:
	TEST_HOURS = 72

END_TIME = START_TIME + datetime.timedelta(hours=TEST_HOURS)
line = "LTP Tests are starting at : %s" % START_TIME
lg(log, line, 0)
line = "LTP Tests will run for %d hours and will end by : %s" % (TEST_HOURS, END_TIME)
lg(log, line, 0)
line = "Scenario completion criteria: %s" % os.environ['WAIT_SCENARIO'].strip()
lg(log, line, 0)


while True:
	#Pick tests for scenario
	tests_scenario = []
	if 'MIN_TEST_PER_SCENARIO' in ltp_vars:
		min_test_scenario = int(ltp_vars['MIN_TEST_PER_SCENARIO'].strip())
	else:
		min_test_scenario = 3

	if 'MAX_TEST_PER_SCENARIO' in ltp_vars:
		max_test_scenario = int(ltp_vars['MAX_TEST_PER_SCENARIO'].strip())
	else:
		max_test_scenario = 8

	if max_test_scenario > min_test_scenario:
		total_tests_scenario = GetRandom(max_test_scenario, min_test_scenario)
	else:
		total_tests_scenario = max_test_scenario

	if 'MUST_TEST' in ltp_vars:
		if ltp_vars['MUST_TEST'].strip() != '':
			must_tests = ltp_vars['MUST_TEST'].strip().split(',')
			must_tests = [x for x in must_tests if x]
			if max_test_scenario > len(must_tests):
				total_tests_scenario = max_test_scenario - len(must_tests)
		if total_tests_scenario < 0:
			total_tests_scenario = 0
		elif total_tests_scenario > min_test_scenario:
			total_tests_scenario = GetRandom(total_tests_scenario, min_test_scenario)
	tlist = []
	for x in range(total_tests_scenario):
		valid_test = 0
		while valid_test == 0:
			#Pick a Random test
			if total_tests <= 0:
				test = test_suite[0]
			else:
				rnum = GetRandom(total_tests, 0)
				if rnum >= len(test_suite):
					rnum = len(test_suite) - 1
				test = test_suite[rnum]
			if test == "" or test == " ":
				continue
			test = test.strip()

			#If not valid test, then pick some other test
			suite_iter = GetSuiteIterations(tlog, test, ltp_vars)		
			if suite_iter[1] == 0:
				continue

			#If already running, then pick some other test
			command = "ps -eaf|grep %s|grep -v grep|wc -l" % (test)
			if int(RunCommand(command, tlog, 2, 0)) != 0:
				continue

			#Check if skip or brok or conf count this test is more than 2, if so dont pick
			command = "cat %s/sls_skip_conf_brok|grep -w '%s:%s'|wc -l" % (sls_logdir, test,suite_iter[0])
			if int(RunCommand(command, tlog, 2, 0)) >= 2:
				continue

			#If test is already picked in this scenario, pick another
			tentry = "%s|%s" % (test, suite_iter[0])
			if tentry in tlist:
				valid_test = 0
				continue

			#If test is part of EXCLUDE_TEST, exclude it
			if 'EXCLUDE_TEST' in ltp_vars:
				if ltp_vars['EXCLUDE_TEST'] != '':
					etests = ltp_vars['EXCLUDE_TEST'].split(',')
					if test in etests:
						continue

			tlist.append(tentry)

			#If test belongs to Network focus area, cap iterations max to 10
			if re.search(suite_iter[0], os.environ['NW1_LIST'], re.M):
				if suite_iter[1] > 10:
					suite_iter[1] = 10
			if re.search(suite_iter[0], os.environ['NW2_LIST'], re.M):
				if suite_iter[1] > 10:
					suite_iter[1] = 10
			if re.search(suite_iter[0], os.environ['NFS_LIST'], re.M):
				if suite_iter[1] > 10:
					suite_iter[1] = GetRandom(10)

			#If network_fail then pick skip NFS and Network tests
			if network_fail == 1:
				if re.search(suite_iter[0], os.environ['NW1_LIST'], re.M):
					iline = 'Ignoring network test:%s, as RHOSTS ping failed' % test
					lg(log, iline, 0)
					continue

				if re.search(suite_iter[0], os.environ['NW2_LIST'], re.M):
					iline = 'Ignoring network test:%s, as RHOSTS ping failed' % test
					lg(log, iline, 0)
					continue

				if re.search(suite_iter[0], os.environ['NFS_LIST'], re.M):
					iline = 'Ignoring NFS test:%s, as RHOSTS ping failed' % test
					lg(log, iline, 0)
					continue

			
			test_detail = "%s(%s|%d)" % (test, suite_iter[0], suite_iter[1])
			tests_scenario.append(test_detail)
			valid_test = 1

	#Add must test testcases
	if 'MUST_TEST' in ltp_vars:
		must_tests = ltp_vars['MUST_TEST'].strip().split(',')
		must_tests = [x for x in must_tests if x]
		for test in must_tests:
			test = test.strip()
			if test == '':
				continue
			if test in tests_scenario:
				continue

			#If already running, then pick some other test
			command = "ps -eaf|grep %s|grep -v grep|wc -l" % (test)
			if int(RunCommand(command, tlog, 2, 0)) != 0:
				line = "Must test:%s, already running. So not picking it for this scenario" % test
				lg(log, line, 0)
				continue

			suite_iter = GetSuiteIterations(tlog, test, ltp_vars)
			if suite_iter[1] == 0:
				lg(log, suite_iter[0], 0)
				continue

			#If test belongs to Network focus area, cap iterations max to 10
			if re.search(suite_iter[0], os.environ['NW1_LIST'], re.M):
				if suite_iter[1] > 10:
					suite_iter[1] = 10
			if re.search(suite_iter[0], os.environ['NW2_LIST'], re.M):
				if suite_iter[1] > 10:
					suite_iter[1] = 10
			if re.search(suite_iter[0], os.environ['NFS_LIST'], re.M):
				if suite_iter[1] > 10:
					suite_iter[1] = GetRandom(10)

			#Add test to test list
			test_detail = "%s(%s|%d)" % (test, suite_iter[0], suite_iter[1])
			tests_scenario.append(test_detail)

	if len(tests_scenario) == 0:
		lg(log, "Not allowed to start any new tests, sleeping for a minute", 0)
		time.sleep(60)
	else:		
		d = datetime.datetime.now()
		dat = "%s/%s/%s,%s:%s:%s" % (d.strftime('%Y'),d.strftime('%m'),d.strftime('%d'),d.strftime('%H'),d.strftime('%M'),d.strftime('%S'))
		line = "[%s] [go_sls] [notice] Scenario_%d:  %s\n" % (dat,scen," ".join(tests_scenario))
		f = open(scenario_file, "a")
		f.write(line)
		f.close()

		#Check free memory and launch only 1 test if less tahn 10% memory is available
		command = "free -m | awk '{print $2}' | grep -v [a-z] | head -n 1"
		total_mem = int(RunCommand(command, tlog, 2, 0))
		command = "free -m | awk '{print $4}' | grep -v [a-z] | head -n 1"
		free_mem = int(RunCommand(command, tlog, 2, 0))
		free_mem_percent = (free_mem * 100) / total_mem
		if free_mem_percent <= 10:
			line = "Alert !! Less than 10%% memory is available, so launching only 1 test for this scenario"
			lg(log, line, 0)
			test = tests_scenario[-1].split('(')[0]
			testsuite = tests_scenario[-1].split('(')[1].split('|')[0]
			tests_scenario = []
			test_detail = "%s(%s|1)" % (test,testsuite)
			tests_scenario.append(test_detail)
			line = "[%s] [go_sls] [info] Starting only 1 test:%s for 1 iteration" % (dat, test)
			lg(log, line, 0)
		else:
			line = "[%s] [go_sls] [info] Starting %d TESTS CONCURRENTLY" % (dat, len(tests_scenario))
			lg(log, line, 0)
	
		execute_scenario(tests_scenario, sls_logdir)
		scen += 1

		#Check Resources
		lg(log, " ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ", 0)
		GetFreeCPU(log, tlog)
		GetFreeMem(log, tlog)
		GetFsSpace(log, tlog)
		if t or n or net_or_nfs == 1:
			if CheckNw(log, tlog, ltp_vars) == 1:
				network_fail = 1
				if b or i or s:
					lg(log, 'Network check failed, so will pick only BASE & IO tests...')
				else:
					lg(log, 'Network check failed, exiting...')
					break
			else:
				network_fail = 0
		time.sleep(2)

	CURRENT_TIME = datetime.datetime.now()
	if CURRENT_TIME > END_TIME:
		line = "LTP Tests executed for %d hours and now its ending" % TEST_HOURS
		lg(log, line, 0)
		line = "Current Time: %s , End Time: %s" % (CURRENT_TIME, END_TIME)
		lg(log, line, 0)

		line = "Waiting for Last scenario to complete" 
		lg(log, line, 0)
		for chpid in test_pids:
			chpid.wait()
		
		break
	else:
		line = "Enough resources are available, going for next iteration"
		lg(log, line, 0)


#Update STATUS in REPORT.json
lock_file = open('%s/ltp.lock' % sls_logdir, "w")
while True:
	line = "Trying to update STATUS to COMPLETE in REPORT.json"
	lg(log, line, 0)
	try:
		fcntl.lockf(lock_file.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
	except IOError:
		time.sleep(GetRandom(10))
	else:
		break

with open(MASTER_FILE, 'r') as g:
	REPORT = json.load(g)
g.close()
if network_fail == 0:
	REPORT['RESULTS']['STATUS'] = 'Completed'
	lg(log, "Completed full suite, Thanks for using SLS Tool", 0)
else:
	REPORT['RESULTS']['STATUS'] = 'ABORTED: RHOST_DOWN'
REPORT['RESULTS']['RUNTIME'] = str(CURRENT_TIME - START_TIME)
with open(MASTER_FILE, 'w') as g:
	json.dump(REPORT, g)
g.close()

fcntl.flock(lock_file, fcntl.LOCK_UN)

line = "Updated STATUS to COMPLETE in REPORT.json"
lg(log, line, 0)
os.killpg(0, signal.SIGINT)
cleanup(log, tlog)
process.terminate() 
