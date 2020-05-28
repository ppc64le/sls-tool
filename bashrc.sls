# .bashrc

# User specific aliases and functions

alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'

# Source global definitions
if [ -f /etc/bashrc ]; then
	. /etc/bashrc
fi
########## REAL TIME CHECK.ALL STATUS ##########
# show check.all result when there is failure
PROMPT_COMMAND="grep -q 'FAIL' /tmp/do.focus.all/check/* &>/dev/null && { echo '{*!* check.all failures, fix ASAP and then rerun check.all *!*}'; grep -h 'FAIL' /tmp/do.focus.all/check/* 2>/dev/null; }"

#*************************************************
#Standard LTP Environment variables
#*************************************************
export TST_USE_SSH=ssh
export LTP_TIMEOUT_MUL=40
export TST_DISABLE_APPARMOR=1
export LTP_RSH=ssh
export PASSWD=don2rry
export LTPROOT=/opt/ltp
export PS1='\[\e[31m\]\u@\h:\w\[\e[0m\] '

#*******************************************************
#Advance LTP Environment variables. For expert users only
#*******************************************************
#export NS_DURATION
#export CONNECTION_TOTAL

#*************************************************
#Export appropriate PATH
#*************************************************
export PATH=$PATH:/opt/ltp:/opt/ltp/testcases/bin:/opt/ltp/testscripts

