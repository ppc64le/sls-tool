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
#  PURPOSE: Contains definitions of all common functions used by SLS.
#           1. GetVars : Reads input file argument and returns a dictionary of values
#           2. lg : Logs the input argument into required log file 
#           3. RunCommand : Executes shell command passed as argument
#           4. GetOS : Read /etc/os-release and returns OS release related information
#           5. InstallPackage : Installs package passed as argument
#           6. LoadModule : Loads the Module passed as argument
#           7. ExportVars : Exports the dictionary argument to shell environment
#           8. ChangeLTP : Replaces rsh related tests with ssh, drop unsupported tests
#           9. DropIPV6 : Drops IPV6 related tests
#          10. DropNfsv3UDP : Drops NFS version3 related tests
#          11. CopyDataFiles : copies the datafiles to /opt/ltp/datafiles required for Network/IO tests
#          12. StartService : Starts the services required for SLS execution
#          13. ValidIP : Verifies if the argument is a valid IP or not
#          14. CheckNetwork : Checks and exports LHOST and RHOST values required for Network/NFS tests
#          15. GetRandom : Generates a random number in given range, used to pick random tests to execute
#          16. MachineInfo : Executes commands mentioned in MACHINE_INFO_COMMANDS in sls_config file
#          17. CheckNw : Checks if RHOST is pingable if Network tests are running
#          18. GetFreeCPU : Check how much free CPU is available, based on this next set of tests will be selected
#          19. GetFreeMem : Check how much free Memory is available, based on this next set of tests will be selected
#          20. GetFsSpace : Check how much free space is available on boot disk
#          21. SetMinFree : Sets min_free_kbytes and swappiness as per SLS requirement
#          22. CreateFS : Creates Filesystem/LVM on IO disks
#          23. OOMKill : Kills SLS related processes if free memory goes below 10% of total memory
#          24. ParseScenFile : Parses scenario file if SLS is executed with -r option
#          25. GetSuiteIterations : Finds to which suite a test belongs to and decides how many iterations a test should be executed
#
#  SETUP:   1. Install SLS : ./install_sls.py 
#           2. Start SLS : ./start_sls.py <options>
#           3. Functions in common_sls.py will get called internally from above two scripts.

import os
import re
#import commands
import subprocess
import random
import time
import datetime

def GetVars(filename='sls_config'):
	ltp_variables = {}
	with open("./" + filename) as fp:
		lines = fp.readlines()
	fp.close()

	line_num = 1
	for line in lines:
		line = line.strip()
		if line == '' or line.startswith('#'):
			continue
			line_num += 1
		if len(line.split('=')) != 2:
			print ("Wrong declaration in sls_config %s, line number:%d") % (line,line_num)
			return None
		variable = line.split('=')[0]
		value = line.split('=')[1]
		if variable == "" or value == "":
			print ("Wrong declaration in sls_config %s, line number:%d") % (line,line_num)
			return None
		value = value.replace('"','').replace("'",'')
		if re.search('\$', value, re.M):
			values_str = ''
			values = value.split('$')
			for v in values:
				v = v.replace('{','').replace('}','')
				if v == '' or v == ' ':
					continue
				val_str = ltp_variables[v]
				if values_str == '':
					values_str = val_str	
				else:
					values_str = "%s%s" % (values_str,val_str)
			ltp_variables[variable] = values_str
		else:
			ltp_variables[variable] = value
		line_num += 1

	#Check for mandatory fields
	if filename == 'sls_config':	
		if 'MIN_TEST_PER_SCENARIO' not in ltp_variables:
			ltp_variables['MIN_TEST_PER_SCENARIO'] = 1
		if 'MAX_TEST_PER_SCENARIO' not in ltp_variables:
			ltp_variables['MAX_TEST_PER_SCENARIO'] = 5
		if 'TEST_HOURS' not in ltp_variables:
			ltp_variables['TEST_HOURS'] = 72
		if 'ITERATIONS' not in ltp_variables:
			ltp_variables['ITERATIONS'] = ''
		if 'MUST_TEST' not in ltp_variables:
			ltp_variables['MUST_TEST'] = ''

		CHECKLIST = ['MIN_TEST_PER_SCENARIO', 'MAX_TEST_PER_SCENARIO', 'TEST_HOURS']
		for CH in CHECKLIST:
			try:
				if int(ltp_variables[CH]) <= 0:
					print('Error in sls_config: %s should be a number' % CH)
					return None
			except Exception as e:
				print('Error in sls_config: %s should be a number' % CH)
				return None
		if int(ltp_variables['MIN_TEST_PER_SCENARIO']) > int(ltp_variables['MAX_TEST_PER_SCENARIO']):
			print('Error in sls_config: MIN_TEST_PER_SCENARIO is greater than MAX_TEST_PER_SCENARIO')
			return None
		if ltp_variables['ITERATIONS'] != '':
			try:
				if int(ltp_variables['ITERATIONS']) <= 0:
					print('Error in sls_config: ITERATIONS should be a positive integer')	
					return None
			except Exception as e:
				print('Error in sls_config: ITERATIONS should be a positive integer')
				return None
		if ltp_variables['WAIT_SCENARIO'] != 'YES' and ltp_variables['WAIT_SCENARIO'] != 'NO':
			print('Error in sls_config: WAIT_SCENARIO can either be YES or NO')
			return None	

	if not ltp_variables:
		print("No variables declared in sls_config file")
		return None
	return ltp_variables	

def lg(logfile,data,tostdout=1, timestamp=0):
	logdir = "/".join(logfile.split('/')[0:-1])
	if not os.path.exists(logdir):
		print ("%s directory does not exist") % (logdir)
		exit(1)
	if timestamp != 0:
		d = datetime.datetime.now().strftime('%Y/%m/%d,%H:%M:%S')
		data = '[' + d + '] ' + data
	if tostdout == 1:
		print(data)
	f = open(logfile, "ab")
	line = "%s\n" % data
	f.write(line.encode('utf-8'))
	f.close()


def RunCommand(command, log, needexit=1, tostdout=1):
	if re.search('go_sls.py', command, re.M):
		os.system(command)
		exit(0)
	#status, output = commands.getstatusoutput(command)
	proc = subprocess.Popen(command, shell=True, stdout = subprocess.PIPE,stderr = subprocess.STDOUT,)
	output, stderr = proc.communicate()
	output = output.decode("utf-8") 
	status = proc.returncode
	if log is not None:
		lg(log,"command: " + command, 0)
		if output != '':
			lg(log,output,0)
	if status != 0:
		if log is None:
			print("Command : " + command + " Failed")
		else:
			lg(log, "Log:" + log, tostdout)
			lg(log, "Command : "+ command + " Failed", tostdout)
		if needexit == 1:
			if tostdout == 1:
				print( "Log:" + log)
			exit(1)
	if needexit == 2:
		return output
	elif needexit == 0:
		return status
	

def GetOS(oskey='ID'):
	with open("/etc/os-release") as fp:
		lines = fp.readlines()
	fp.close()
	OS = {}
	for l in lines:
		if re.search('=',l,re.M):
			key = l.split('=')[0]
			value = l.split('=')[1].strip().replace('"','')
			OS[key] = value	

	if OS[oskey]:
		return OS[oskey]
	else:
		return None
	return lines


def InstallPackage(package, log, check=1):
	if check == 1:
		ret = RunCommand("which " + package + "> /dev/null 2>&1", log, 0, 0)
	else:
		ret = 1
	if ret != 0:
		os = GetOS()
		if os == 'rhel' or os == 'fedora':
			RunCommand("yum install -y " + package, log)
		elif os == 'sles':
			RunCommand("zypper install -y " + package, log)
		else:
			RunCommand("apt-get update; apt-get install " + package, log)


def LoadModule(module, log):
	command = "find /lib/modules/$(uname -r) -type f -name *%s*|tr '\n' '^'" % module
	mods = str(RunCommand(command, log, 2, 0))
	modules = mods.split('^')
	for m in modules:
		if m == '' or m == ' ':	
			continue
		RunCommand("insmod " + m, log, 2, 0)	


def ExportVars(ltp_vars, log):
	if 'SLS_DIR' not in ltp_vars:
		ltp_vars['SLS_DIR'] = '/var/log/sls/'
	elif ltp_vars['SLS_DIR'].strip() == '':
		ltp_vars['SLS_DIR'] = '/var/log/sls/'
	logdir = ltp_vars['SLS_DIR']
	os.environ['HOSTNAME'] = RunCommand("hostname -s", log, 2).strip()
	os.environ['os_version'] = GetOS('ID').strip()
	os.environ['os_version'] = os.environ['os_version'].replace('\n\r', '').strip()
	os.environ['TMP'] = RunCommand("date +'%Y%m%d.%H%M%S.%3N'", log, 2).strip()
	os.environ['TMPFILE'] = RunCommand("echo %s/$$" % logdir, log, 2).strip()

	if ('TC_HTML_PATH' in ltp_vars) and ltp_vars['TC_HTML_PATH'] != '':
		html_path = ltp_vars['TC_HTML_PATH']
	else:
		html_path = "/LOGS/SLS/"
		ltp_vars['TC_HTML_PATH'] = html_path

	os.environ['ltp_log_dir'] = ltp_vars['TC_HTML_PATH'] + '/' + os.environ['HOSTNAME'] + "/ltpresult" + os.environ['TMP']
	os.environ['ltp_path'] = "/opt/ltp"
	os.environ['ltp_bin'] = "/opt/ltp/testcases/bin"
	os.environ['KERNEL_LEVEL'] = RunCommand("uname -r | sed s/-default//", log, 2).strip()
	os.environ['BUILD_LEVEL'] = os.environ['KERNEL_LEVEL']
	OS_RELEASE = GetOS('NAME').strip()
	os.environ['OS_RELEASE'] = "".join(OS_RELEASE.split(' ')[0:2]).strip()
	os.environ['OS_RELEASE'] = os.environ['OS_RELEASE'].strip()
	os.environ['TC_HTML_PATH'] = html_path + '/' + os.environ['OS_RELEASE'] + "/" + \
	os.environ['BUILD_LEVEL'] + "/" + os.environ['HOSTNAME'] + '/' + os.environ['TMP']
	os.environ['TC_OUTPUT'] = os.environ['TC_HTML_PATH'] 
	os.environ['TC_OUTPUT'] = os.environ['TC_OUTPUT'].replace('\r\n', '')

	if 'HTTP_SERVER' in ltp_vars and ltp_vars['HTTP_SERVER'] != '':
		os.environ['HTTP_SERVER'] = ltp_vars['HTTP_SERVER']
	else:
		ltp_vars['HTTP_SERVER'] = os.environ['HOSTNAME']
		os.environ['HTTP_SERVER'] = os.environ['HOSTNAME']

	RunCommand("mkdir -p " + os.environ['TC_OUTPUT'], log)
	RunCommand("chmod -R 0777 " + os.environ['ltp_path'] + '/*', log)
	RunCommand("chmod -R 0777 /dev/* > /dev/null 2>&1", log, 0, 0)	

	os.environ['TST_USE_SSH'] = 'ssh'
	os.environ['LTP_TIMEOUT_MUL'] = '40'
	os.environ['TST_DISABLE_APPARMOR'] = '1'
	os.environ['LTP_RSH'] = 'ssh'

	if 'EXPORT_VARIABLES' in ltp_vars and ltp_vars['EXPORT_VARIABLES'] != '':
		exp_variables = ltp_vars['EXPORT_VARIABLES'].split(',')
		exp_variables = [x for x in exp_variables if x]
		for evar in exp_variables:
			if len(evar.split(':')) != 2:
				lg(log, 'Invalid entry : %s in EXPORT_VARIABLES' % evar)
				exit(1)
			else:
				key = evar.split(':')[0].strip()
				value = evar.split(':')[1].strip()
				os.environ[key] = value
				lg(log, 'Exported %s' % evar)
		
	os.environ['LTPROOT'] = '/opt/ltp'
	#os.environ['PS1'] = '\[\e[31m\]\u@\h:\w\[\e[0m\] '
	os.environ['NS_DURATION'] = '127'
	os.environ['CONNECTION_TOTAL'] = '27'
	os.environ['DOWNLOAD_REGFILESIZE'] = '2147483627'
	os.environ['UPLOAD_REGFILESIZE'] = '214748364727'
	if 'PATH' in ltp_vars and ltp_vars['PATH'] != '':
		os.environ['PATH'] = os.environ['PATH'] + ':' + ltp_vars['PATH']
		ltp_vars['PATH'] = os.environ['PATH']
		
	return ltp_vars


def ChangeLTP(log):
	ltpbin = os.environ['ltp_bin']
	command = "ls %s|grep -w rcp01.sh|grep -v grep|grep -v new|wc -l" % ltpbin
	if int(RunCommand(command, log, 2, 0)) != 0:
		lg(log, "Fixing LTP Code to enable rcp01")
		command = "sed 's/rsh/ssh/g' %s/rcp01.sh > %s/rcp01.sh.new" % (ltpbin, ltpbin)
		RunCommand(command, log, 1)
		command = "mv -f %s/rcp01.sh.new %s/rcp01.sh" % (ltpbin, ltpbin)
		RunCommand(command, log, 1)

	command = "ls %s|grep -w ftp01.sh|grep -v grep|grep -v new|wc -l" % ltpbin
	if int(RunCommand(command, log, 2, 0)) != 0:
		lg(log, "Fixing LTP Code to ftp01")
		command = "sed 's/rsh/ssh/g' %s/ftp01.sh > %s/ftp01.sh.new" % (ltpbin, ltpbin)
		RunCommand(command, log, 1)
		command = "mv -f %s/ftp01.sh.new %s/ftp01.sh" % (ltpbin, ltpbin)
		RunCommand(command, log, 1)

	command = "ls %s|grep -w check_envval|grep -v grep|grep -v new|wc -l" % ltpbin
	if int(RunCommand(command, log, 2, 0)) != 0:
		lg(log, "Fixing LTP code to enable mcast4-queryfld related tests")
		command = "sed 's/exists cut locale rsh/exists cut locale ssh/g' %s/check_envval > %s/check_envval.new" % (ltpbin, ltpbin)
		RunCommand(command, log, 1)
		command = "mv -f %s/check_envval.new %s/check_envval" % (ltpbin, ltpbin)
		RunCommand(command, log, 1)

	lg(log, "Change IO tests to use $TMPDIR")
	command = "sed -i 's/\/test\//$TMPDIR\//g' /opt/ltp/runtest/lvm.part1"
	RunCommand(command, log, 0, 0)
	command = "sed -i 's/\/test\//$TMPDIR\//g' /opt/ltp/runtest/lvm.part2"
	RunCommand(command, log, 0, 0)
	command = "sed -i 's/\/test\//$TMPDIR\//g' /opt/ltp/runtest/scsi_debug.part1"
	RunCommand(command, log, 0, 0)
	command = "sed -i 's/\/tmp\//$TMPDIR\//g' /opt/ltp/runtest/fcntl-locktests"
	RunCommand(command, log, 0, 0)
	
	lg(log, "Dropping unsupported tests")
	arch = RunCommand("uname -i",log,2,0).strip()
	if arch == 'ppc64' or arch == 'ppc64le':
		command = "sed -i '/_16/d' /opt/ltp/runtest/syscalls"
		RunCommand(command, log, 0, 0)
	ltppath = os.environ['ltp_path'] + '/runtest'
	command = "uname -r|awk -F'.' '{print $1\".\"$2}'"
	uname_val = RunCommand(command, log, 2, 0)
	uname1 = int(uname_val.strip().split('.')[0])
	uname2 = int(uname_val.strip().split('.')[1])
	command = "grep TST_MIN_KVER /opt/ltp/testcases/bin/* 2>/dev/null|grep =|sed 's/TST_MIN_KVER=//g'|sed 's/\"//g'|tr '\n' '^'"
	tests = RunCommand(command, log, 2, 0)
	testlist = tests.split('^')
	for test in testlist:
		if test == '':
			continue
		tst = test.split(':')[0]
		testname = test.split(':')[0].replace('/opt/ltp/testcases/bin/','')
		test_version1 = int(test.split(':')[1].split('.')[0])
		test_version2 = int(test.split(':')[1].split('.')[1])
		if test_version1 >= uname1:
			if test_version1 == uname1 and test_version2 < uname2:
				continue
			lg(log, 'Removing test:%s,  supported on: %d.%d kernel, current kernel: %d.%d' % (testname,test_version1,test_version2,uname1,uname2))
			command = "grep -i '%s'  %s/* | cut -f 1 -d :|tr '\n' '^'" % (testname, ltppath)
			output = RunCommand(command, log, 2, 0)
			tsts = output.split('^')
			for te in tsts:
				if te == '' or te == ' ':
					continue
				command = "sed \"/%s/d\" %s > %s.new" % (testname,te,te)
				RunCommand(command, log, 1)
				command = "mv -f %s.new %s" % (te,te)
				RunCommand(command, log, 1)


def DropIPV6(log):
	lg(log, "Removing IPV6 tests")
	ltppath = os.environ['ltp_path'] + '/runtest'
	ipv6_pattern = ['\-6', 'v6', 'ipv6', 'route6', 'mcast6']
	for i in ipv6_pattern:
		command = "grep -i '%s'  %s/* | cut -f 1 -d :|tr '\n' '^'" % (i, ltppath)
		output = RunCommand(command, log, 2, 0)
		tests = output.split('^')
		for t in tests:
			if t == '' or t == ' ':
				continue
			command = "sed \"/%s/d\" %s > %s.new" % (i,t,t)
			RunCommand(command, log, 1)
			command = "mv -f %s.new %s" % (t,t)
			RunCommand(command, log, 1)


def DropNfsv3UDP(log):
	lg(log, "Removing unsupported nfsv3_udp tests")
	ltppath = os.environ['ltp_path'] + '/runtest'
	command = "grep '\-v 3 \-t udp' %s/net.nfs|wc -l" % ltppath
	num_entries = int(RunCommand(command, log, 2, 0))
	i = 0
	while i < num_entries:
		command = "sed -i '/\-v 3 \-t udp/d' %s/net.nfs" % ltppath
		RunCommand(command, log, 1)
		i+=1
	
	command = "sed -i '/nfs01_06/d' %s/net.nfs" % ltppath
	RunCommand(command, log, 1)
	command = "sed -i '/nfs02_06/d' %s/net.nfs" % ltppath
	RunCommand(command, log, 1)
	command = "echo \"nfs01_06  nfs06 -v '3,4,4,4' -t 'tcp,tcp,tcp,tcp' \" >> %s/net.nfs" % ltppath
	RunCommand(command, log, 1)
	command = "echo \"nfs02_06 nfs06 -v '4,4.1,4.2,4.2,4.2' -t 'tcp,tcp,tcp,tcp,tcp' \" >> %s/net.nfs" % ltppath
	RunCommand(command, log, 1)


def CopyDataFiles(log):
	if not os.path.exists('/opt/ltp/datafiles'):
		if not os.path.exists('/opt/ltp/testcases/bin/datafiles'):
			lg('Datafiles directory is not available /opt/ltp/testcases/bin/datafiles')
			return 1
		lg(log, "Copying Datafiles to /opt/ltp/datafiles", 1)
		command = "cp -Rf /opt/ltp/testcases/bin/datafiles /opt/ltp/"
		RunCommand(command, log, 1)
	

def StartService(log):
	os = GetOS()
	if os == 'rhel' or os == 'fedora':
		lg(log, 'Stoping xinetd service', 0)
		RunCommand("systemctl stop xinetd", log, 1)
		lg(log, 'Disable Firewall', 0)
		RunCommand("service firewalld stop", log, 1)
		lg(log, 'Starting NFS Service', 0)
		RunCommand("systemctl start nfs-server", log, 1)
		RunCommand("systemctl enable nfs-server", log, 1)
		lg(log, 'Starting httpd Service', 0)
		RunCommand("systemctl start httpd", log, 1)
		lg(log, 'Enabling Telnet Service', 0)
		RunCommand("chkconfig telnet on", log, 1)
		RunCommand("systemctl start telnet.socket", log, 1)
		RunCommand("systemctl enable telnet.socket", log, 1)
		lg(log, 'Updating vsftpd configuration file to allow root users for ftp tests', 0)
		RunCommand("sed '/root/d' /etc/vsftpd/user_list > /etc/vsftpd/user_list.bk", log, 1)
		RunCommand("mv /etc/vsftpd/user_list.bk /etc/vsftpd/user_list", log, 1, 0)
		RunCommand("sed '/root/d' /etc/vsftpd/ftpusers > /etc/vsftpd/ftpusers.bk", log, 1)
		RunCommand("mv /etc/vsftpd/ftpusers.bk /etc/vsftpd/ftpusers", log, 1)
		RunCommand("[[ -f /etc/vsftpd/vsftpd.conf ]] && sed -i 's/listen=NO/listen=YES/' /etc/vsftpd/vsftpd.conf", log, 1)
		RunCommand("[[ -f /etc/vsftpd/vsftpd.conf ]] && sed -i 's/listen_ipv6=YES/listen_ipv6=NO/' /etc/vsftpd/vsftpd.conf", log, 1)
		RunCommand("systemctl restart vsftpd", log, 1)
		RunCommand("systemctl start xinetd", log, 1)
	elif os == 'sles':
		lg(log, 'Enabling Telnet Service', 0)
		RunCommand("systemctl start telnet.socket", log, 1)
		RunCommand("systemctl enable telnet.socket", log, 1)
		lg(log, 'Starting FTP service', 0)
		RunCommand("[[ -f /etc/vsftpd.conf ]] && sed -i 's/listen=NO/listen=YES/' /etc/vsftpd.conf", log, 1)
		RunCommand("[[ -f /etc/vsftpd.conf ]] && sed -i 's/listen_ipv6=YES/listen_ipv6=NO/' /etc/vsftpd.conf", log, 1)
		RunCommand("systemctl  start vsftpd", log, 1)
		RunCommand("systemctl  enable vsftpd", log, 1)
		lg(log, 'Starting NFS service', 0)
		RunCommand("systemctl  start nfs-server", log, 1)
		RunCommand("systemctl  enable nfs-server", log, 1)
		RunCommand("systemctl  start nfs", log, 1)
		RunCommand("systemctl  enable nfs", log, 1)
		RunCommand("systemctl  start syslog", log, 0)
		RunCommand("systemctl  enable syslog", log, 0)
	return 0


def ValidIP(ip):
	return ip.count('.') == 3 and  all(0<=int(num)<256 for num in ip.rstrip().split('.'))


def CheckNetwork(ltp_vars, log, slog):
	if 'SLS_DIR' not in ltp_vars:
		ltp_vars['SLS_DIR'] = '/var/log/sls/'
	elif ltp_vars['SLS_DIR'].strip() == '':
		ltp_vars['SLS_DIR'] = '/var/log/sls/'
	logdir = ltp_vars['SLS_DIR']

	if ('LHOST' not in ltp_vars) or ('RHOST' not in ltp_vars):
		lg(log, "Please define 'LHOST' and 'RHOST' in ./sls_config file")
		return 1
	if ltp_vars['LHOST'] == '' or ltp_vars['RHOST'] == '':
		lg(log, "Please define 'LHOST' and 'RHOST' in ./sls_config file")
		return 1

	InstallPackage('bind-utils', log)
	LHOST = ltp_vars['LHOST']
	RHOST = ltp_vars['RHOST']
	if ValidIP(LHOST):
		LHOST_IP = LHOST.strip()
	else:
		LHOST_IP = RunCommand("host " + LHOST, log, 2)
		if not ValidIP(LHOST_IP.split(' ')[-1]):
			lg(log, "LHOST entry in ./sls_config  : " + LHOST + ' Invalid')
			return 1
		LHOST_IP = LHOST_IP.split(' ')[-1].strip()

	if ValidIP(RHOST):
		RHOST_IP = RHOST.strip()
	else:
		RHOST_IP = RunCommand("host " + RHOST, log, 2)
		if not ValidIP(RHOST_IP.split(' ')[-1]):
			lg(log, "RHOST entry in ./sls_config  : " + RHOST + ' Invalid')
			return 1
		RHOST_IP = RHOST_IP.split(' ')[-1].strip()
	
	lg(slog, "LHOST=" + LHOST)
	lg(slog, "IPV4_LHOST=" + LHOST_IP)
	lg(slog, "RHOST=" + RHOST)
	lg(slog, "IPV4_RHOST=" + RHOST_IP)

	command = "ip -o addr | grep -w %s|awk '{print $2}'" % (LHOST_IP)
	LHOST_INTERFACE = RunCommand(command, log, 2)
	LHOST_INTERFACE = LHOST_INTERFACE.strip()
	if LHOST_INTERFACE == '':
		lg(log, 'Network Interface for IP: '+ LHOST_IP + ' on LHOST: '+ LHOST + ' could not be found')
		return 1
	lg(slog, "LHOST_IFACES=" + LHOST_INTERFACE)
        
	command = "ip a l|grep -B1 %s|grep ether|awk '{print $2}'" % (LHOST_IP)
	LHOST_MAC = RunCommand(command, log, 2)
	LHOST_MAC = LHOST_MAC.strip()
	if LHOST_MAC == '':
		lg(log, 'Mac Address for for IP: '+ LHOST_IP + ' on LHOST: '+ LHOST + ' could not be found')
		return 1
	lg(slog, "LHOST_HWADDRS=" + LHOST_MAC)
       
	command = "ssh -o PasswordAuthentication=no -n -q %s 'ip a' > %s/rhost_interfaces" % (RHOST, logdir) 
	RunCommand(command, log, 1)
	command = "cat %s/rhost_interfaces|grep -B2 -w %s|head -1|awk '{print $2}'|sed 's/://g'" % (logdir, RHOST_IP)
	RHOST_INTERFACE = RunCommand(command, log, 2)
	RHOST_INTERFACE = RHOST_INTERFACE.strip()
	lg(slog, "RHOST_IFACES=" + RHOST_INTERFACE)

	command = "cat %s/rhost_interfaces|grep -B2 -w %s|grep ether|tail -1|awk '{print $2}'" % (logdir, RHOST_IP)
	RHOST_MAC = RunCommand(command, log, 2)
	RHOST_MAC = RHOST_MAC.strip()
	if RHOST_INTERFACE == '':
		lg(log, 'Mac Address for for IP: '+ RHOST_IP + ' on RHOST: '+ RHOST + ' could not be found')
		return 1
	lg(slog, "RHOST_HWADDRS=" + RHOST_MAC)

	if not re.search(':',RHOST_MAC, re.M):
		lg(log, 'Mac Address for for IP: '+ RHOST_IP + ' on RHOST: '+ RHOST + ' is not correct : ' + RHOST_MAC)
		return 1	
	
	os.environ['LHOST'] = LHOST
	os.environ['IPV4_LHOST'] = LHOST_IP
	os.environ['IPV6_LHOST'] = ''
	os.environ['LHOST_IFACES'] = LHOST_INTERFACE
	os.environ['LHOST_HWADDRS'] = LHOST_MAC

	os.environ['RHOST'] = RHOST
	os.environ['IPV4_RHOST'] = RHOST_IP
	os.environ['IPV6_RHOST'] = ''
	os.environ['RHOST_IFACES'] = RHOST_INTERFACE
	os.environ['RHOST_HWADDRS'] = RHOST_MAC
	
	return 0


def GetRandom(max_val, min_val=1):
	return random.randrange(min_val, max_val)


def MachineInfo(log, ltp_vars):
	lg(log, '------------------------------------------------------------------------', 0)
	lg(log, 'LTP VERSION: ', 0)
	lg(log, '------------------------------------------------------------------------', 0)
	RunCommand("/opt/ltp/runltp -e", log, 0, 0)
	lg(log, '\n', 0)

	lg(log, '------------------------------------------------------------------------', 0)
	lg(log, 'Network Interface Details: ', 0)
	lg(log, '------------------------------------------------------------------------', 0)
	command = "ip a | grep -B2 `host " + os.environ['HOSTNAME'] + " | awk '{print $4}'`" 
	netdir = '/sys/class/net/'
	for device in os.listdir(netdir):
		driver = os.path.realpath(netdir + '/' + device + '/device/driver/module').split('/')[-1]
		if driver == 'module':
			driver = 'None'
		command = 'cat /sys/class/net/' + device + '/address'
		address = RunCommand(command, None, 2, 0)
		command = 'cat /sys/class/net/' + device + '/operstate'
		operstate = RunCommand(command, None, 2, 0)
		lg(log, device + "\t: " + driver + " : " + address + " : " + operstate, 0)
	lg(log, '\n', 0)

	ret = RunCommand("which lparstat > /dev/null 2>&1", None, 0, 0)
	if ret == 0:
		lg(log, '------------------------------------------------------------------------', 0)
		lg(log, 'lparstat -i', 0)
		lg(log, '------------------------------------------------------------------------', 0)
		RunCommand("lparstat -i", log, 0, 0)
		lg(log, '\n', 0)

	ret = RunCommand("which lsblk > /dev/null 2>&1", None, 0, 0)
	if ret == 0:
		lg(log, '------------------------------------------------------------------------', 0)
		lg(log, 'lsblk', 0)
		lg(log, '------------------------------------------------------------------------', 0)
		RunCommand("lsblk", log, 0, 0)
		lg(log, '\n', 0)
	
	#If User specified extra commands to collect lpar info
	if 'MACHINE_INFO_COMMANDS' in ltp_vars:
		ecommands = ltp_vars['MACHINE_INFO_COMMANDS'].strip().split(',')
		for cmd in ecommands:
			cmd = cmd.strip()
			if cmd == '':
				continue
			command = "which %s > /dev/null 2>&1" % cmd.split(' ')[0]
			if int(RunCommand(command, None, 0, 0)) == 0:
				lg(log, '------------------------------------------------------------------------', 0)
				lg(log, cmd, 0)
				lg(log, '------------------------------------------------------------------------', 0)
				RunCommand(cmd, log, 0, 0)
				lg(log, '\n', 0)
			else:
				line = "%cmd is not found"


def CheckNw(log, ltp_vars):
	ping_target = ''
	if ('IPV4_RHOST' in os.environ) and os.environ['IPV4_RHOST'] != '':
		ping_target = os.environ['IPV4_RHOST'].strip()
	elif ltp_vars['HTTP_SERVER']:
		ping_target = ltp_vars['HTTP_SERVER'].strip()
	else:
		lg(log, 'Plese define either HTTP_SERVER or RHOST in ./sls_config')
		return 1

	if RunCommand("ping -c 4 " + ping_target + '> /dev/null', None, 0, 0) != 0:
		time.sleep(20)
		check_iter = 1
		while check_iter <= 30:
			if RunCommand("ping -c 4 " + ping_target + '> /dev/null', None, 0, 0) != 0:
				line = "[CheckNw] [info] ping to %s Failed, retry:%d" % (ping_target,check_iter)
				lg(log, line, 0, 1)
			else:
				line = "[CheckNw] [info] ping to %s Pass, retry:%d" % (ping_target,check_iter)
				lg(log, line, 0, 1)
				return 0
			check_iter +=1
		return 1
	else:
		line = "[CheckNw] [info] ping to %s Pass" % (ping_target)
		lg(log, line, 0, 1)
	return 0


def GetFreeCPU(log, tlog):
	while True:
		command = "top -b -n 4 | grep Cpu | tail -n 1 | cut -f 4 -d , | cut -f 1 -d .| sed 's/ //g'"
		idle_cpu = int(RunCommand(command, tlog, 2, 0))
		time.sleep(2)
		idle_cpu += int(RunCommand(command, tlog, 2, 0))
		time.sleep(2)
		idle_cpu += int(RunCommand(command, tlog, 2, 0))
		time.sleep(2)
		idle_cpu += int(RunCommand(command, tlog, 2, 0))
		time.sleep(1)
		idle_cpu /= 4
		cpu_line = "[GetFreeCPU] [info] Avg idle_cpu is %d" % (idle_cpu)
		lg(log, cpu_line, 0, 1)
		
		if idle_cpu < 27:
			rnum = GetRandom(327)
			line =	"[GetFreeCPU] [warn] Not enough free CPUs. Waiting for %d seconds." % (rnum)
			lg(log, line, 0, 1)
			time.sleep(rnum)
		else:
			line = "[GetFreeCPU] [info] Idle CPU: %d" % (idle_cpu)
			lg(log, line, 0, 1)
			break


def GetFreeMem(log, tlog):
	while True:
		lg(tlog, "Flushing the system buffers (sync). Tests not progressing? sync might by hung", 0)
		RunCommand("sync", tlog, 2, 0)
		RunCommand("echo 3 > /proc/sys/vm/drop_caches", tlog, 2, 0)
		free_mem = RunCommand("free -m | awk '{print $4}' | grep -v [a-z] | head -n 1", tlog, 2, 0)
		line = "[GetFreeMem] [info] Available free memory %s MB" % (free_mem.strip())
		lg(log, line, 0, 1)
		free_swap = RunCommand("free -m | awk '{print $4}' | grep -v [a-z] | tail -n 1", tlog, 2, 0)
		line = "[GetFreeMem] [info] Available swap space %s MB" % (free_swap.strip())
		lg(log, line, 0, 1)
		
		if int(free_mem) < 427:
			rnum = GetRandom(327)
			line = "[GetFreeMem] [warn] Not enough free Memory. Waiting for %d seconds." % (rnum)
			lg(log, line, 0, 1)
			time.sleep(rnum)
		else:
			line = "[GetFreeMem] [info] Free Memory %s MB" % (free_mem.strip())
			lg(log, line, 0, 1)
			break


def GetFsSpace(log, tlog):
	while True:
		command = "df -hl | grep -w '/$' | awk ' {print $5}' | cut -f 1 -d '%'"
		root_fs_size = int(RunCommand(command, tlog, 2, 0))
		if root_fs_size > 90:
			wline = "[GetFsSpace] [warn] / is more than 90%%. IO tests using /tmp will fail"
			lg(log, wline, 0, 1)
			RunCommand('wall / filesystem is close to 100%%. Please fix asap', tlog, 2)
			lg(log, "Cleaning up loop devices")
			RunCommand("losetup -D", tlog)
			time.sleep(27)
		else:
			break


def SetMinFree(log):
	#Setting min_free_kbytes to 5% of RAM
	#Change to use the -g flag -- chanh
	mem = int(RunCommand("free -g|grep -i 'mem'|awk -F' ' '{print $2}'", log, 2, 0))
	mem = mem * 1024 * 1024
	fkbyte= mem / 20
	command = "echo %d > /proc/sys/vm/min_free_kbytes" % fkbyte
	RunCommand(command, log)

	#Setting swappiness to 40
	RunCommand("echo 40 > /proc/sys/vm/swappiness", log)	


def CreateFS(DISKS, FSTYPES, log):
	#Check Disks
	IODISKS = DISKS.split(',')
	IODISKS = [x for x in IODISKS if x]
	if len(IODISKS) == 0:
		lg(log, 'No disks mentioned in sls_config')	
		return 2
	DISKS = []
	for D in IODISKS:
		command = "ls /dev/|grep -w %s" % D
		if int(RunCommand(command, log, 0, 0)) == 0:
			DISKS.append('/dev/%s' % D)
		else:
			command = "ls /dev/mapper/|grep -w %s" % D
			if int(RunCommand(command, log, 0, 0)) == 0:
				DISKS.append('/dev/mapper/%s' % D)
			else:
				lg(log, "Disk: %s not found" % D)
				return 1

		#Check if already mounted
		command = "mount |grep -w %s" % D
		if int(RunCommand(command, log, 0, 0)) == 0:
			lg(log,'Looks like %s is already in use, please check : %s' % (D,command)) 	
			return 1

		command = "mount |grep -e '%s_' -e '%s-'" % (D,D)
		if int(RunCommand(command, log, 0, 0)) == 0:
			lg(log,'Looks like %s is already in use, please check : %s' % (D,command)) 	
			return 1
	#Remove old io directories
	command = "ls -d /tmp/ltp_io|tr '\n' ' '"
	io_dirs = RunCommand(command, log, 2, 0)
	iodirs = io_dirs.split(' ')
	for d in iodirs:
		command = "rm -rf %s" % d
		RunCommand(command, log, 0, 0)

	#decide on FS or LVM
	FS_AVAILABLE = []
	lvm = 0;
	if FSTYPES.strip() != '' and len(FSTYPES.split(',')) != 0:
		FS_TYPES = FSTYPES.split(',')
		for T in FS_TYPES:
			T = T.strip()
			if T == 'lvm' or T == 'LVM':
				lvm = 1
				command = "which vgcreate"
				if int(RunCommand(command, log, 0, 0))  != 0:
					lg(log, 'vgcreate command not found')
					return 1
				continue
			command = "which mkfs.%s" % T
			if int(RunCommand(command, log, 0, 0)) == 0:
				FS_AVAILABLE.append(T)
			else:
				lg(log, 'mkfs.%s command not found' % T)
				return 1
	else:
		FS_TYPES = ['xfs', 'btrfs', 'ext3', 'ext4', 'ext2']
		for FS in FS_TYPES:
			command = "which mkfs.%s" % FS
			if int(RunCommand(command, log, 0, 0)) == 0:
				FS_AVAILABLE.append(FS)
	if len(FS_AVAILABLE) == 0:
		if lvm == 0:
			lg(log, 'None of mkfs command available for FS TYPES: %s' % ' '.join(FS_TYPES))
			return 1	
		FS_TYPES = ['xfs', 'btrfs', 'ext3', 'ext4', 'ext2']
		for FS in FS_TYPES:
			command = "which mkfs.%s" % FS
			if int(RunCommand(command, log, 0, 0)) == 0:
				FS_AVAILABLE.append(FS)		
		if len(FS_AVAILABLE) == 0:
			lg(log, 'None of mkfs command available for FS TYPES: %s' % ' '.join(FS_TYPES))
			return 1
	#Create LVM if required
	if lvm == 1:
		command = 'vgs|grep -w ltp_io'
		if int(RunCommand(command, log, 0, 0)) == 0:
			lg(log,'VG: ltp_io is already present, please remove it using: vgremove and lvremove and retry')
			return 1
		lg(log, 'Creating VG on disks : %s' % ' '.join(DISKS))
		command = 'vgcreate ltp_io %s' % ' '.join(DISKS)
		lg(log, command)
		if int(RunCommand(command, log, 0, 1)) != 0:
			lg(log, 'VG creation failed')
			return 1
		
		lg(log, 'Creating LV on disks : %s' % ' '.join(DISKS))
		command = 'lvcreate -l 100%FREE -n ltp_io ltp_io'
		lg(log, command)
		if int(RunCommand(command, log, 0, 1)) != 0:
			lg(log, 'LV creation failed')
			return 1

		if len(FS_AVAILABLE) == 1:
			FSINDEX = 0
		else:
			FSINDEX = GetRandom(len(FS_AVAILABLE)-1, 0)
		FS = FS_AVAILABLE[FSINDEX]
		lg(log, 'Creating FS : %s on LV:ltp_io' % FS)
		if FS in ['ext2', 'ext3', 'ext4']:
			force_option = '-F'
		else:
			force_option = '-f'
		command = 'mkfs.%s %s /dev/mapper/ltp_io-ltp_io' % (FS, force_option)
		lg(log, command)
		if int(RunCommand(command, log, 0, 1)) != 0:
			lg(log, '%s : Failed' % command)
			return 1
		command = 'mkdir -p /tmp/ltp_io0'
		RunCommand(command, log, 1, 1)
		lg(log, 'Mounting LV:/dev/mapper/ltp_io-ltp_io to /tmp/ltp_io0')
		command = 'mount /dev/mapper/ltp_io-ltp_io /tmp/ltp_io0'
		lg(log,command)
		if int(RunCommand(command, log, 0, 1)) != 0:
			lg(log, '%s : Failed' % command)
			return 1
	else:
		dnum = 0
		for D in DISKS:
			if len(FS_AVAILABLE) == 1:
				FSINDEX = 0
			else:
				FSINDEX = GetRandom(len(FS_AVAILABLE)-1, 0)
			FS = FS_AVAILABLE[FSINDEX]
			lg(log,'Creating FS:%s on Disk:%s' % (FS,D))
			if FS in ['ext2', 'ext3', 'ext4']:
				force_option = '-F'
			else:
				force_option = '-f'
			command = 'mkfs.%s %s %s' % (FS, force_option, D)
			lg(log,command)
			if int(RunCommand(command, log, 0, 1)) != 0:
				chkcommand = "blkid %s|grep -w 'TYPE='|wc -l" % D
				if int(RunCommand(chkcommand, log, 2, 1)) == 0:
					lg(log, '%s : Failed' % command)
					return 1	
				else:
					lg(log, 'FS exists on %s, so proceeding' % D)
			command = 'mkdir -p /tmp/ltp_io%d' % dnum
			RunCommand(command, log, 1, 1)
			lg(log, 'Mounting Disk:%s to /tmp/ltp_io%d' % (D,dnum))
			command = 'mount %s /tmp/ltp_io%d' % (D,dnum)
			lg(log,command)
			if int(RunCommand(command, log, 0, 1)) != 0:
				lg(log, '%s : Failed' % command)
				return 1
			dnum += 1
			
	return 0 

def OOMKill(log, slog):
	while True:
		#If free memory is low, kill processes
		command = "free -m | awk '{print $2}' | grep -v [a-z] | head -n 1"
		total_mem = int(RunCommand(command, log, 2, 0))
		command = "free -m | awk '{print $4}' | grep -v [a-z] | head -n 1"
		free_mem = int(RunCommand(command, log, 2, 0))
		free_mem_percent = (free_mem*100)/total_mem
		if free_mem_percent <= 10:
			line = "Free Memory is %d%%" % free_mem_percent
			lg(slog, line, 0)
			command = "ps -eaf|grep memcg|grep -v grep|awk '{print $2}'|tr '\n' '^'"
			output = RunCommand(command, log, 2, 0)
			pids = output.split('^')
			pids = [i for i in pids if i]
			for pid in pids:
				if pid == '' or pid == ' ':
					continue
				line = "Calling kill -9 %s" % pid
				lg(slog, line, 0)
				command = "kill -9 %s" % (pid)
				RunCommand(command, log, 0)	

			command = "ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem | head|awk -F' ' '{print $1\":\"$2\" \"$3}'|tr '/' ' '|awk -F' ' '{print $1\" \"$NF}'|tr ':' ' ' | awk '{ print $3}' |grep -v CMD|tr '\n' '^'"
			output = RunCommand(command, log, 2, 0)
			ship = output.split('^')	
			ship = [i for i in ship if i]
			for boat in ship:
				boat = boat.replace('[','').replace(']','')
				if boat == 'sh':
					continue
				command = "grep -w %s /opt/ltp/runtest/*|grep -v 'grep'|wc -l" % boat
				if int(RunCommand(command, log, 2, 0)) != 0:
					line = "Calling killall -I %s" % boat
					lg(slog, line, 0)
					command = "killall  -I %s" % boat
					RunCommand(command, log, 0)
					line = "Calling pkill %s" % boat
					lg(slog, line, 0)
					command = "pkill %s" % boat
					RunCommand(command, log, 0)
					lg(slog, "Free Mem < 10%%. Killed %s process!!" % boat, 0)
				
				command = "echo %s | grep -i memcg*|grep -v 'grep'|wc -l" % boat
				if int(RunCommand(command, log, 2, 0)) != 0:
					line = "Calling killall -I %s" % boat
					lg(slog, line, 0)
					command = "killall  -I %s" % boat
					RunCommand(command, log, 0)
					line = "Calling pkill %s" % boat
					lg(slog, line, 0)
					command = "pkill %s" % boat
					RunCommand(command, log, 0)
			


		#To remove any local ltp interface getting created. This may impact lab network
		command = "ip a | grep -i -e dummy -e ltp|wc -l"
		if int(RunCommand(command, log, 2, 0)) != 0:
			command = "ls /sys/class/net/|grep ltp|tr '\n' '^'"
			output = RunCommand(command, log, 2, 0)
			ltp_interfaces = output.split('^')
			ltp_interfaces = [i for i in ltp_interfaces if i]
			for i in ltp_interfaces:
				line = "Deleting unwanted interface %s" % i
				lg(slog, line, 0)
				command = "ip link delete %s" % i
				RunCommand(command, log, 0)
			
		time.sleep(2)
	
		command = 'ps -eaf|grep go_sls|grep -v grep|wc -l'
		if int(RunCommand(command, log, 2, 0)) <= 1:
			lg(slog, "Looks like go_sls is completed, OOMKiller is exiting")


def ParseScenFile(log, sfile):
	with open(sfile) as fp:
		lines = fp.readlines()
	fp.close()
	linenum = 1
	for l in lines:
		if l == '' or l == ' ' or l.startswith('#'):
			linenum += 1
			continue
		if re.search('HOST', l, re.M) and re.search('=', l, re.M):
			linenum += 1
			continue
		if not re.search('Scenario_', l, re.M|re.I):
			lg(log, 'No Scenario_ tag found in Line no %d' % linenum)
			return(1)
		if not re.search(':', l, re.M|re.I) and not re.search('=', l, re.M) and not re.search('HOST', l, re.M):
			lg(log, 'No colon found in line no %d' % linenum)
			return(1)
		if len(l.split(':')) != 4:
			lg(log, "Invalid line, line no: %d" % linenum)
			return 1
		tests = l.split(':')[3].split(' ')
		for test in tests:
			if test == '':
				continue
			if len(test.split('|')) != 2:
				pl = "Invalid test: %s in Line no:%d" % (test,linenum)
				lg(log, pl)
				return(1)
			testname  = test.split('(')[0].strip()
			testsuite = test.split('(')[1].split('|')[0].strip()
			iters = test.split('|')[1].replace(')','').strip()
			if testname == '':
				lg(log, "Invalid test name in line no: %d" % linenum)
				return(1)
			if testsuite == '':
				lg(log, "Invalid test suite name in line no: %d" % linenum)
				return(1)
			try:
				int(iters)
			except Exception:
				lg(log, "Invalid iterations for test:%s in line no: %d" % (test,linenum))
				return(1)
		linenum +=1
		
	return 0


def GetSuiteIterations(tlog, test, ltp_vars):
	suite = ''; 
	iterations = 0

	#get Test suite
	command = "ls /opt/ltp/testcases/bin/%s | wc -l" % (test)	
	if int(RunCommand(command, tlog, 0, 0)) != 0:
		line = "Test_%s_ not_found_under_/opt/ltp/testcases/bin/" % test
		return [line, iterations]

	runtest = '/opt/ltp/runtest/'
	command = "grep -w %s %s/* |wc -l" % (test, runtest)
	suite_c = int(RunCommand(command, tlog, 2, 0).strip())
	if suite_c == 0:
		line  = "Test_suite_for_test_:%s_not_found" % test
		return [ line, iterations]
	elif suite_c > 1:
		command = "grep -w %s %s/* | cut -f 1 -d : |sort -u|tr '\n' '^'" % (test, runtest)
		output = RunCommand(command, tlog, 2, 0)
		suite_m = output.split('^')
		suite_len = len(suite_m)
		rnum = GetRandom(suite_len) - 1
		if rnum < 0:
			rnum = 0
		suite = suite_m[rnum]
	else:
		command = "grep -w %s %s/* | cut -f 1 -d :" % (test, runtest)
		suite = RunCommand(command, tlog, 2, 0)

	suite = suite.replace(runtest,'').strip().replace('/','')

	#get Iterations
	RIT = os.environ['RIT'].strip()
	R = RIT.split('|')
	R = list(dict.fromkeys(R))
	R = [i for i in R if i]
	RIT_PATTERN = " -e ".join(R)
	command = "echo %s|grep -i -e %s|grep -v grep|wc -l" % (test,RIT_PATTERN)
	if int(RunCommand(command, tlog, 2, 0)) != 0:
		if 'ITERATIONS' in ltp_vars and ltp_vars['ITERATIONS'] != '':
			iterations = int(ltp_vars['ITERATIONS'])
			if iterations > 4:
				iterations = GetRandom(4)
		else:
			iterations = GetRandom(4)
	else:
		#If user has mentioned iterations, go for it
		if 'ITERATIONS' in ltp_vars:
			iterations = ltp_vars['ITERATIONS']
			if iterations == '':
				iterations = GetRandom(127)
			else:
				iterations = int(ltp_vars['ITERATIONS'])
		else:
			iterations = GetRandom(127)
	
	return [suite, iterations]
