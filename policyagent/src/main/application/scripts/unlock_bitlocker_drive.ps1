$SecureString = Get-Content ..\configuration\bitlocker.key | ConvertTo-SecureString
$MountLocation = Get-Content ..\configuration\policyagent.properties | Select-String "MOUNT_LOCATION" | ForEach-Object {$_.line.split("=")[1]}
Unlock-BitLocker -MountPoint $MountLocation -Password $SecureString