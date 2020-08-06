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
#  PURPOSE: 1. Reads test inputs from sls_config file on current directory.
#           2. Installs LTP if it is not already installed.
#           3. Drop unsupported LTP Tests.
#           4. Installs packages required for LTP tests execution.
#           5. Loads modules required for LTP tests execution.
#           6. Starts service required for LTP tests execution.
#           7. Create ~/.bashrc with required exports from bashrc.sls file.
#
#  SETUP:   1. Create or Edit ./sls_config with required test inputs.
#           2. ./install_sls.py

import os
import sys

from common_sls import *

#reload(sys)
#sys.setdefaultencoding('utf-8')

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
RunCommand('mkdir -p ' + logdir, None, 0, 0)

ilog = logdir + '/install_ltp.log'

#Check if SLS is already Running
command = "ps -eaf|grep go_sls|grep -v grep |wc -l"
if int(RunCommand(command,ilog,2,0)) > 0:
	print("SLS is already running, if u wish to stop SLS please use: ./stop_sls.py")
	exit(1)

#Remove Log file
lg(ilog,'Remove Old log:\n-------------------------', 0)
RunCommand('rm -f ' + ilog, ilog)
RunCommand('rm -f %s/*' % logdir, None, 0, 0)

pack = "automake sysstat make gcc"
packages = pack.split(' ')
packages = [x for x in packages if x]

ret = RunCommand('/opt/ltp/runltp --help > /dev/null 2>&1', ilog, 0, 0)
if ret != 0:
	#Clone or copy ltp source code
	lg(ilog,'GET LTP:\n-------------------------')
	for p in packages:
		lg(ilog, 'Installing : ' + p)
		InstallPackage(p, ilog, 0) 
	
	ret = RunCommand('ping -c 2 github.com > /dev/null 2>&1', ilog, 0, 0)
	if ret != 0:
		lg(ilog, 'ping github.com : FAIL, Please install LTP manually to proceed')
		exit(1)
	else:
		lg(ilog,'ping github.com : PASS')
		InstallPackage('git', ilog)
		lg(ilog,'Cloning latest LTP from Github')
		RunCommand('rm -rf %s/sls_ltp' % logdir, ilog)
		RunCommand('git clone https://github.com/linux-test-project/ltp.git %s/sls_ltp' % logdir, ilog)
		lg(ilog, 'LTP source code is cloned to %s/sls_ltp directory' % logdir)

	#Compile LTP tests
	lg(ilog,'\nCompile & Install LTP:\n-------------------------')
	lg(ilog,'Running : make autotools')
	RunCommand('cd %s/sls_ltp ; make autotools' % logdir, ilog)
	lg(ilog,'Running : ./configure')
	RunCommand('cd %s/sls_ltp ; ./configure' % logdir, ilog)
	lg(ilog,'Running : make all')
	RunCommand('cd %s/sls_ltp ; make all' % logdir, ilog)
	lg(ilog,'Running : make install')
	RunCommand('cd %s/sls_ltp ; make install' % logdir, ilog)
	RunCommand('rm -rf %s/sls_ltp/*' % logdir, ilog)	
else:
	lg(ilog,'LTP is already installed')

ltp_vars = ExportVars(ltp_vars, ilog)
ChangeLTP(ilog)
DropIPV6(ilog)
DropNfsv3UDP(ilog)
SetMinFree(ilog)
CopyDataFiles(ilog)

#Install required packages
os.environ['os_version'] = GetOS('ID')
os.environ['VERSION'] = GetOS('VERSION')
lg(ilog,'\nInstalling required packages:\n-------------------------')
if 'PACKAGE_LIST' in ltp_vars and ltp_vars['PACKAGE_LIST'].strip() != '':
	packages = ltp_vars['PACKAGE_LIST'].split(',')
	packages = [x for x in packages if x]
	for p in packages:
		lg(ilog, 'Installing : ' + p)
		InstallPackage(p, ilog, 0)

if os.environ['os_version'] == 'rhel' or os.environ['os_version'] == 'fedora':
	if re.search('7', os.environ['VERSION'], re.M):
		pack = "tpm* opencryptoki dnsmasq xinetd ftp vsftpd telnet telnet-server httpd traceroute dhcp* libaio-devel* nfs-utils numactl* libaio* bzip2"
	else:
		pack = "tpm* opencryptoki dnsmasq xinetd ftp vsftpd telnet telnet-server httpd traceroute dhcp* kernel-modules-extra libaio-devel* libtirpc-devel nfs-utils psmisc numactl* libaio* bzip2"
	mods = "xfrm dccp tunnel sctp"
elif os.environ['os_version'] == 'sles':
	if re.search('15', os.environ['VERSION'], re.M):
		pack = "lftp telnet telnet-server systemd openssh httpd iftop vsftpd syslog nfs-kernel-server nfs-client iputils libtirpc-devel psmisc numactl* libaio* bzip2"
	else:
		pack = "lftp telnet rlogin rcp httpd iftop vsftpd syslog psmisc numactl* libaio* bzip2"
	
	mods = ''

if 'MODULES' in ltp_vars and ltp_vars['MODULES'] != '':
	modules = ltp_vars['MODULES'].split(' ')
	modules = [x for x in modules if x]
	for m in modules:
		lg(ilog, 'Loading : ' + m)
		LoadModule(m, ilog)

packages = pack.split(' ')
packages = [x for x in packages if x]
for p in packages:
	lg(ilog, 'Installing : ' + p)
	InstallPackage(p, ilog, 0) 

modules = mods.split(' ')
modules = [x for x in modules if x]
for m in modules:
	lg(ilog, 'Loading : ' + m)
	LoadModule(m, ilog)

lg(ilog,'Starting Required OS services')
if StartService(ilog) != 0:
	lg(ilog, "Failed to start some service, please refer to : %s" % ilog)
	#exit(1)
lg(ilog,'')

#Copy bashrc
lg(ilog, 'Updating .bashrc with LTP_PATH and other Variables')
command = "[[ -f /root/.bashrc.orig ]] || cp /root/.bashrc /root/.bashrc.orig"
RunCommand(command, ilog, 1, 0)
command = "cp -f ./bashrc.sls /root/.bashrc"
if int(RunCommand(command, ilog, 0, 0)):
	lg(ilog, 'Failed to update .bashrc')
	exit(1)

ret = RunCommand('/opt/ltp/runltp --help > /dev/null 2>&1', ilog, 0)
if ret != 0:
	lg(ilog, "FAILED to Install LTP. Refer "+ ilog)
else:
	lg(ilog, "SUCCESS: LTP Installed. Log: "+ ilog)
