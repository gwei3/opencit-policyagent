#!/bin/bash

service nova-compute stop
cp driver.py /usr/share/pyshared/nova/virt/libvirt
cp utils.py /usr/share/pyshared/nova/virt/libvirt
service nova-compute start

