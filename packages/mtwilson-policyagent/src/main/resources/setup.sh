#!/bin/sh

# Policy Agent install script
# Outline:
# 1. load existing environment configuration
# 2. source the "functions.sh" file:  mtwilson-linux-util-3.0-SNAPSHOT.sh
# 3. look for ~/policyagent.env and source it if it's there
# 4. enforce root user installation
# 5. define application directory layout
# 6. backup configuration and repository
# 7. create application directories and set permissions
# 8. store directory layout in env file
# 9. create the policyagent.properties file
# 10. load previous configuration if applicable; current installation settings override
# 11. install prerequisites
# 12. check if KMSPROXY exists and is responding; warn otherwise
# 13. update configuration with variables
# 14. unzip policyagent archive policyagent-zip-0.1-SNAPSHOT.zip into /opt/policyagent, overwrite if any files already exist
# 15. copy utilities script file to application folder
# 16. set additional permissions
# 17. link /usr/local/bin/policyagent -> /opt/policyagent/bin/policyagent, if not already there
# 18. SELinux policy update in case of RHEL system
#####


function getFlavour()
{
        flavour=""
        grep -c -i ubuntu /etc/*-release > /dev/null
        if [ $? -eq 0 ] ; then
                flavour="ubuntu"
        fi
        grep -c -i "red hat" /etc/*-release > /dev/null
        if [ $? -eq 0 ] ; then
                flavour="rhel"
        fi
        grep -c -i fedora /etc/*-release > /dev/null
        if [ $? -eq 0 ] && [ $flavour == "" ] ; then
                flavour="fedora"
        fi
        grep -c -i suse /etc/*-release > /dev/null
        if [ $? -eq 0 ] ; then
                flavour="suse"
        fi
        if [ "$flavour" == "" ] ; then
                echo "Unsupported linux flavor, Supported versions are ubuntu, rhel, fedora"
                exit
        else
                echo $flavour
        fi
}

# default settings
# note the layout setting is used only by this script
# and it is not saved or used by the app script
export POLICYAGENT_HOME=${POLICYAGENT_HOME:-/opt/policyagent}
POLICYAGENT_LAYOUT=${POLICYAGENT_LAYOUT:-home}

# the env directory is not configurable; it is defined as POLICYAGENT_HOME/env and
# the administrator may use a symlink if necessary to place it anywhere else
export POLICYAGENT_ENV=$POLICYAGENT_HOME/env

# load application environment variables if already defined
if [ -d $POLICYAGENT_ENV ]; then
  POLICYAGENT_ENV_FILES=$(ls -1 $POLICYAGENT_ENV/*)
  for env_file in $POLICYAGENT_ENV_FILES; do
    . $env_file
    env_file_exports=$(cat $env_file | grep -E '^[A-Z0-9_]+\s*=' | cut -d = -f 1)
    if [ -n "$env_file_exports" ]; then eval export $env_file_exports; fi
  done
fi

# functions script (mtwilson-linux-util-3.0-SNAPSHOT.sh) is required
# we use the following functions:
# java_detect java_ready_report 
# echo_failure echo_warning
# register_startup_script
UTIL_SCRIPT_FILE=$(ls -1 mtwilson-linux-util-*.sh | head -n 1)
if [ -n "$UTIL_SCRIPT_FILE" ] && [ -f "$UTIL_SCRIPT_FILE" ]; then
  . $UTIL_SCRIPT_FILE
fi

# load installer environment file, if present
if [ -f ~/policyagent.env ]; then
  echo "Loading environment variables from $(cd ~ && pwd)/policyagent.env"
  . ~/policyagent.env
  env_file_exports=$(cat ~/policyagent.env | grep -E '^[A-Z0-9_]+\s*=' | cut -d = -f 1)
  if [ -n "$env_file_exports" ]; then eval export $env_file_exports; fi
else
  echo "No environment file"
fi

# enforce root user installation
if [ "$(whoami)" != "root" ]; then
  echo_failure "Running as $(whoami); must install as root"
  exit -1
fi

# define application directory layout
if [ "$POLICYAGENT_LAYOUT" == "linux" ]; then
  export POLICYAGENT_CONFIGURATION=${POLICYAGENT_CONFIGURATION:-/etc/policyagent}
  export POLICYAGENT_REPOSITORY=${POLICYAGENT_REPOSITORY:-/var/opt/policyagent}
  export POLICYAGENT_LOGS=${POLICYAGENT_LOGS:-/var/log/policyagent}
elif [ "$POLICYAGENT_LAYOUT" == "home" ]; then
  export POLICYAGENT_CONFIGURATION=${POLICYAGENT_CONFIGURATION:-$POLICYAGENT_HOME/configuration}
  export POLICYAGENT_REPOSITORY=${POLICYAGENT_REPOSITORY:-$POLICYAGENT_HOME/repository}
  export POLICYAGENT_LOGS=${POLICYAGENT_LOGS:-$POLICYAGENT_HOME/logs}
fi
export POLICYAGENT_BIN=$POLICYAGENT_HOME/bin

# note that the env dir is not configurable; it is defined as "env" under home
export POLICYAGENT_ENV=$POLICYAGENT_HOME/env

policyagent_backup_configuration() {
  if [ -n "$POLICYAGENT_CONFIGURATION" ] && [ -d "$POLICYAGENT_CONFIGURATION" ] &&
    (find "$POLICYAGENT_CONFIGURATION" -mindepth 1 -print -quit | grep -q .); then
    datestr=`date +%Y%m%d.%H%M`
    backupdir=/var/backup/policyagent.configuration.$datestr
    mkdir -p "$backupdir"
    cp -r $POLICYAGENT_CONFIGURATION $backupdir
  fi
}
policyagent_backup_repository() {
  if [ -n "$POLICYAGENT_REPOSITORY" ] && [ -d "$POLICYAGENT_REPOSITORY" ] &&
    (find "$POLICYAGENT_REPOSITORY" -mindepth 1 -print -quit | grep -q .); then
    datestr=`date +%Y%m%d.%H%M`
    backupdir=/var/backup/policyagent.repository.$datestr
    mkdir -p "$backupdir"
    cp -r $POLICYAGENT_REPOSITORY $backupdir
  fi
}

# backup current configuration and data, if they exist
mkdir -p /var/backup
policyagent_backup_configuration
policyagent_backup_repository

# create application directories (chown will be repeated near end of this script, after setup)
for directory in $POLICYAGENT_HOME $POLICYAGENT_CONFIGURATION $POLICYAGENT_ENV $POLICYAGENT_REPOSITORY $POLICYAGENT_LOGS $POLICYAGENT_BIN; do
  mkdir -p $directory
  chmod 755 $directory
done

# store directory layout in env file
echo "# $(date)" > $POLICYAGENT_ENV/policyagent-layout
echo "export POLICYAGENT_HOME=$POLICYAGENT_HOME" >> $POLICYAGENT_ENV/policyagent-layout
echo "export POLICYAGENT_CONFIGURATION=$POLICYAGENT_CONFIGURATION" >> $POLICYAGENT_ENV/policyagent-layout
echo "export POLICYAGENT_REPOSITORY=$POLICYAGENT_REPOSITORY" >> $POLICYAGENT_ENV/policyagent-layout
echo "export POLICYAGENT_BIN=$POLICYAGENT_BIN" >> $POLICYAGENT_ENV/policyagent-layout
echo "export POLICYAGENT_LOGS=$POLICYAGENT_LOGS" >> $POLICYAGENT_ENV/policyagent-layout

# store the auto-exported environment variables in env file
# to make them available after the script uses sudo to switch users;
# we delete that file later
echo "# $(date)" > $POLICYAGENT_ENV/policyagent-setup
for env_file_var_name in $env_file_exports
do
  eval env_file_var_value="\$$env_file_var_name"
  echo "export $env_file_var_name=$env_file_var_value" >> $POLICYAGENT_ENV/policyagent-setup
done

POLICYAGENT_PROPERTIES_FILE=${POLICYAGENT_PROPERTIES_FILE:-"$POLICYAGENT_CONFIGURATION/policyagent.properties"}
POLICYAGENT_INIT_LOG_FILE=${POLICYAGENT_INIT_LOG_FILE:-"/var/log/policyagent-init.log"}
touch "$POLICYAGENT_INIT_LOG_FILE"
chmod 600 "$POLICYAGENT_INIT_LOG_FILE"

# previous configuration loading
load_policyagent_conf() {
  POLICYAGENT_PROPERTIES_FILE=${POLICYAGENT_PROPERTIES_FILE:-"/opt/policyagent/configuration/policyagent.properties"}
  if [ -n "$DEFAULT_ENV_LOADED" ]; then return; fi

  # policyagent.properties file
  if [ -f "$POLICYAGENT_PROPERTIES_FILE" ]; then
    echo -n "Reading properties from file [$POLICYAGENT_PROPERTIES_FILE]....."
    export CONF_KMSPROXY_SERVER=$(read_property_from_file "KMSPROXY_SERVER" "$POLICYAGENT_PROPERTIES_FILE")
    export CONF_KMSPROXY_SERVER_PORT=$(read_property_from_file "KMSPROXY_SERVER_PORT" "$POLICYAGENT_PROPERTIES_FILE")
    export CONF_SPARSEFILE_SIZE=$(read_property_from_file "SPARSE_FILE_SIZE" "$POLICYAGENT_PROPERTIES_FILE")
    echo_success "Done"
  fi

  export DEFAULT_ENV_LOADED=true
  return 0
}
load_policyagent_defaults() {
  export DEFAULT_KMSPROXY_SERVER=""
  export DEFAULT_KMSPROXY_SERVER_PORT=""
  export DEFAULT_SPARSEFILE_SIZE=""
  export KMSPROXY_SERVER=${KMSPROXY_SERVER:-${CONF_KMSPROXY_SERVER:-$DEFAULT_KMSPROXY_SERVER}}
  export KMSPROXY_SERVER_PORT=${KMSPROXY_SERVER_PORT:-${CONF_KMSPROXY_SERVER_PORT:-$DEFAULT_KMSPROXY_SERVER_PORT}}
  export SPARSEFILE_SIZE=${SPARSEFILE_SIZE:-${CONF_SPARSEFILE_SIZE:-$DEFAULT_SPARSEFILE_SIZE}}
}

# load existing environment; set variables will take precedence
load_policyagent_conf
load_policyagent_defaults

## required properties
#prompt_with_default KMSPROXY_SERVER "KMS Proxy Server:" "$KMSPROXY_SERVER"
#update_property_in_file "KMSPROXY_SERVER" "$POLICYAGENT_PROPERTIES_FILE" "$KMSPROXY_SERVER"
#prompt_with_default KMSPROXY_SERVER_PORT "KMS Proxy Server Port:" "$KMSPROXY_SERVER_PORT"
#update_property_in_file "KMSPROXY_SERVER_PORT" "$POLICYAGENT_PROPERTIES_FILE" "$KMSPROXY_SERVER_PORT"
##prompt_with_default SPARSEFILE_SIZE "Sparse File size (Enter a integer number):" "$SPARSEFILE_SIZE"
##update_property_in_file "sparsefile.size" "$POLICYAGENT_PROPERTIES_FILE" "$SPARSEFILE_SIZE"

# make sure prerequisites are installed
POLICYAGENT_YUM_PACKAGES="zip unzip xmlstarlet python-lxml"
POLICYAGENT_APT_PACKAGES="zip unzip xmlstarlet python-lxml"
POLICYAGENT_YAST_PACKAGES="zip unzip xmlstarlet python-lxml"
POLICYAGENT_ZYPPER_PACKAGES="zip unzip xmlstarlet python-lxml"
auto_install "Installer requirements" "POLICYAGENT"
if [ $? -ne 0 ]; then echo_failure "Failed to install prerequisites through package installer"; exit -1; fi

# extract policyagent  (policyagent-zip-0.1-SNAPSHOT.zip)
echo "Extracting application..."
POLICYAGENT_ZIPFILE=`ls -1 mtwilson-policyagent-*.zip 2>/dev/null | head -n 1`
unzip -oq $POLICYAGENT_ZIPFILE -d $POLICYAGENT_HOME

# check if KMSPROXY exists and is responding; warn otherwise
if [ -n "$KMSPROXY_SERVER" ] && [ -n "$KMSPROXY_SERVER_PORT" ]; then
  kmsProxyOutput=$(curl -ks "http://${KMSPROXY_SERVER}:${KMSPROXY_SERVER_PORT}/v1/keys/1/transfer")
  if [[ $kmsProxyOutput != *"javax.ws.rs.NotAllowedException"* ]]; then
    echo_warning "kmsproxy is not available or is configured incorrectly"
  fi
fi
update_property_in_file "KMSPROXY_SERVER" "$POLICYAGENT_PROPERTIES_FILE" "$KMSPROXY_SERVER"
update_property_in_file "KMSPROXY_SERVER_PORT" "$POLICYAGENT_PROPERTIES_FILE" "$KMSPROXY_SERVER_PORT"

# copy utilities script file to application folder
cp $UTIL_SCRIPT_FILE $POLICYAGENT_HOME/bin/functions.sh

# set permissions
find $POLICYAGENT_HOME/bin/ -type f -exec chmod 744 {} \;
find $POLICYAGENT_HOME/bin/ -type d -exec chmod 755 {} \;

# policyagent
policyagentBin=`which policyagent 2>/dev/null`
if [ -n "$policyagentBin" ]; then
  rm -f "$policyagentBin"
fi
ln -s "$POLICYAGENT_HOME/bin/policyagent.py" "/usr/local/bin/policyagent"

# policyagent-init
policyagent_init=`which policyagent-init 2>/dev/null`
if [ -n "$policyagent_init" ]; then
  rm -f "$policyagent_init"
  remove_startup_script policyagent-init
fi
ln -s "$POLICYAGENT_HOME/bin/policyagent-init" "/usr/local/bin/policyagent-init"

register_startup_script /usr/local/bin/policyagent-init policyagent-init

# delete the temporary setup environment variables file
rm -f $POLICYAGENT_ENV/policyagent-setup

FLAVOUR=`getFlavour`

#SELinux policy change update for RHEL
if [ $FLAVOUR == "rhel" ] ; then
    POLICYAGENT_CONFIG=$POLICYAGENT_HOME/configuration/

    /usr/bin/checkmodule -M -m -o $POLICYAGENT_CONFIG/policyagent.mod $POLICYAGENT_CONFIG/policyagent.te
    /usr/bin/semodule_package -o $POLICYAGENT_CONFIG/policyagent.pp -m $POLICYAGENT_CONFIG/policyagent.mod
    /usr/sbin/semodule -i $POLICYAGENT_CONFIG/policyagent.pp
    rm -f $POLICYAGENT_CONFIG/policyagent.mod $POLICYAGENT_CONFIG/policyagent.pp
fi

echo_success "policy agent installation complete"
