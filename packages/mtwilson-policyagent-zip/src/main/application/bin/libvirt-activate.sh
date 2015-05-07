#!/bin/bash

### BEGIN INIT INFO
# Provides:          libvirt-activate
# Required-Start:    $local_fs $network $remote_fs
# Required-Stop:     $local_fs $network $remote_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: libvirt-activate
# Description:       libvirt-activate
### END INIT INFO

# Ensure the script is loaded just after init scripts

logfile=/var/log/libvirt-activate.log

DISK_LOCATION=/var/lib/nova/instances/enc_disks/
ENC_KEY_LOCATION=/var/lib/nova/keys/
MOUNT_LOCATION=/mnt/crypto/
DEK=/var/lib/nova/keys/

# Assumption, 
# 1. key names are similar to the image UUID
# 2. mount names(image_id), so we need not touch them at this stage.
#	Once the above mounts are created, links will be accessible


mount_enc_partitions() {

	export BINDING_KEY_PASSWORD=$(cat /opt/trustagent/configuration/trustagent.properties | grep binding.key.secret | cut -d = -f 2)
	cd $ENC_KEY_LOCATION
	for KEY in `ls $ENC_KEY_LOCATION | grep ".key"`
	do
	# For each key
	# 1. Get the details of UUID
	# 2. Unseal the key
	# 3. Create a loop device for the particular key
	# 4. Mount the loop device using the particular key
	
		# e.g key file 12345677890.enckey
		IMAGE_ID=`echo $KEY | awk 'BEGIN{FS="."}{print $1}'`
		#DEK=$IMAGE_ID.key
		#tpm_unseal $KEY > $DEK
	 	# Abhay : test : uncomment start
		#/opt/trustagent/bin/tpm_unbindaeskey -k /opt/trustagent/configuration/binding.blob -i $KEY -o "$DEK/${IMAGE_ID}.dek" -q BINDING_KEY -t -x
                /opt/trustagent/bin/tpm_unbindaeskey -k /opt/trustagent/configuration/bindingkey.blob -i $KEY -o "$DEK/${IMAGE_ID}.dek" -q BINDING_KEY_PASSWORD -t -x
		# Abhay : test : uncomment end
	
		# Retrieve the loop device via losetup
		FREE_DEVICE=`losetup -f`
		if [ "$FREE_DEVICE" = "" ] ; then
		    # Find a free node id
		    i=`ls -l /dev/loop* | wc -l`
		    i=$(($i-1))
		    # Create a loop mounted device
		    loop_dev=`mknod -m0660 /dev/loop$i b 7 $i`
		    chown root:disk $loop_dev
		fi
		FREE_DEVICE=`losetup -f`
		# Setup the device over the file under encrypted mount
		if [ ! -z "$FREE_DEVICE" ]; then
		    losetup $FREE_DEVICE $DISK_LOCATION/$IMAGE_ID
		else
		    echo "Error : Created device not visible"
		fi
		# cryptsetup luksFormat --keyfile=$DEK /dev/mapper/$IMAGE_ID
		echo "cryptsetup luksOpen --key-file=$DEK/${IMAGE_ID}.dek $FREE_DEVICE $IMAGE_ID"
		cryptsetup luksOpen --key-file="$DEK/${IMAGE_ID}.dek" $FREE_DEVICE $IMAGE_ID
		# Delete the decrypted key
		# Abhay : uncomment this : 
                rm -rf "$DEK/${IMAGE_ID}.dek"
		# Assuming $MOUNT_LOCATION/$IMAGE_ID is already present 
		mount -t ext4 /dev/mapper/$IMAGE_ID $MOUNT_LOCATION/$IMAGE_ID
		# VM_Images will be links available under /var/lib/nova/instance/encrypted_images/UUID
		# pointing to images 
	done
}


case "$1" in
 start)
	echo "libvirt-activate : Starting up libvirt-activate"
	echo "Start call received" >> $logfile
	echo "==========================" >> $logfile
	echo "Initial mounts ===========" >> $logfile
	mount >> $logfile
	mount_enc_partitions
        echo "Final mounts ===========" >> $logfile
        mount >> $logfile
   ;;
 stop)
	echo "Stop call received" >> $logfile
   ;;
 restart)
	echo "Restart call received" >> $logfile
   ;;
 *)
   echo "Usage: libvirt-activate {start|stop|restart}" >&2
   exit 3
   ;;
esac

exit 0
