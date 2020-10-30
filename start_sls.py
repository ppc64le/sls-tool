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
#  PURPOSE: Starts the LTP tests via SLS.
#           1. Parses arguments and validates them.
#           2. Reads test inputs from ./sls_config.
#           3. Validates IO_DISKS if IO tests need to executed.
#           4. Validates MUST_TESTS and EXCLUDE_TESTS.
#           5. Disabled IPv6.
#           6. Checks if kdump/fadump enabled on ppc64/ppc64le platorm.
#           7. Export LHOST RHOST values if Network and NFS needs to be executed.
#           8. Starts LTP tests in background via : ./go_sls.py
#
#  SETUP:   1. Create or Edit ./sls_config file with test inputs
#           2. Execute ./install_sls.py
#           3. Execute ./start_sls.py <options>
#

import os
import sys
import argparse
from common_sls import *

def usage():
	print("\n--------------------------------------------------------------")
	print("Usage: ./start_sls.py  -b -i -n -t -s \"Test Suites\" -r <Scenario File>")
	print(" -b --> Runs Base Tests")
	print(" -i --> Runs IO Tests")
	print(" -n --> Runs NFS Tests")
	print(" -t --> Runs Network Tests")
	print(" -s --> Run with Test suites. ex:\"syscalls,commands,fs\"")
	print(" -r --> Run with previous Scenario File")
	print("----------------------------------------------------------------\n")
	exit(1)

#Read LTP variables from ./sls_config file
if not os.path.exists('./sls_config'):
	print('./sls_config file present')
	exit(1)

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

#Create Log directory
RunCommand('mkdir -p %s' % logdir, None, 0, 0)
slog = '%s/start_sls.log' % logdir

#Parse Arguments
lg(slog, 'Parsing Arguments')
parser = argparse.ArgumentParser(description='Start SLS')

parser.add_argument('-b', action="store_true", dest="b", help='BASE Tests')
parser.add_argument('-i', action="store_true", dest="i", help='IO Tests')
parser.add_argument('-t', action="store_true", dest="t", help='Network Tests')
parser.add_argument('-n', action="store_true", dest="n", help='NFS Tests')
parser.add_argument('-s', action="store", dest="s", nargs="+", help='Test Suites')
parser.add_argument('-r', action="store", dest="r", nargs="+", help='Run with Sceanrio file')
	
args = parser.parse_args()

t = args.t
i = args.i
b = args.b
n = args.n
r = args.r
s = args.s

#Do not allow to run w/o focus area flag
if not ( t or b or i or n or s or r):
	usage()

#Check if SLS is already Running
command = "ps -eaf|grep go_sls|grep -v grep |wc -l"
if int(RunCommand(command,slog,2,0)) > 0:
	print("SLS is already running, if you wish to stop SLS please use: ./stop_sls.py")
	exit(1)

#Remove old log files in SLS_DIR
RunCommand('rm -f %s/*' % logdir, None, 0, 0)

#Check if ltp is installed
ret = RunCommand('/opt/ltp/runltp --help > /dev/null 2>&1', slog, 0, 0)
if ret != 0:
	lg(slog, 'LTP is not installed, please execute ./install_sls.py')
	exit(1)

#Remove Log file
lg(slog,'Remove Old log:\n-------------------------', 0)
RunCommand('rm -f ' + slog, slog)
lg(slog,'\n', 0)

#Check if LTP is installed
ret = RunCommand('/opt/ltp/runltp --help > /dev/null 2>&1', slog, 0)
if ret == 1:
	lg(slog, "LTP is not installed. Execute  : ./install_sls.py")
	exit(1)


#If both scenario file and focus_area flags are given, fail
if b or i or n or t or s:
	if r:
		lg(slog, "Cannot execute a Scenario file with any Focus Area mentioned")
		usage()

#If both Suites and focus_area flags are given, fail
if b or i or n or t or r:
	if s:
		lg(slog, "Cannot execute Test Suites with any Focus Area mentioned")
		usage()

#Unmount IO filesystems if any
lg(slog, 'Trying to umount sls related filesystems, if any...')
command = "mount |grep -e '/tmp/ltp-' -e '/tmp/ltp_'|awk '{print $3}'|tr '\n' '^'"
mntpoints = RunCommand(command, slog, 2, 0).strip().split('^')
mntpoints = [x for x in mntpoints if x]
for mp in mntpoints:
	lg(slog, 'Unmounting : %s' % mp)
	command = 'umount %s' % mp
	if int(RunCommand(command, slog, 0, 0)) != 0:
		command = 'umount -f %s' % mp
		if int(RunCommand(command, slog, 0, 0)) != 0:
			command = 'umount -l %s' % mp
			if int(RunCommand(command, slog, 0, 0)) != 0:
				lg(slog,'Failed to umount : %s, please umount manually' % mp)
				exit(1)

#Check IO_DISKS if IO tests need to executed
if i or s:
	io_tests = 0
	if s:
		suites = s[0].split(',')
		suites = [x for x in suites if x]
		tests_list = GetVars('./tc_group')
		IO_TESTS = tests_list['IO_LIST'].strip().split(' ')
		IO_TESTS = [x for x in IO_TESTS if x]
		for suite in suites:
			suite = suite.strip()
			if suite in IO_TESTS:
				io_tests = 1
				break
	if i or io_tests == 1:
		if 'IO_DISKS' in ltp_vars and ltp_vars['IO_DISKS'] != '':
			lg(slog, '\nPreparing Disks for IO tests:\n------------------------------')
			FSTYPES = ''
			if 'IO_FS' in ltp_vars and ltp_vars['IO_FS']:
				FSTYPES = ltp_vars['IO_FS'].strip()
			IODISKS = ltp_vars['IO_DISKS'].strip()
			fs_ret = CreateFS(IODISKS, FSTYPES, slog)
			if fs_ret == 1:
				exit(1)
			elif fs_ret == 2:
				lg(slog, '/tmp will be used by IO tests')
			else:
				lg(slog, 'IO disks will be used for IO tests')	
			lg(slog, '------------------------------\n')


		PMEMDISKS = ltp_vars['PMEM']
		if PMEMDISKS == 'Y' or PMEMDISKS == 'yes' or PMEMDISKS == 1 or PMEMDISKS == 'y':
			lg(slog, '\nPreparing pmem devices for IO tests:\n------------------------------')
			fs_ret = CreatePMEMFS(slog)
			if fs_ret == 1:
				exit(1)
			else:
				lg(slog, 'IO pmem disks will be used for IO tests')
			lg(slog, '------------------------------\n')


#Check MUST TESTS and EXCLUDE TESTS
for TST in ['MUST_TEST', 'EXCLUDE_TEST']:
	if TST in ltp_vars and ltp_vars[TST] != '':
		mtests = ltp_vars[TST].split(',')
		mtests = [x for x in mtests if x]
		for mt in mtests:
			mt = mt.strip()
			if mt == "":
				continue
			if int(RunCommand("ls /opt/ltp/testcases/bin|grep -w %s|wc -l" % mt, slog, 2, 0)) == 0:
				lg(slog, '%s: %s not found under /opt/ltp/testcases/bin' % (TST,mt))
				exit(1)
			if int(RunCommand("grep -w %s /opt/ltp/runtest/*|wc -l" % mt, slog, 2, 0)) == 0:
				lg(slog, 'test suite for %s: %s not found under /opt/ltp/runtest/' % (TST,mt))
				exit(1)
	if TST == 'EXCLUDE_TEST' and 'MUST_TEST' in ltp_vars and ltp_vars['MUST_TEST'] != '' and 'EXCLUDE_TEST' in ltp_vars:
		mtests = ltp_vars['MUST_TEST'].split(',')
		mtests = [x for x in mtests if x]
		etests = ltp_vars['EXCLUDE_TEST'].split(',')
		etests = [x for x in etests if x]
		for et in etests:
			if et in mtests:
				lg(slog, '%s: is mentioned both in MUST_TEST and EXCLUDE_TEST' % et)
				exit(1)		

#Export variables
lg(slog, 'Exporting LTP Variables')
lg(slog, 'Creating Log directories')
ltp_vars = ExportVars(ltp_vars, slog)

#Check if Network variables are declared if network test has to be executed
if t or n:
	scen_file = os.environ['TC_OUTPUT'] + '/SCENARIO_LIST'
	lg(slog, 'Checking LHOST and RHOST setting for Network Tests')
	if CheckNetwork(ltp_vars, slog, scen_file) == 1:
		exit(1)
if s:
	net_or_nfs = 0
	suites = s[0].split(',')
	suites = [x for x in suites if x]
	tests_list = GetVars('./tc_group')
	NW1_TESTS = tests_list['NW1_LIST'].strip().split(' ')
	NW1_TESTS = [x for x in NW1_TESTS if x]
	NW2_TESTS = tests_list['NW2_LIST'].strip().split(' ')
	NW2_TESTS = [x for x in NW2_TESTS if x]
	NFS_TESTS = tests_list['NFS_LIST'].strip().split(' ')
	NFS_TESTS = [x for x in NFS_TESTS if x]
	for suite in suites:
		suite = suite.strip()
		if suite in NW1_TESTS or suite in NW2_TESTS or suite in NFS_TESTS:
			net_or_nfs = 1
			break
	if net_or_nfs == 1:
		scen_file = os.environ['TC_OUTPUT'] + '/SCENARIO_LIST'
		lg(slog, 'Checking LHOST and RHOST setting for Network Tests')
		if CheckNetwork(ltp_vars, slog, scen_file) == 1:
			exit(1)

#Disable IPv6
command = "sysctl net.ipv6.conf.all.disable_ipv6=1"
RunCommand(command,slog,2)

#check if kdump or fadump is enabled, if arch is ppc64 or pp64le
arch = RunCommand("uname -i",slog,2,0)
arch = arch.strip()
if arch == 'ppc64' or arch == 'ppc64le':
	if RunCommand("systemctl is-active kdump", slog, 2, 0).strip() != 'active' \
	or RunCommand("grep -i 'fadump=on' /etc/default/grub |wc -l", slog, 2, 0) == 0:
		lg(slog, "kdump/fadump not configured")
		exit(1)

#Load modules and start OS services
lg(slog,'Loading modules')
if os.environ['os_version'] == 'rhel' or os.environ['os_version'] == 'fedora':
	mods = "xfrm dccp tunnel sctp"
else:
	mods = ''
if 'MODULES' in ltp_vars and ltp_vars['MODULES'] != '':
	modules = ltp_vars['MODULES'].split(' ')
	modules = [x for x in modules if x]
	for m in modules:
		lg(slog, 'Loading : ' + m)
		LoadModule(m, slog)
modules = mods.split(' ')
modules = [x for x in modules if x]
for m in modules:
	lg(slog, 'Loading : ' + m)
	LoadModule(m, slog)

lg(slog,'Starting Required OS services')
if StartService(slog) != 0:
	lg(slog, "Failed to start some service, please refer to : %s" % slog)

#If Scenario file given as input
if r:
	#Validate Scenario File
	if len(r) > 1:
		lg(slog, 'Please provide only 1 Scenario file as argument')
		exit(1)
	rfile = r[0]
	if not os.path.exists(rfile):
		lg(slog, "Scenario File: '%s' not found" % rfile)
		exit(1)
	if ParseScenFile(slog, rfile) != 0:
		exit(1)

#If Scenario file given as input
if s:
	#validate test suites names
	if len(s) > 1:
		lg(slog, 'Please provide only one argument : test suites names comma separated')
		exit(1)
	suites = s[0].split(',')
	suites = [x for x in suites if x]
	for suite in suites:
		command = "ls /opt/ltp/runtest/|grep -w '^%s$'|wc -l" % suite
		if int(RunCommand(command,slog, 2, 0)) == 0:
			lg(slog, 'Test Suite: %s not found under /opt/ltp/runtest' % suite)
			exit(1)

lg(slog, '--------------------------------------------------')
lg(slog, 'Started LTP with ./start_sls.py ' + " ".join(sys.argv[1:]))
lg(slog, '--------------------------------------------------')

command = "cp -f ./sls_config %s/SLS_CONFIG" % os.environ['TC_OUTPUT']
RunCommand(command, slog, 1, 0)

#Create HTML direcotry to capture LTP html output files
command = 'mkdir -p %s/LTP_HTML_LOG' % os.environ['TC_OUTPUT']
RunCommand(command, slog, 1, 0)

html_file = os.environ['TC_OUTPUT'] + '/START.LTP_log'
lg(html_file, 'Started LTP with ./start_sls.py ' + " ".join(sys.argv[1:]), 0)
reportstr = 'Please monitor HTML test logs here : '
if os.environ['HOSTNAME'] == ltp_vars['HTTP_SERVER']:
	lg(slog, reportstr + ltp_vars['HTTP_SERVER'] +":"+ os.environ['TC_OUTPUT'])
else:
	lg(slog, reportstr + ltp_vars['HTTP_SERVER'] + '/' + ltp_vars['HTTP_SERVER'] + '/' + os.environ['TC_OUTPUT'])

command = "echo %s > %s/latest_log" % (os.environ['TC_OUTPUT'], logdir)
RunCommand(command, slog, 2, 0)

command = "./go_sls.py " +  " ".join(sys.argv[1:]) + " > %s/go_sls.err 2>&1 &" % logdir
RunCommand(command, slog, 2, 0)
