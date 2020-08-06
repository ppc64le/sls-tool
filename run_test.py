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
#  PURPOSE: This is the thread script which actually calls runltp to execute LTP test
#           1. Reads the arguments passed by go_sls.py
#           2. Calls runltp to execute required LTP test
#           3. Captures the test results, updates REPORT.json and dumps html file to log directory
#
#  SETUP:   1. Create or Edit ./sls_config file with test inputs
#           2. Install SLS: ./install_sls.py
#           3. Start SLS: ./start_sls.py <options>
#           4. go_sls.py gets called by ./start_sls.py
#           5. run_test.py gets called by go_sls.py as a multithreaded function

import os
import sys
import re
import fcntl
import datetime
import time
import json
from common_sls import lg,RunCommand,GetRandom

test = str(sys.argv[1])
iter = int(sys.argv[2])
suite = str(sys.argv[3])
dat = str(sys.argv[4])
str_time = str(sys.argv[5])
logdir = str(sys.argv[6])

START_TIME = datetime.datetime.strptime(str_time, '%Y%m%d%H%M%S')
C_TIME = datetime.datetime.now()
c_time = C_TIME.strftime('%Y%m%d%H%M%S')

tlog = '%s/run_test.log' % logdir

ltp_path = os.environ['ltp_path']

command = "mkdir -p %s/results" % (ltp_path)
RunCommand(command, tlog, 2, 0)

LOG_FILE = "%s/results/%s_%s" % (ltp_path,test, c_time)

#If its a IO test then give temp dir
if re.search(suite,os.environ['IO_LIST'],re.M):
	command = "ls -d /tmp/*|grep ltp_io|tr '\n' ' '"
	io_dirs = RunCommand(command, tlog, 2, 0)
	iodirs = io_dirs.split(' ')
	if len(iodirs) == 0:
		io_dir = '/tmp'
	elif len(iodirs) == 1:
		io_dir = iodirs[0]
	else:
		ioindex = GetRandom(len(iodirs)-1,0)
		io_dir = iodirs[ioindex]
	command = "%s/runltp -I %d -f %s -s %s -g %s/LTP_HTML_LOG/%s.html -C /tmp/FAILCMDFILE -T /tmp/TCONFCMDFILE -o %s/output/%s_%s -l %s -p -d %s > /dev/null 2>&1" % (ltp_path, iter, suite, test, os.environ['TC_HTML_PATH'], test, ltp_path, test, c_time, LOG_FILE, io_dir)
else:
	command = "%s/runltp -I %d -f %s -s %s -g %s/LTP_HTML_LOG/%s.html -C /tmp/FAILCMDFILE -T /tmp/TCONFCMDFILE -o %s/output/%s_%s -l %s -p > /dev/null 2>&1" % (ltp_path, iter, suite, test, os.environ['TC_HTML_PATH'], test, ltp_path, test, c_time, LOG_FILE)

os.system(command)


#Remove test line from In progress file
in_progess_file = os.environ['TC_OUTPUT'] + '/IN-PROGRESS-TEST'
lock_file = open('%s/ltp_inprogress.lock' % logdir, "w")
while True:
	try:
		fcntl.lockf(lock_file.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
	except IOError:
		time.sleep(GetRandom(5))
	else:
		break

with open(in_progess_file, 'r') as g:
	ITESTS = g.readlines()
g.close()

inprog_tests = ''
for itst in ITESTS:
	if not re.search(':', itst,  re.M):
		continue
	t = itst.split(':')[0]
	if test == t:
		continue
	inprog_tests = "%s\n%s" % (inprog_tests,itst)

g = open(in_progess_file, "w")
g.write(inprog_tests)
g.close()

fcntl.flock(lock_file, fcntl.LOCK_UN)

#Read TOTAL_TEST TOTAL_SKIP TOTAL_FAIL from log file
command = "grep 'Total Tests' %s | cut -f 2 -d :" % LOG_FILE
TOTAL_TEST = int(RunCommand(command, tlog, 2, 0).strip())
command = "grep 'Total Skipped Tests' %s | cut -f 2 -d :" % LOG_FILE
TOTAL_SKIP = int(RunCommand(command, tlog, 2, 0).strip())
command = "grep 'Total Failures' %s | cut -f 2 -d :" % LOG_FILE
TOTAL_FAIL = int(RunCommand(command, tlog, 2, 0).strip())


#Prepare Results
RESULTS = []

#Read Test numbers from html file
HTML_FILE = "%s/LTP_HTML_LOG/%s.html" % (os.environ['TC_HTML_PATH'], test)

command = "grep 'Total Test TBROK' %s|sed -e 's/<[^<>]*>//g'|sed 's/Total Test TBROK//'" % HTML_FILE
TOTAL_BROK = RunCommand(command, tlog, 2, 0).strip()
if TOTAL_BROK == '':
	TOTAL_BROK = 0
else:
	TOTAL_BROK = int(TOTAL_BROK)

command = "grep 'Total Test TCONF' %s|sed -e 's/<[^<>]*>//g'|sed 's/Total Test TCONF//'" % HTML_FILE
TOTAL_CONF = RunCommand(command, tlog, 2, 0).strip()
if TOTAL_CONF == '':
	TOTAL_CONF = 0
else:
	TOTAL_CONF = int(TOTAL_CONF)

TOTAL_PASS = TOTAL_TEST - TOTAL_SKIP - TOTAL_FAIL - TOTAL_CONF
if TOTAL_PASS < 0:
	TOTAL_PASS = 0

if TOTAL_CONF == TOTAL_SKIP:
	TOTAL_SKIP = 0

if (TOTAL_CONF + TOTAL_SKIP + TOTAL_BROK) >= TOTAL_TEST:
	command = "echo '%s:%s' >> %s/sls_skip_conf_brok" % (test,suite,logdir)
	RunCommand(command, tlog, 2, 0)

test_results = {}
test_results['TOTAL_ITRN'] = TOTAL_TEST
test_results['TOTAL_FAIL'] = TOTAL_FAIL
test_results['TOTAL_PASS'] = TOTAL_PASS
test_results['TOTAL_BROK'] = TOTAL_BROK
test_results['TOTAL_SKIP'] = TOTAL_SKIP
test_results['TOTAL_CONF'] = TOTAL_CONF

#Read REPORT.json for this test
MASTER_FILE=os.environ['TC_HTML_PATH'] + '/REPORT.json'
lock_file = open('%s/ltp.lock' % logdir, "w")
while True:
	try:
		fcntl.lockf(lock_file.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
	except IOError:
		time.sleep(GetRandom(5))
	else:
		break

with open(MASTER_FILE, 'r') as g:
	REPORT = json.load(g)
g.close()

fcntl.flock(lock_file, fcntl.LOCK_UN)

REPORT_TESTS = REPORT['TESTS']
if test in REPORT_TESTS.keys():
	OLD_RESULT = REPORT_TESTS[test]
	NEW_RESULT = {}
	NEW_RESULT['TOTAL_ITRN'] = OLD_RESULT['TOTAL_ITRN'] + test_results['TOTAL_ITRN']
	NEW_RESULT['TOTAL_FAIL'] = OLD_RESULT['TOTAL_FAIL'] + test_results['TOTAL_FAIL']
	NEW_RESULT['TOTAL_PASS'] = OLD_RESULT['TOTAL_PASS'] + test_results['TOTAL_PASS']
	NEW_RESULT['TOTAL_BROK'] = OLD_RESULT['TOTAL_BROK'] + test_results['TOTAL_BROK']
	NEW_RESULT['TOTAL_SKIP'] = OLD_RESULT['TOTAL_SKIP'] + test_results['TOTAL_SKIP']
	NEW_RESULT['TOTAL_CONF'] = OLD_RESULT['TOTAL_CONF'] + test_results['TOTAL_CONF']
	REPORT['TESTS'][test] = NEW_RESULT	
else:
	REPORT['TESTS'][test] = test_results

TOT_ITRN=0;TOT_PASS=0;TOT_FAIL=0;TOT_SKIP=0;TOT_BROK=0;TOT_CONF=0;
T_TC=0;T_TP=0;T_FL=0;T_BR=0;T_WA=0;T_CO=0
for tst in REPORT_TESTS.keys():
	if REPORT_TESTS[tst]['TOTAL_ITRN'] != 0:
		TOT_ITRN += REPORT_TESTS[tst]['TOTAL_ITRN']
	if REPORT_TESTS[tst]['TOTAL_FAIL'] != 0:
		TOT_FAIL += REPORT_TESTS[tst]['TOTAL_FAIL']
	if REPORT_TESTS[tst]['TOTAL_PASS'] != 0:
		TOT_PASS += REPORT_TESTS[tst]['TOTAL_PASS']
	if REPORT_TESTS[tst]['TOTAL_BROK'] != 0:
		TOT_BROK += REPORT_TESTS[tst]['TOTAL_BROK']
	if REPORT_TESTS[tst]['TOTAL_SKIP'] != 0:
		TOT_SKIP += REPORT_TESTS[tst]['TOTAL_SKIP']
	if REPORT_TESTS[tst]['TOTAL_CONF'] != 0:
		TOT_CONF += REPORT_TESTS[tst]['TOTAL_CONF']
	
	if REPORT_TESTS[tst]['TOTAL_ITRN'] != 0:
		T_TC += 1
	if REPORT_TESTS[tst]['TOTAL_FAIL'] != 0:
		T_FL += 1
	elif REPORT_TESTS[tst]['TOTAL_CONF'] != 0:
		T_CO += 1
	elif REPORT_TESTS[tst]['TOTAL_BROK'] != 0:
		T_BR += 1
	elif REPORT_TESTS[tst]['TOTAL_SKIP'] != 0:
		T_WA += 1
	elif REPORT_TESTS[tst]['TOTAL_PASS'] != 0:
		T_TP += 1

if TOT_ITRN == 0:
	REPORT['RESULTS']['PASS%'] = 0
	REPORT['RESULTS']['FAIL%'] = 0
	REPORT['RESULTS']['SKIP%'] = 0
	REPORT['RESULTS']['CONF%'] = 0
	REPORT['RESULTS']['BROK%'] = 0
else:
	REPORT['RESULTS']['PASS%'] = round((100 * TOT_PASS) / TOT_ITRN)
	REPORT['RESULTS']['FAIL%'] = round((100 * TOT_FAIL) / TOT_ITRN)
	REPORT['RESULTS']['SKIP%'] = round((100 * TOT_SKIP) / TOT_ITRN)
	REPORT['RESULTS']['CONF%'] = round((100* TOT_CONF) / TOT_ITRN)
	REPORT['RESULTS']['BROK%'] = round((100* TOT_BROK) / TOT_ITRN)

#Update RUNTIME
CURRENT_TIME = datetime.datetime.now()
cur_time = CURRENT_TIME.strftime('%Y%m%d%H%M%S')
CTIME = datetime.datetime.strptime(cur_time, '%Y%m%d%H%M%S')
if CTIME >= START_TIME:
	REPORT['RESULTS']['RUNTIME'] = str(CTIME - START_TIME)
else:
	REPORT['RESULTS']['RUNTIME'] = str(START_TIME - CTIME)

REPORT['RESULTS']['OVERVIEW'] = "TEST_CASES(%d) | TOTAL_ITR(%d/%d) | TOTAL_PASS(%d/%d) | TOTAL_FAIL(%d/%d) | TOTAL_BROK(%d/%d) | TOTAL_SKIP(%d/%d) | TOTAL_CONF(%d/%d)" % (T_TC,TOT_ITRN,T_TC,TOT_PASS,T_TP,TOT_FAIL,T_FL,TOT_BROK,T_BR,TOT_SKIP,T_WA,TOT_CONF,T_CO)
lock_file = open('%s/ltp.lock' % logdir, "w")
while True:
	try:
		fcntl.lockf(lock_file.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
	except IOError:
		time.sleep(1)
	else:
		break

with open(MASTER_FILE, "w") as g:
	json.dump(REPORT, g)	
g.close()
fcntl.flock(lock_file, fcntl.LOCK_UN)
fcntl.flock(lock_file, fcntl.LOCK_UN)
fcntl.flock(lock_file, fcntl.LOCK_UN)
