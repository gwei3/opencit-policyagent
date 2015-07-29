#!/bin/bash

# chkconfig: 2345 80 30
# description: Intel Policy Agent Service

### BEGIN INIT INFO
# Provides:          policyagent
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Should-Start:      $portmap
# Should-Stop:       $portmap
# X-Start-Before:    nis
# X-Stop-After:      nis
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# X-Interactive:     true
# Short-Description: policyagent
# Description:       Main script to run policyagent commands
### END INIT INFO
DESC="POLICYAGENT"
NAME=policyagent

# the home directory must be defined before we load any environment or
# configuration files; it is explicitly passed through the sudo command
export POLICYAGENT_HOME=${POLICYAGENT_HOME:-/opt/policyagent}

# the env directory is not configurable; it is defined as POLICYAGENT_HOME/env
# and the administrator may use a symlink if necessary to place it anywhere else
export POLICYAGENT_ENV=$POLICYAGENT_HOME/env

policyagent_load_env() {
  local env_files="$@"
  local env_file_exports
  for env_file in $env_files; do
    if [ -n "$env_file" ] && [ -f "$env_file" ]; then
      . $env_file
      env_file_exports=$(cat $env_file | grep -E '^[A-Z0-9_]+\s*=' | cut -d = -f 1)
      if [ -n "$env_file_exports" ]; then eval export $env_file_exports; fi
    fi
  done  
}

if [ -z "$POLICYAGENT_USERNAME" ]; then
  policyagent_load_env $POLICYAGENT_HOME/env/policyagent-username
fi

###################################################################################################

## if non-root execution is specified, and we are currently root, start over; the POLICYAGENT_SUDO variable limits this to one
## attempt we make an exception for the uninstall command, which may require root access to delete users and certain directories
#if [ -n "$POLICYAGENT_USERNAME" ] && [ "$POLICYAGENT_USERNAME" != "root" ] && [ $(whoami) == "root" ] && [ -z "$POLICYAGENT_SUDO" ] && [ "$1" != "uninstall" ]; then
#  sudo -u $POLICYAGENT_USERNAME POLICYAGENT_USERNAME=$POLICYAGENT_USERNAME POLICYAGENT_HOME=$POLICYAGENT_HOME POLICYAGENT_PASSWORD=$POLICYAGENT_PASSWORD POLICYAGENT_SUDO=true policyagent $*
#  exit $?
#fi

###################################################################################################

# load environment variables; these may override the defaults set above and also
# note that policyagent-username file is loaded twice, once before sudo and once
# here after sudo.
if [ -d $POLICYAGENT_ENV ]; then
  policyagent_load_env $(ls -1 $POLICYAGENT_ENV/*)
fi

# default directory layout follows the 'home' style
export POLICYAGENT_CONFIGURATION=${POLICYAGENT_CONFIGURATION:-${POLICYAGENT_CONF:-$POLICYAGENT_HOME/configuration}}
export POLICYAGENT_BIN=${POLICYAGENT_BIN:-$POLICYAGENT_HOME/bin}
export POLICYAGENT_REPOSITORY=${POLICYAGENT_REPOSITORY:-$POLICYAGENT_HOME/repository}
export POLICYAGENT_LOGS=${POLICYAGENT_LOGS:-$POLICYAGENT_HOME/logs}

###################################################################################################


# load linux utility
if [ -f "$POLICYAGENT_HOME/bin/functions.sh" ]; then
  . $POLICYAGENT_HOME/bin/functions.sh
fi

###################################################################################################

# the standard PID file location /var/run is typically owned by root;
# if we are running as non-root and the standard location isn't writable 
# then we need a different place
POLICYAGENT_PID_FILE=${POLICYAGENT_PID_FILE:-/var/run/policyagent.pid}
if [ ! -w "$POLICYAGENT_PID_FILE" ] && [ ! -w $(dirname "$POLICYAGENT_PID_FILE") ]; then
  POLICYAGENT_PID_FILE=$POLICYAGENT_REPOSITORY/policyagent.pid
fi

###################################################################################################



logfile=/var/log/policyagent.log
configfile=/opt/policyagent/configuration/policyagent.properties
INSTANCE_DIR=/var/lib/nova/instances/

if [ ! -f $logfile ]; then 
   touch $logfile; 
fi


md5() {
  local file="$1"
  md5sum "$file" | awk '{ print $1 }'
}


pa_log() {
  #local datestr=`date '+%Y-%m-%d %H:%M:%S'`
  # use RFC 822 format
  local datestr=`date -R`
  echo "[$datestr] $$ $@" >> $logfile
}

# arguments:  <since-timestamp>
# the <since-timestamp> required argument is a timestamp where to start extracting data from the log
# lines in the log on or after the <since-timestamp> until the end are returned
# Usage example:  policyagent getlog 1382720512
# This would print all log statements on or after "Fri, 25 Oct 2013 10:01:52 -0700"
# To obtain a timestamp from a date in that format do this: date --utc --date "Fri, 25 Oct 2013 10:01:52 -0700" +%s
pa_getlog() {
  local since="$1"
  local trigger=false
  # default timestamp format for comparison is seconds since epoch (these days an 11 digit number)
  # if the caller supplied a 14-digit number they are including milliseconds so we add zeros to our format so we can compare
  local timestamp_format="%s"
  local since_length=`echo $since | wc -c`
  if [ $since_length -eq 14 ]; then timestamp_format="%s000"; fi
  while read line
  do
    if $trigger; then
      echo $line
    else
      # Given a logfile entry like "[Fri, 25 Oct 2013 10:01:59 -0700] 7088 Decrypted VM image",
      # extract the date using   awk -F '[][]' '{ print $2 }' which  outputs   Fri, 25 Oct 2013 10:01:59 -0700
      # and pass it to the date command using xargs -i ... {} ...  to create a command line like this:
      #  date --utc --date "Fri, 25 Oct 2013 10:01:52 -0700" +%s
      # which converts the date from that format into a  timestamp like 1383322675
      local linetime=`echo $line | awk -F '[][]' '{ print $2 }' | xargs -i date --utc --date "{}" +"$timestamp_format"`
      if [ -n "$linetime" ] && [ $linetime -ge $since ]; then
        trigger=true
        echo $line
      fi
    fi
  done < $logfile
}


openssl_encrypted_file() {
  local filename="$1"
  encheader=`hexdump -C -n 8 $filename | head -n 1 | grep "Salted__"`
  if [ -n "$encheader" ]; then
      return 0
  fi
  return 1
}

pa_encrypt() {
  local infile="$1"
  local encfile="$infile.enc"
  if [ ! -f $infile ]; then
     echo "error: failed to encrypt $infile: file not found"
     return 1
  fi
  if openssl_encrypted_file $infile; then
    echo "error: failed to encrypt $infile: already encrypted";
    return 2;
  fi
  # XXX TODO need to change ciphers to aes-256-cbc and also add hmac for authentication!
  openssl enc -aes-128-ofb -in "$infile" -out "$encfile" -pass pass:password
  if openssl_encrypted_file $encfile; then
     mv $encfile $infile
     retur n0
  fi
  echo "error: failed to encrypt $infile"
  return 3
}

pa_delete_instance(){
pa_log "Delete instance"
ins_dir=$1
pa_log "INSTANCE to be deleted: $ins_dir"
instance_symlink=`readlink $ins_dir`
sym_stat=$?
pa_log "Found symlink stat: $sym_stat"

pa_log "Deleting symlink: $instance_symlink"
rm -rf $instance_symlink
sym_dir_stat=$?
pa_log "Deletion status: $sym_dir_stat"
if [ $sym_dir_stat -eq 0 ]; then
    unlink $ins_dir
else
   pa_log "There was an error deleting the $instance_symlink_target"
   exit 1
fi


}

pa_decrypt() {
  DISK_LOCATION=/var/lib/nova/instances/enc_disks
  MOUNT_LOCATION=/mnt/crypto/
  ENC_KEY_LOCATION=/var/lib/nova/keys/
  NOVA_BASE=/var/lib/nova/instances/_base/
  NOVA_INSTANCES=/var/lib/nova/instances/
  
  local infile="$1"
  local private_key=/opt/trustagent/configuration/bindingkey.blob
  local dek_base64=/var/lib/nova/dek_id_base64
  export BINDING_KEY_PASSWORD=$(cat /opt/trustagent/configuration/trustagent.properties | grep binding.key.secret | cut -d = -f 2)  
  local decdir=$MOUNT_LOCATION/$IMAGE_ID/_base/
  decfile=$MOUNT_LOCATION/$IMAGE_ID/_base/$IMAGE_ID
  
   
   
  if [ ! -f $infile ]; then
     pa_log "error: failed to decrypt $infile: file not found"
     return 1
  fi
  
  ls -la $infile >> $logfile
  if ! openssl_encrypted_file $infile; then
     pa_log "error: failed to decrypt $infile: not encrypted";
     return 1
  fi
  
  if [ ! -z $DEK_URL ]; then
      pa_log "send the dek request to key server"
      pa_request_dek $DEK_URL
  else
      pa_log "No DEK URL"
	  exit 1
  fi
  

  if [ ! -d "$DISK_LOCATION" ]; then
      mkdir $DISK_LOCATION
  fi
  
  if [ ! -d "$MOUNT_LOCATION/$IMAGE_ID" ]; then
      mkdir -p $MOUNT_LOCATION/$IMAGE_ID
  fi
 
   
  if [ ! -e "$DISK_LOCATION/$IMAGE_ID" ]; then
      sparse_file_size=$(grep "sparsefile.size=" $configfile | cut -d "=" -f2)
	  if [ -z "$sparse_file_size" ]; then
	      #sparse file size will be obtained in KB
              sparse_file_size=$(df -k / | tail -n +2 | sed 'N;s/\n/ /' | awk '{print $4}') #remove first line|remove newlines|get 4th arg
          else
              available_space=$(df -k / | tail -n +2 | sed 'N;s/\n/ /' | awk '{print $4}') #remove first line|remove newlines|get 4th arg
              if [ "$sparse_file_size" -gt "$available_space" ]; then
                  pa_log "The size of the sparse file in the properties file exceeds the available disk size"
                  pa_log "Allocating the available disk size to continue with the launch"
                  sparse_file_size=$(df -k / | tail -n +2 | sed 'N;s/\n/ /' | awk '{print $4}') #remove first line|remove newlines|get 4th arg
              fi
	   fi
      
      #avail_disk=`df -h / | tail -1 |awk {'print $4'}`
      #root disk size converted from GB to KB
	  root_disk_size=$(($ROOT_DISK*1024*1024))
      pa_log "==root disk size: $root_disk_size=="
      pa_log "==sparse file size: $sparse_file_size=="
      if [ "$root_disk_size" -gt "$sparse_file_size" ]; then
          pa_log "WARNING:The size of the root disk exceeds the allocated sparse file size"
          pa_log "Copying a file larger than the size of the sparse file on the launched VM might cause failure"
      else
          pa_log "The available disk size is: $sparse_file_size"
      fi
      size_in_bytes=$(($sparse_file_size*1024))
	  pa_log "Size allocated for the Sparse file is: $size_in_bytes bytes"
      truncate -s $size_in_bytes $DISK_LOCATION/$IMAGE_ID  
      sparse_file_exit_status=$?
      pa_log "The sparse file creation status: $sparse_file_exit_status"      


      loop_dev=`losetup --find`
      loopdev_exit_status=$?
      pa_log "The loopdev  status: $loopdev_exit_status"
      if [ -z $loop_dev ]; then
          #TODO: Keep track of loopback device numbers being used
           pa_log "Requires additional loop device for use"
           count=`ls -l /dev/loop[^-]* | wc -l`
           pa_log "Create a new loop device for use"
	       add_dev=`mknod  -m 660 /dev/loop$count b 7 $count`
		   loop_dev=`losetup --find`
      fi
      if [ ! -z "$loop_dev" ]; then
          pa_log "losetup $loop_dev $DISK_LOCATION/$IMAGE_ID"
          losetup $loop_dev $DISK_LOCATION/$IMAGE_ID
      else
           pa_log "No loop device available"
           exit 1
      fi
      
         
      pa_log "Available loopback device: $loop_dev"

      pa_log "cryptsetup -v luksFormat --key-file="$ENC_KEY_LOCATION/${IMAGE_ID}.dek" $loop_dev"
      /opt/trustagent/bin/tpm_unbindaeskey -k /opt/trustagent/configuration/bindingkey.blob -i $ENC_KEY_LOCATION/${IMAGE_ID}.key -q BINDING_KEY_PASSWORD -t -x | cryptsetup -v --batch-mode luksFormat --key-file=- $loop_dev 2>> $logfile
      luksFormat_status=$?
      pa_log "luksFormat : $luksFormat_status"

        pa_log "cryptsetup -v luksOpen --key-file="$ENC_KEY_LOCATION/${IMAGE_ID}.dek" $loop_dev $IMAGE_ID"
       /opt/trustagent/bin/tpm_unbindaeskey -k /opt/trustagent/configuration/bindingkey.blob -i $ENC_KEY_LOCATION/${IMAGE_ID}.key -q BINDING_KEY_PASSWORD -t -x  | cryptsetup -v luksOpen --key-file=- $loop_dev $IMAGE_ID 2>> $logfile
      luksOpen_status=$?
      pa_log "luksOpen : $luksOpen_status"

      pa_log "mkfs.ext4 -v /dev/mapper/$IMAGE_ID"
      mkfs.ext4 -v  /dev/mapper/$IMAGE_ID
     

     #MOUNT DEVICE OVER MOUNT LOCATION IDENTIFIED BY <IMAGE_UUID>
     if [ -e "$MOUNT_LOCATION/$IMAGE_ID" ]; then
         pa_log "mount -t ext4 /dev/mapper/$IMAGE_ID $MOUNT_LOCATION/$IMAGE_ID"
         mount -t ext4 /dev/mapper/$IMAGE_ID $MOUNT_LOCATION/$IMAGE_ID    
    else
        pa_log "Exit the policy agent"
        exit 1
    fi
  
  else
      pa_log "Sparse file for the current image id already exists: $DISK_LOCATION/$IMAGE_ID"
  fi
   
  if [ ! -d "$MOUNT_LOCATION/$IMAGE_ID/_base/$IMAGE_ID" ]; then
      pa_log "mkdir -p $MOUNT_LOCATION/$IMAGE_ID/_base"
      mkdir -p $MOUNT_LOCATION/$IMAGE_ID/_base
  else
      pa_log "mount location _base dir already exits: $MOUNT_LOCATION/$IMAGE_ID/_base/"
  fi
  
  
   ls -la $MOUNT_LOCATION >> $logfile
   ls -la $MOUNT_LOCATION/$IMAGE_ID/_base/ >> $logfile
     
   if [ -n "$ENC_KEY_LOCATION/${IMAGE_ID}.key" -a ! -f "$MOUNT_LOCATION/$IMAGE_ID/_base/$IMAGE_ID"  ]; then
	   pa_log "/opt/trustagent/bin/tpm_unbindaeskey -k $private_key -i $ENC_KEY_LOCATION/${IMAGE_ID}.key  -o $ENC_KEY_LOCATION/${IMAGE_ID}.dek -q BINDING_KEY_PASSWORD -t -x"
       
    
	   pa_log "openssl enc -base64 -in $ENC_KEY_LOCATION/${IMAGE_ID}.dek -out $dek_base64"
       export pa_dek_key=`/opt/trustagent/bin/tpm_unbindaeskey -k /opt/trustagent/configuration/bindingkey.blob -i $ENC_KEY_LOCATION/${IMAGE_ID}.key -q BINDING_KEY_PASSWORD -t -x  | openssl enc -base64`
       
       
	   pa_log "openssl enc -d -aes-128-ofb -in $infile -out $decfile -pass env:pa_dek_key"
       openssl enc -d -aes-128-ofb -in "$infile" -out "$decfile" -pass env:pa_dek_key 2>> $logfile
       dek_status=$?
       pa_log "decryptionn: $dek_status"

      ls -la $MOUNT_LOCATION/$IMAGE_ID/_base/ >> $logfile
   fi
 
   if ! openssl_encrypted_file $decfile; then
      if [ -n "$IMAGE_ID" ]; then
          pa_log "Decrypted image: $IMAGE_ID"
      fi

      
       pa_log "ln -s -f $decfile $TARGET"
       ln -s -f $decfile $TARGET 2>> $logfile
       link_status=`echo $?`
       pa_log "Link_Status: $link_status"
       
	

       mv $INSTANCE_DIR $MOUNT_LOCATION/$IMAGE_ID/$INASTANCE_ID/ 2>> $logfile
       check_status=$?
       pa_log "Move INSTANCE_DIR status: $check_status"
       if [ "$check_status" -eq 0 ]; then
           ln -s -f $MOUNT_LOCATION/$IMAGE_ID/$INSTANCE_ID $INSTANCE_DIR 2>> $logfile
       fi
      
      ls -l $MOUNT_LOCATION/$IMAGE_ID/$INSTANCE_ID >> $logfile
      pa_log "************"
      ls -l $INSTANCE_DIR >> $logfile
      rm -rf $ENC_KEY_LOCATION/${IMAGE_ID}.dek
 
      return 0
  else
      pa_log "error: failed to decrypt $infile"
      return 2
  fi
}


untar_file() {
    if [ -n "$TARGET" ]; then
        if [ -f $TARGET ]; then
	pa_log "ls -latr $TARGET **********************"
		ls -latr $TARGET >> $logfile
            local temp_dir=$TARGET"_temp"
            trust_policy_loc="${TARGET}.xml"
            if [ ! -d "$temp_dir" ]; then
                 pa_log "created temp dir"
                 mkdir $temp_dir
            else
			     pa_log "temp dir already exists"
			fi
			
            
            if [ "$MTW_TRUST_POLICY" == "glance_image_tar" ]; then
               pa_log " Image is been downloaded from the glance"
               tar -xvf $TARGET -C $temp_dir
               #ls -l $temp_dir >> $logfile
               mv $temp_dir/*.xml $trust_policy_loc
	       cp $trust_policy_loc $INSTANCE_DIR/"trustpolicy.xml"
               pa_log "trust policy location: $trust_policy_loc"
               pa_log "*******************************************"
               image_path=`find $temp_dir -name '*.[img|vhd|raw|qcow2]*'`
               pa_log "image location: $image_path"
               pa_log "*******************************************"
               if [ -n $image_path ]; then
                   cp $image_path $TARGET
               else  
                   pa_log "failed to untar and copy the image successfully"
                   exit 1
               fi
	pa_log "ls -latr $TARGET **********************"
	ls -latr $TARGET >> $logfile
            else
                # There will be other sources like swift to add later
                pa_log "Image is not downloaded from the glance"
            fi
        fi
    fi
	
	if [ -d "$temp_dir" ]; then
	   echo "REMOVE THIS"
	   #rm -rf $temp_dir
	fi
}


pa_verify_trustpolicy_signature(){
        trust_policy=$1
        if [ -n "$trust_policy" ]; then   
           #Call the Verifier Java snippet
           tagentScript="/usr/local/bin/tagent"
           if [ ! -f "$tagentScript" ]; then
             pa_log "Error: Missing tagent script";
             echo "Missing tagent script";
             exit 1
           fi
           pa_log "$tagentScript verify-trustpolicy-signature $trust_policy"
           $tagentScript verify-trustpolicy-signature "$trust_policy"
           #/usr/bin/java -classpath  "$verifierJavaLoc" "$javaClassName" "$trust_policy"
           verifier_exit_status=$?
           pa_log "signature verfier exitCode: $verifier_exit_status"
           if [ $verifier_exit_status -eq 0 ]; then
               pa_log " Signature verification was successful"
               pa_log "policy agent will proceed to decrypt the image"
			   cp $trust_policy $INSTANCE_DIR/"trustpolicy.xml"
           else
               pa_log "Signature verification was unsuccessful. VM launch process will be aborted"
               exit 1
           fi
        fi
}

parse_trust_policy(){
    if [ -n "$trust_policy_loc" ]; then
            is_encrypted=`grep -r "<Encryption" $trust_policy_loc`
            if [ ! -z "$is_encrypted" ]; then
                pa_log "received an encrypted image"
                CHECKSUM=`cat $trust_policy_loc | xmlstarlet fo --noindent | sed -e 's/ xmlns.*=".*"//g' | xmlstarlet sel -t -v "/TrustPolicy/Encryption/Checksum"`
                DEK_URL=`cat $trust_policy_loc | xmlstarlet fo --noindent | sed -e 's/ xmlns.*=".*"//g' | xmlstarlet sel -t -v "/TrustPolicy/Encryption/Key"`
                pa_log "Checksum: $CHECKSUM"
                pa_log "DEK URL: $DEK_URL"
            else
                pa_log "no encryption tag found"
            fi
	fi 
}

parse_args() {
  if ! options=$(getopt -n policyagent -l project-id:,instance-name:,base-image:,image-id:,target:,instance_id:,mtwilson-trustpolicy-location:,instance_type_root_gb: -- "$@"); then exit 1; fi
  eval set -- "$options"
  while [ $# -gt 0 ]
  do
    case $1 in
      --project-id) PROJECT_ID="$2"; shift;;
      --instance-name) INSTANCE_NAME="$2"; shift;;
      --base-image) BASE_IMAGE="$2"; shift;;
      --image-id) IMAGE_ID="$2"; shift;;
      --target) TARGET="$2"; shift;;
      --instance_id) INSTANCE_ID="$2";shift;;
      --mtwilson-trustpolicy-location) MTW_TRUST_POLICY="$2";shift;;
      --instance_type_root_gb) ROOT_DISK="$2";shift;;
    esac
    shift
  done
}

generate_manifestlist(){
     cat $trust_policy_loc | xmlstarlet fo --noindent | sed -e 's/ xmlns.*=".*"//g' | xmlstarlet sel -t -c "/TrustPolicy/Whitelist" | xmlstarlet ed -u '/Whitelist/*' -v '' | xmlstarlet ed -r "Whitelist" -v "Manifest" |xmlstarlet ed -r "/Manifest/@DigestAlg" -v 'xmlns="mtwilson:trustdirector:manifest:1.1" DigestAlg'> $INSTANCE_DIR/manifestlist.xml
 }

pa_launch() {
  pa_log "pa_launch: $@"
  pa_log "Project Id: $PROJECT_ID"
  pa_log "Instance Name: $INSTANCE_NAME"
  pa_log "Base Image: $BASE_IMAGE"
  pa_log "Image Id: $IMAGE_ID"
  pa_log "Target: $TARGET"
  pa_log "Checksum: $CHECKSUM"
  pa_log "DEK URL: $DEK_URL"
  pa_log "MANIFEST UUID: $MANIFEST_UUID"
  pa_log "INSTANCE ID: $INSTANCE_ID"
  pa_log "MTW_TRUST_POLICY: $MTW_TRUST_POLICY"
  INSTANCE_DIR=$INSTANCE_DIR/$INSTANCE_ID
  pa_log "INSTANCE_DIR: $INSTANCE_DIR"
  pa_log "ROOT_DISK: $ROOT_DISK"

  
  
    if [ -n "$TARGET" ]; then
        if [ -f $TARGET ]; then
	    pa_log "Found base image tar file: $TARGET"
          
	   #untar the file to extract the vm image and trust policy
	   untar_file
           pa_log "Untar func completed"
           pa_log "Before sleep"
           cat $trust_policy_loc >> $logfile
           pa_log "After sleep"
           cat $trust_policy_loc >> $logfile

           #start TP Check the Encryption Tag, extract DEK and Checksum
            if [ -n "$trust_policy_loc" ]; then
               pa_verify_trustpolicy_signature $trust_policy_loc
   
               #parse the trust policy to generate the manifest list
               generate_manifestlist
     
              #parse trust policy to check if image is encrypted
               parse_trust_policy
           else
               pa_log "Trust policy was not found"
               exit 1
           fi
           
           if [ ! -z $CHECKSUM ] && [ ! -z $DEK_URL ]; then
              pa_decrypt $TARGET >> $logfile
              local current_md5=$(md5 $decfile)
              pa_log "Checksum after decryption: $current_md5"
              if [ "$current_md5" != "$CHECKSUM" ]; then
                 pa_log "Error: checksum is $current_md5 but expected $CHECKSUM"
                 exit 1
		      else
	          pa_log "image decryption completed for $TARGET"
              fi
           else
               pa_log "The image is not encrypted"
           fi
        else
            pa_log "File not found: $TARGET"
            exit 1
        fi
    else
        pa_log "Missing parameter --target"
        exit 1
    fi
}

pa_terminate() {
  pa_log "pa_terminate: $@"
}

pa_suspend() {
  pa_log "pa_suspend: $@"
}

pa_suspend_resume() {
  pa_log "pa_suspend_resume: $@"
}

pa_pause() {
  pa_log "pa_pause: $@"
}

pa_pause_resume() {
  pa_log "pa_pause_resume: $@"
}

pa_fix_aik() {
  local aikdir=/etc/intel/cloudsecurity/cert

  # first prepare the aik for posting. trust agent keeps the aik at /etc/intel/cloudsecurity/cert/aikcert.cer in PEM format.
  if [ ! -f $aikdir/aikcert.crt ]; then
    if [ ! -f $aikdir/aikcert.pem ]; then
      # trust agent aikcert.cer is in broken PEM format... it needs newlines every 76 characters to be correct
      cat $aikdir/aikcert.cer | sed 's/.\{76\}/&\n/g' > $aikdir/aikcert.pem
    fi
    if [ -f $aikdir/aikcert.pem ]; then
      openssl x509 -in $aikdir/aikcert.pem -inform pem -out $aikdir/aikcert.crt -outform der
    fi
  fi

  if [ ! -f $aikdir/aikpubkey.pem ]; then
    if [ -f $aikdir/aikcert.crt ]; then
      openssl x509 -in $aikdir/aikcert.crt -inform der -pubkey -noout > $aikdir/aikpubkey.pem
      openssl rsa -in $aikdir/aikpubkey.pem -inform pem -pubin -out $aikdir/aikpubkey -outform der -pubout
    fi
  fi
}

# example:
# pa_request_dek https://10.254.57.240:8443/v1/data-encryption-key/request/testkey2
pa_request_dek() {
  local url="$1"
  local aikdir
  local dekdir
  key_id=$INSTANCE_DIR/$IMAGE_ID
  
  if [ -x /opt/xensource/tpm/xentpm ]; then
    local aikblobfile=/opt/xensource/tpm/aiktpmblob
    if [ -f $aikblobfile ]; then
      /opt/xensource/tpm/xentpm --get_aik_pem $aikblobfile > /tmp/aikpubkey.pem
    else
      /opt/xensource/tpm/xentpm --get_aik_pem > /tmp/aikpubkey.pem
    fi
    aikdir=/tmp
    dekdir=/tmp
  else
    #pa_fix_aik
    aikdir=/opt/trustagent/configuration
    dekdir=/var/lib/nova
  fi
  if [ ! -f $aikdir/aik.pem ]; then
    pa_log "Error: Missing AIK Public Key";
    echo "Missing AIK Public Key";
    exit 1
  fi

  #wget --no-check-certificate --header "Content-Type: application/octet-stream" --post-file=$aikdir/aikcert.crt "$url"
  #curl --verbose --insecure -X POST -H "Content-Type: application/octet-stream" --data-binary @$aikdir/aikcert.crt "$url"
 
  if [  -f $configfile ]; then
      kms_proxy_ipaddress=$(grep "kmsproxy.server=" $configfile | cut -d "=" -f2)
      kms_proxy_port=$(grep "kmsproxy.server.port=" $configfile | cut -d "=" -f2)
      pa_log "kms proxy ip address: $kms_proxy_ipaddress"
	  pa_log "kms jetty port: $kms_proxy_port"
   
      if [ ! -z "$kms_proxy_ipaddress" ] && [ ! -z "$kms_proxy_port" ]; then
          if [ ! -d $ENC_KEY_LOCATION ]; then
              mkdir $ENC_KEY_LOCATION
          fi
         curl --proxy http://$kms_proxy_ipaddress:$kms_proxy_port --verbose -X POST -H "Content-Type: application/x-pem-file" -H "Accept: application/octet-stream" --data-binary @$aikdir/aik.pem  "$url" > "$ENC_KEY_LOCATION/${IMAGE_ID}.key" 2>> $logfile
         
     else
          pa_log "failed to make a request to kms proxy. Could not find the proxy url"
          exit 1
      fi
  else 
      pa_log "missing configuration file, unable to retrieve the kms proxy ip address"
      exit 1
  fi 
  
  

 if [ -n ""$ENC_KEY_LOCATION/${IMAGE_ID}.key"" ]; then
     pa_log "received key from the key server"
  else
     pa_log "failed to get the Key ID from the Key server"
     exit 1
 fi

}

pa_uninstall() {
  remove_startup_script libvirt-activate
  rm -f "/usr/local/bin/policyagent" 2>/dev/null
  rm -f "/usr/local/bin/libvirt-activate" 2>/dev/null
  if [ -d "${POLICYAGENT_HOME}" ]; then
    rm -rf "${POLICYAGENT_HOME}" 2>/dev/null
  fi
  #groupdel policyagent > /dev/null 2>&1
  #userdel policyagent > /dev/null 2>&1
  echo_success "policy agent uninstall complete"
}

pa_log "Num args: $#"
pa_log "Running as `whoami`"
pa_log "$@"
parse_args $@

case "$1" in
  version)
    echo "policyagent-0.1"
    ;;
  log)
    shift
    pa_log "LOG" $@
    ;;
  getlog)
    shift
    pa_getlog $@
    ;;
  launch)
    shift
    pa_launch $@
    ;;
  delete)
    shift
    pa_delete_instance $@
    ;;
  launch-check)
    shift
    PROJECT_FILE=/var/lib/nova/instances/_base/$PROJECT_ID
    pa_log "launch-check $PROJECT_FILE"
    if [ -f $PROJECT_FILE ]; then
      md5sum $PROJECT_FILE >> $logfile
    else
      echo "cannot find $PROJECT_FILE" >> $logfile
    fi
    ;;
  terminate)
    shift
    pa_terminate $@
    ;;
  pause)
    shift
    pa_pause $@
    ;;
  pause-resume)
    shift
    pa_pause_resume $@
    ;;
  suspend)
    shift
    pa_suspend $@
    ;;
  suspend-resume)
    shift
    pa_suspend_resume $@
    ;;
  encrypt)
    shift
    pa_encrypt $@
    ;;
  decrypt)
    shift
    pa_decrypt $@
    ;;
  request-dek)
    shift
    pa_request_dek $@
    ;;
  uninstall)
    shift
    pa_uninstall $@
    ;;
  #fix-aik)
  #  shift
  #  pa_fix_aik $@
  #  # since this command is probably being run as root, we should ensure the aik is readable to the nova user:
  #  # chmod +rx /etc/intel/cloudsecurity
  #  ;;
  *)
    echo "usage: policyagent version|launch|terminate|pause|pause-resume|suspend|suspend-resume|encrypt|decrypt"
    exit 1
esac

exit $?


