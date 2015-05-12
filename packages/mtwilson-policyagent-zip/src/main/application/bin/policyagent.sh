#!/bin/bash
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
 
   
  if [ ! -d "$DISK_LOCATION/$IMAGE_ID" ]; then
      #TODO: The size of the sparse file should be configurable
      pa_log "truncate -s 2G $DISK_LOCATION/$IMAGE_ID  "
      size_in_percentage=$(grep "sparsefile.size=" $configfile | cut -d "=" -f2)
	  if [ -z "$size_in_percentage" ]; then
	      #default sparse file size
          size_in_percentage=50
	   fi
      image_size=$(stat -c%s "$infile")
      pa_log " image size is: $image_size"
      if [ ! -z "$image_size" ] && [ ! -z "$size_in_percentage" ]; then
          size_in_bytes=$(($image_size*$size_in_percentage/100))
          pa_log "Extra size in bytes: $size_in_bytes"
          sparse_file_size=$(($image_size+$size_in_bytes))
          pa_log "Sparse file size will be: $sparse_file_size"
      else
          pa_log "Please provide a valid integer number in the config file to specify the sparse file size"
          exit 1
      fi
      truncate -s $sparse_file_size $DISK_LOCATION/$IMAGE_ID  
      sparse_file_exit_status=$?
      pa_log "The sparse file creation status: $sparse_file_exit_status"      


      loop_dev=`losetup --find`
      loopdev_exit_status=$?
      pa_log "Loop_dev: $loop_dev"
      pa_log "The loopdev  status: $loopdev_exit_status"
      if [ -z $loop_dev ]; then
          #TODO: Keep track of loopback device numbers being used
           pa_log "Requires additional loop device for use"
           count_loop_dev=`ls -l /dev/loop* | wc -l`
           if ["$count_loop_dev" > 8 ]; then
               pa_log "Create a new loop device for use"
			   #Subtracting the count by 1 as there are 8 loop devices and 1 controller device
               $count_loop_dev=$count_loop_dev-1
               loop_dev=`mknod  -m 660 /dev/loop$count_loop_dev -b 7 $count_loop_dev`
           else
               pa_log "Unable to create additional loop device"
               exit 1
           fi
      elif [ ! -z "$loop_dev" ]; then
          pa_log "losetup $loop_dev $DISK_LOCATION/$IMAGE_ID"
          losetup $loop_dev $DISK_LOCATION/$IMAGE_ID
      else
           pa_log "No loop device available"
           exit 1
      fi
      
      losetup --find >> $logfile 2>> $logfile
    
      #open the dm-crypt device with password
      #tpm_unbindaeskey –k /opt/trustagent/configuration/bindingkey.blob –i $ENC_KEY_LOCATION/$image_ID.key –q BINDING_KEY_PASSWORD –t -x | openssl enc -base64 cmd  | cryptsetup luksOpen –-key-file=-  $loop_dev $IMAGE_ID

    #Delete this later 
      #/opt/trustagent/bin/tpm_unbindaeskey -k $private_key -i "$ENC_KEY_LOCATION/${IMAGE_ID}.key"  -o "$ENC_KEY_LOCATION/${IMAGE_ID}.dek" -q BINDING_KEY_PASSWORD -t -x 2>> $logfile
     
      pa_log "loopback device: $loop_dev"

      pa_log "cryptsetup -v luksFormat --key-file="$ENC_KEY_LOCATION/${IMAGE_ID}.dek" $loop_dev"
      /opt/trustagent/bin/tpm_unbindaeskey -k /opt/trustagent/configuration/bindingkey.blob -i $ENC_KEY_LOCATION/${IMAGE_ID}.key -q BINDING_KEY_PASSWORD -t -x | cryptsetup -v --batch-mode luksFormat --key-file=- $loop_dev 2>> $logfile
      luksFormat_status=$?
      pa_log "luksFormat : $luksFormat_status"

        pa_log "cryptsetup -v luksOpen --key-file="$ENC_KEY_LOCATION/${IMAGE_ID}.dek" $loop_dev $IMAGE_ID"
       /opt/trustagent/bin/tpm_unbindaeskey -k /opt/trustagent/configuration/bindingkey.blob -i $ENC_KEY_LOCATION/${IMAGE_ID}.key -q BINDING_KEY_PASSWORD -t -x  | cryptsetup -v luksOpen --key-file=- $loop_dev $IMAGE_ID 2>> $logfile
      luksOpen_status=$?
      pa_log "luksOpen : $luksOpen_status"

      pa_log "mkfs.ext4 /dev/mapper/$IMAGE_ID"
      #FORMAT ENCRYPTED DEVICE WITH EXT4 FILE SYSTEM
      mkfs.ext4 /dev/mapper/$IMAGE_ID


     #MOUNT DEVICE OVER MOUNT LOCATION IDENTIFIED BY <IMAGE_UUID>
     if [ -d "$MOUNT_LOCATION/$IMAGE_ID" ]; then
	 pa_log "mount -t ext4 /dev/mapper/$IMAGE_ID $MOUNT_LOCATION/$IMAGE_ID"
         mount -t ext4 /dev/mapper/$IMAGE_ID $MOUNT_LOCATION/$IMAGE_ID
    else
        pa_log "Exit the policy agent"
        exit 1
    fi
    #Delete
  else
      pa_log "Sparse file for the current image id already exists: $DISK_LOCATION/$IMAGE_ID"
  fi
   
  if [ ! -d "$MOUNT_LOCATION/$IMAGE_ID/_base/$IMAGE_ID" ]; then
      pa_log "mkdir -p $MOUNT_LOCATION/$IMAGE_ID/_base"
      mkdir -p $MOUNT_LOCATION/$IMAGE_ID/_base
  else
      pa_log "mount location _base dir already exits: $MOUNT_LOCATION/$IMAGE_ID/_base/"
  fi
  #VM-enc
  
   ls -la $MOUNT_LOCATION >> $logfile
   ls -la $MOUNT_LOCATION/$IMAGE_ID/_base/ >> $logfile
     
   if [ -n "$ENC_KEY_LOCATION/${IMAGE_ID}.key" ]; then
	   pa_log "/opt/trustagent/bin/tpm_unbindaeskey -k $private_key -i $ENC_KEY_LOCATION/${IMAGE_ID}.key  -o $ENC_KEY_LOCATION/${IMAGE_ID}.dek -q BINDING_KEY_PASSWORD -t -x"
       #/opt/trustagent/bin/tpm_unbindaeskey -k $private_key -i "$ENC_KEY_LOCATION/${IMAGE_ID}.key"  -o "$ENC_KEY_LOCATION/${IMAGE_ID}.dek" -q BINDING_KEY_PASSWORD -t -x 2>> $logfile
    
	   pa_log "openssl enc -base64 -in $ENC_KEY_LOCATION/${IMAGE_ID}.dek -out $dek_base64"
       export pa_dek_key=`/opt/trustagent/bin/tpm_unbindaeskey -k /opt/trustagent/configuration/bindingkey.blob -i $ENC_KEY_LOCATION/${IMAGE_ID}.key -q BINDING_KEY_PASSWORD -t -x  | openssl enc -base64`
       
       #export pa_dek_key=`cat $dek_base64`
       cat $pa_dek_key >> $logfile
	   pa_log "openssl enc -d -aes-128-ofb -in $infile -out $decfile -pass env:pa_dek_key"
       openssl enc -d -aes-128-ofb -in "$infile" -out "$decfile" -pass env:pa_dek_key 2>> $logfile
       dek_status=$?
       pa_log "decryptionn: $dek_status"

      ls -la $MOUNT_LOCATION/$IMAGE_ID/_base/ >> $logfile
   fi
 
   if ! openssl_encrypted_file $decfile; then
      if [ -n "$IMAGE_ID" ]; then
          pa_log "Decrypted image: $IMAGE_ID"
          # XXX DEBUG for debugging only - 
          #cp $decfile /tmp/image.dec
      fi

      
       pa_log "ln -s -f $decfile $TARGET"
       ln -s -f $decfile $TARGET 2>> $logfile
       link_status=`echo $?`
       pa_log "Link_Status: $link_status"
	

       mv $INSTANCE_DIR $MOUNT_LOCATION/$IMAGE_ID/$INASTANCE_ID/
       check_status=$?
       pa_log "Move INSTANCE_DIR status: $check_status"
       if [ "$check_status" -eq 0 ]; then
           ln -s -f $MOUNT_LOCATION/$IMAGE_ID/$INSTANCE_ID $INSTANCE_DIR
       fi
      
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
               image_path=`find $temp_dir -name '*.[img|vhd|raw]*'`
               pa_log "image location: $image_path"
               pa_log "*******************************************"
               if [ -n $image_path ]; then
                   cp $image_path $TARGET
               else  
                   pa_log "failed to untar and copy the image successfully"
                   exit 1
               fi
            else
                # There will be other sources like swift to add later
                pa_log "Image is not downloaded from the glance"
            fi
        fi
    fi
	
	if [ -d "$temp_dir" ]; then
	   rm -rf $temp_dir
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
  if ! options=$(getopt -n policyagent -l project-id:,instance-name:,base-image:,image-id:,target:,instance_id:,mtwilson-trustpolicy-location: -- "$@"); then exit 1; fi
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

  
  
    if [ -n "$TARGET" ]; then
        if [ -f $TARGET ]; then
	    pa_log "Found base image tar file: $TARGET"
          
	   #untar the file to extract the vm image and trust policy
	   untar_file
           pa_log "Untar func completed"
	 
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
	          pa_log "image decryption completed"
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
         curl --proxy http://$kms_proxy_ipaddress:$kms_proxy_port --verbose -X POST -H "Content-Type: application/x-pem-file" -H "Accept: application/octet-stream" --data-binary @$aikdir/aik.pem  "$url" > "$ENC_KEY_LOCATION/${IMAGE_ID}.key"
         
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


