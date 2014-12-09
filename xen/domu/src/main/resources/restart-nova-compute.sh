#!/bin/bash
# 10.1.70.240 /usr/local/bin/restart-nova-compute
# On this system nova services don't have the easy restart command working.
nova_compute_pid=`ps gauxw | grep nova-compute | grep -v grep | awk '{ print $2 }'`
if [ -n "$nova_compute_pid" ]; then kill -9 $nova_compute_pid; fi
/usr/bin/python /usr/local/bin/nova-compute --config-file /etc/nova/nova.conf 2>&1 > /var/log/nova/nova-compute.log  &
