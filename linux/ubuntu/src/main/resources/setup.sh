#!/bin/sh

# check for software required by mhagent
required_tools="openssl hd md5sum curl base64"
aikdir=/etc/intel/cloudsecurity/cert

if [ ! -d $aikdir ]; then echo "mhagent requires the AIK to obtain keys; install tagent"; fi
for t in $required_tools
do
  if [ -z `which $t` ]; then echo "mhagent requires $t"; fi
done

chmod +x mhagent
cp mhagent /usr/local/bin

cp driver.py /usr/share/pyshared/nova/virt/libvirt/
service nova-compute stop
service nova-compute start

