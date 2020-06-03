IBM Structured LTP Stress SLS Tool
-------------------------------------------------------------------------------
SLS is a tool designed to run opensource [Linux Test Project tests](https://github.com/linux-test-project/ltp) in System Test or Stress Test environment. It mainly uses several control structures to regulate the stress during long incubation cycles.

The test scenarios are dynamiclly generated based on config file input. It makes use of the resource utilization effectively, to keep the system busy all the time without overcommiting the resource. It does mix of tests dynamically at run time, to check the system stability in longer run

The initial Open Source release of SLS caters to all manners of Power platforms running Linux. It supports any type of Linux running in different guest modes (Baremetal, PowerVM LPAR, KVM Guest). Although, the scope of execution is limited within the operating sytem boundry, this has not been tested on other architecture.

Test Grouping
-------------------------------------------------------------------------------
LTP contains large number of testcases. It is important to organise the tests into smaller sub groups, to have a flexible run during stress test. The group of tests can be found under [tc_group](https://github.com/ppc64le/sls-tool/blob/master/tc_group)
- **BASE**  General Kernel Stress|Memory Management|Process Management|Security|Threads|IPC
- **IO** General IO Test|File System|File Stress|LVM
- **NFS** General NFS Stress|NFS procotol & version|Network File stress/Lock tests|RPC
- **TCP** General Network Stress|Network Feature Stress|TCP/IP Command Tests|SCTP|Stress test for TCP/IP protocol stack

Prerequisites
-------------------------------------------------------------------------------
Python 

Copy & Install
-------------------------------------------------------------------------------
```
$ git clone https://github.com/ppc64le/sls-tool
$ cd sls-tool ; $ ./install_sls.py
```
Setting up SLS:
-------------------------------------------------------------------------------
It is necessary to prepare the test environment to effectively run SLS. This involves setting up the latest [LTP](https://github.com/linux-test-project/ltp) code, installing necessary RPMs, starting the services, loading modules etc.,
```
install_sls.py
```
`WARNING` It is improtant to run this successfully before going to next step. Failing to install or start any services has to be manually addressed, else the associated LTP tests will fail.

Starting SLS:
-------------------------------------------------------------------------------
Review and edit [sls_config](https://github.com/ppc64le/sls-tool/blob/master/sls_config) file. Refer [README](https://github.com/ppc64le/sls-tool/blob/master/README_SLS_CONFIG)

Review start.sls.py usage and start accordingly
```
./start_sls.py --help
usage: start_sls.py [-h] [-b] [-i] [-t] [-n] [-s S [S ...]] [-r R [R ...]]
Start SLS
optional arguments:
  -h, --help    show this help message and exit
  -b            BASE Tests
  -i            IO Tests
  -t            Network Tests
  -n            NFS Tests
  -s S [S ...]  Test Suites
  -r R [R ...]  Run with Sceanrio file
```
More Examples:
-------------------------------------------------------------------------------
To run all the four focus area (*-t and -n require RHOST and LHOST varilable to be exported in sls_config*)
```
$ ./start_sls.py -b -i -n -t 
```
To run only BASE tests
```
$ ./start_sls.py -b
```
To run with last scenario file (*This is helpful while recreating the problems, since it maintains the order of execution*)
```
./start_sls.py -r /tmp/SCENARIO_LIST
```
To run testcases from [syscalls](https://github.com/linux-test-project/ltp/blob/master/runtest/syscalls) suite 
```
./start_sls.py -s syscalls
```
Monitoring
-------------------------------------------------------------------------------
To view the status and details of tests running:
```
$ ./show_results.py
```
Review show_results.py usage and use accordingly
```
./show_results.py --help
usage: show_results.py [-h] [-c] [-m] [-s] [-t] [-i] [-d]

Show LTP Results

optional arguments:
  -h, --help  show this help message and exit
  -c          Show CPU Usage
  -m          Show Memory Usage
  -s          Show Test Scenarios
  -t          Show Tests
  -i          Show In Progress Tests
  -d          Show Details of In Progress Tests
```
The hierarchical logs are created under the path specified by TC_HTML_PATH
```
Default Path --> /LOGS/SLS/Distro Name/Distro Level/Machine_Name/Date & Time Stamp/
```
Refer to [README](https://github.com/ppc64le/sls-tool/blob/master/README_MONITORING) to know about the logs created during execution

Stopping tests
-------------------------------------------------------------------------------
To stop SLS tests
```
./stop_sls.py
```
Authors
-------------------------------------------------------------------------------
Original author, who developed the initial version of SLS under shell code

Chethan Jain -chetjain@in.ibm.com 

Current owner, who rewritten the code in Python language

Manjunath H.R -manjuhr1@in.ibm.com
