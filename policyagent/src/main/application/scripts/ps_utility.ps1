param(
[Parameter(Mandatory=$True)]
[string]$task,
[string]$drive
)

function Get-ReclaimableBytes
{
	$output=(DISKPART /s diskpartscript.txt) | findstr reclaimable
	$output.split('(')[1].split(' ')[0].trim()
}

function Get-DiskNumber
{
	Param ([string]$drive)
	$output = Get-Partition -DriveLetter $drive | fl DiskNumber | findstr DiskNumber
	$output.Split(':')[1].trim()
}

function Create-Partition
{
	DISKPART /s diskpartscript.txt
}

function Check-DriveExist
{
	Param ([string]$driveLetter)
	Test-Path $driveLetter":"
}

function Check-PartitionCount
{
	$output=(DISKPART /s diskpartscript.txt) | findstr Primary | measure-object | findstr Count
	$output.split(':')[1].trim()
}

switch ($task) 
{
	"getFreeSpace" {Get-ReclaimableBytes}
	"getDiskNumber" {Get-DiskNumber -drive $drive}
	"createFinalPartition" {Create-Partition}
	"isDriveExist" {Check-DriveExist -driveLetter $drive}
	"getPartitionCount" {Check-PartitionCount}
	default { echo "Wrong choice" }
}
