#!/bin/bash
# workspace is typically "target" and must contain the files to package in the installer including the setup script
workspace="${1}"
projectVersion="${2}"
# installer name
projectNameVersion=`basename "${workspace}"`
# where to save the installer (parent of directory containing files)
targetDir=`dirname "${workspace}"`

#if [ -z "$workspace" ]; then
#  echo "Usage: $0 <workspace>"
#  echo "Example: $0 /path/to/AttestationService-0.5.1"
#  echo "The self-extracting installer AttestationService-0.5.1.bin would be created in /path/to"
#  exit 1
#fi

#if [ ! -d "$workspace" ]; then echo "Cannot find workspace '$workspace'"; exit 1; fi

# ensure all executable files in the target folder have the x bit set
#chmod +x $workspace/*.sh 

# check for the makeself tool
makezip=`which zip`
if [ -z "$makezip" ]; then
    echo "Missing zip tool"
    exit 1
fi

# unzip the trustagent-3.0-SNAPSHOT.zip since we are going to zip it again
policyagentZip="mtwilson-policyagent-zip-${projectVersion}.zip"
cd $targetDir/${projectNameVersion}
unzip ${policyagentZip}

# instead of making a zip file, we run makesis to generate the trustagent windows installer
MAKENSIS=`which makensis`
if [ -z "$MAKENSIS" ]; then
    echo "Missing makensis tool"
    exit 1
fi

cd $targetDir
$MAKENSIS "${projectNameVersion}/policyagentinstallscript.nsi"
mv "${projectNameVersion}/Installer.exe" "${projectNameVersion}.exe"

# This is not necessary, but to zip it
#$makezip -r "${projectNameVersion}.zip" "${projectNameVersion}"
