$log_file = "C:\Program Files (x86)\Intel\Policy Agent\logs\bitlockersetup.log"
If (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator"))
{    
  Echo "This script needs to be run As Admin" >> $log_file
  Break
} 

Echo "This script is runing As Admin" >> $log_file
#$SecureString = Get-Content "C:\Program Files (x86)\Intel\Policy Agent\configuration\bitlocker.key" | ConvertTo-SecureString
$SecureString = ConvertTo-SecureString ( Get-Content "C:\Program Files (x86)\Intel\Policy Agent\configuration\bitlocker.key" ) -AsPlainText -Force
$MountLocation = Get-Content "C:\Program Files (x86)\Intel\Policy Agent\configuration\policyagent_nt.properties" | Select-String "MOUNT_LOCATION" | ForEach-Object {$_.line.split("=")[1]}
If($?)
{
	echo "success get content of properties" >> $log_file
}
else
{
    echo "failed get content of properties" >> $log_file
}
Unlock-BitLocker -MountPoint $MountLocation -Password $SecureString
