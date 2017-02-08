param(
[Parameter(Mandatory=$True)]
[string]$file,
[string]$property
)

$property = Get-Content $file | findstr.exe "MOUNT_LOCATION"
$value = $property.Split("=")[1]

manage-bde -off $value
