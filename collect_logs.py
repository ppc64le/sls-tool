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
#  PURPOSE: Collects SLS logs required for debug pupose.
#           1. Copies SLS Log files to SLS_DIR.
#           2. Creates tar file
#
#  SETUP:   1. Install SLS: ./install_sls.py
#           2. Execute SLS: ./start_sls.py <option>
#           3. In case of any SLS issue/failure : ./collect_logs.py
#           4. Give the tar file to SLS Tool developers
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

htmlfile = '%s/latest_log' % logdir
htmldir = ''
if os.path.exists(htmlfile):
	f = open(htmlfile, "r")	
	htmldir = f.read().strip()

if os.path.exists(htmldir):
	command = "ls %s|grep -v html|tr '\n' '^'" % htmldir
	outputfiles = RunCommand(command, None, 2, 0).split('^')
	outputfiles = [x for x in outputfiles if x]
	for f in outputfiles:
		if f == 'LTP_HTML_LOG':
			continue
		filepath = "%s/%s" % (htmldir,f)
		if os.path.exists(filepath):
			command = 'cp -f %s/%s %s' % (htmldir,f,logdir)
			RunCommand(command, None, 1, 0)

command = "tar -cf sls.tar %s" % (logdir)
RunCommand(command, None, 1, 0)

print("Logs captured : %s.tar" % logdir)
