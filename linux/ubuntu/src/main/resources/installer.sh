
apt-get install xmlstarlet
echo $?
dir=/opt/policyagent/configuration/
#configuration_dir=/opt/policyagent/configuration/
if [ ! -d $dir ]; then
   mkdir -p $dir
fi
#if [ ! -d $configuration_dir ]
#   mkdir /opt/policyagent/configuration/
#fi

mv /usr/lib/python2.7/dist-packages/nova/virt/xenapi/vmops.py /usr/lib/python2.7/dist-packages/nova/virt/xenapi/vmops.py.bak
cp ./libvirt/vmops.py /usr/lib/python2.7/dist-packages/nova/virt/xenapi/vmops.py


mv /usr/lib/python2.7/dist-packages/nova/virt/libvirt/driver.py /usr/lib/python2.7/dist-packages/nova/virt/libvirt/driver.py.bak
mv /usr/lib/python2.7/dist-packages/nova/virt/libvirt/utils.py /usr/lib/python2.7/dist-packages/nova/virt/libvirt/utils.py.bak
cp ./libvirt/driver.py /usr/lib/python2.7/dist-packages/nova/virt/libvirt/driver.py
cp ./libvirt/utils.py /usr/lib/python2.7/dist-packages/nova/virt/libvirt/utils.py

cp ./policyagent /usr/local/bin/policyagent
chmod +x /usr/local/bin/policyagent

rm -f /usr/lib/python2.7/dist-packages/nova/virt/libvirt/driver.pyc
rm -f /usr/lib/python2.7/dist-packages/nova/virt/libvirt/utils.pyc

chown nova:nova /usr/local/bin/policyagent
rm -f /var/log/policyagent.log
touch /var/log/policyagent.log
chown nova:nova  /var/log/policyagent.log
rm /var/lib/nova/instances/_base/*

chmod +x ./Validate.java
javac ./Validate.java 
mv ./Validate*.class /usr/local/bin/
chmod +x /usr/local/bin/Validate*
chown nova:nova /usr/local/bin/Validate*
