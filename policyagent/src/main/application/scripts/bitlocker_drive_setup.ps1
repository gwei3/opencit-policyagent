param(
[Parameter(Mandatory=$True)]
[string]$drive
)

echo "Setting up bitlocker drive on $drive"

$feature = Get-WindowsFeature -Name Bitlocker | fl Installed | findstr.exe Installed
$isInstalled = $feature.Split(':')[1].Trim()
If($isInstalled.equals("False"))
{
	echo "Bitlocker not installed!"
	echo "Please install Bitlocker and restart the machine with following command :"
	echo "Install-WindowsFeature Bitlocker -Restart"
	echo "Once done, re-run the policyagent installer"
	return "False"
}
Else
{
	echo "Bitlocker present. Proceeding with the setup."
}

$key_file = "C:\Program Files (x86)\Intel\Policy Agent\configuration\bitlocker.key"
Get-Random | ConvertTo-SecureString -AsPlainText -Force | ConvertFrom-SecureString | Out-File $key_file

$SecureString = Get-Content $key_file | ConvertTo-SecureString
Add-BitLockerKeyProtector -MountPoint $drive -Password $SecureString -PasswordProtector

manage-bde -on $drive
while(1)
{
	$status = Get-BitLockerVolume -MountPoint $drive  | fl EncryptionPercentage | findstr.exe EncryptionPercentage
	$percentage = $status.Split(':')[1].Trim()
	if($percentage.equals('100'))
	{
		echo "Drive Encryption completed!"
		break;
	}
	Start-Sleep -s 2
}

return "True"