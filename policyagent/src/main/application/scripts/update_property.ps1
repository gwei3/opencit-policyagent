param(
[Parameter(Mandatory=$True)]
[string]$property_file,
[string]$property,
[string]$value
)

(Get-Content $property_file) | ForEach-Object { if($_ -match ($property)) {$_ -Replace ($property.ToString() + "=.*"), ($property.ToString() + "=" + $value.ToString())} else {$_} } | Set-Content $property_file
