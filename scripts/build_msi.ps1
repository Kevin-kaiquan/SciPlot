$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DistApp = Join-Path $Root "dist\SciPlot"
$MsiRoot = Join-Path $Root "build\msi"
$Staging = Join-Path $MsiRoot "staging\SciPlot"
$WxsPath = Join-Path $MsiRoot "SciPlot.wxs"
$LicensePath = Join-Path $MsiRoot "License.rtf"
$OutputPath = Join-Path $Root "dist\SciPlot-Windows-x64.msi"
$VersionFile = Join-Path $Root "src\sciplot\version.py"
$VersionMatch = Select-String -Path $VersionFile -Pattern '^APP_VERSION\s*=\s*"([^"]+)"$'
if (-not $VersionMatch) {
    throw "Unable to read APP_VERSION from src\sciplot\version.py."
}
$ProductVersion = $VersionMatch.Matches[0].Groups[1].Value
$UpgradeCode = "AE751FD0-B9E6-410E-9F39-4A7BA2758F66"
$WixVersion = "5.0.2"
$env:DOTNET_CLI_HOME = Join-Path $Root "runtime\dotnet_home"
$env:NUGET_PACKAGES = Join-Path $Root "runtime\nuget"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = "1"
$env:DOTNET_NOLOGO = "1"
$env:TEMP = Join-Path $Root "runtime\temp"
$env:TMP = $env:TEMP
foreach ($directory in @($env:DOTNET_CLI_HOME, $env:NUGET_PACKAGES, $env:TEMP)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

if (-not (Test-Path (Join-Path $DistApp "SciPlot.exe"))) {
    throw "Missing packaged app. Run build_exe.ps1 before scripts\build_msi.ps1."
}

$resolvedRoot = [System.IO.Path]::GetFullPath($Root)
$resolvedMsiRoot = [System.IO.Path]::GetFullPath($MsiRoot)
if (-not $resolvedMsiRoot.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to prepare MSI outside the repository."
}

if (Test-Path $MsiRoot) {
    Remove-Item -LiteralPath $MsiRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $Staging | Out-Null
Copy-Item -Path (Join-Path $DistApp "*") -Destination $Staging -Recurse -Force
foreach ($name in @("exports", "runtime", "user_data")) {
    $path = Join-Path $Staging $name
    if (Test-Path $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}
foreach ($name in @("last_session.json", "last_session.tmp")) {
    $path = Join-Path $Staging $name
    if (Test-Path $path) {
        Remove-Item -LiteralPath $path -Force
    }
}
New-Item -ItemType File -Path (Join-Path $Staging "sciplot_installed.flag") -Force | Out-Null

function ConvertTo-WixLiteral([string]$value) {
    return [System.Security.SecurityElement]::Escape($value)
}

function New-WixId([string]$prefix, [string]$value) {
    $sha1 = [System.Security.Cryptography.SHA1]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($value.ToLowerInvariant())
    $hash = [System.BitConverter]::ToString($sha1.ComputeHash($bytes)).Replace("-", "")
    return "$prefix$($hash.Substring(0, 18))"
}

function New-StableGuid([string]$value) {
    $sha1 = [System.Security.Cryptography.SHA1]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes(("SciPlot|" + $value).ToLowerInvariant())
    $hash = $sha1.ComputeHash($bytes)
    $guidBytes = New-Object byte[] 16
    [Array]::Copy($hash, $guidBytes, 16)
    return (New-Object System.Guid -ArgumentList (, $guidBytes)).ToString().ToUpperInvariant()
}

function Get-RelativePathCompat([string]$basePath, [string]$targetPath) {
    $baseFull = [System.IO.Path]::GetFullPath($basePath).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $targetFull = [System.IO.Path]::GetFullPath($targetPath)
    $baseUri = New-Object System.Uri(($baseFull + [System.IO.Path]::DirectorySeparatorChar))
    $targetUri = New-Object System.Uri($targetFull)
    return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($targetUri).ToString()).Replace("/", [System.IO.Path]::DirectorySeparatorChar)
}

function Assert-NativeCommand([string]$description) {
    if ($LASTEXITCODE -ne 0) {
        throw "$description failed with exit code $LASTEXITCODE."
    }
}

$componentIds = New-Object System.Collections.Generic.List[string]
$directoryIds = @{}
$directoryIds[$Staging] = "INSTALLFOLDER"

function Write-WixDirectory([System.IO.DirectoryInfo]$directory, [int]$indent) {
    $pad = " " * $indent
    $lines = New-Object System.Collections.Generic.List[string]

    foreach ($file in Get-ChildItem -LiteralPath $directory.FullName -File | Sort-Object Name) {
        $relative = Get-RelativePathCompat $Staging $file.FullName
        $componentId = New-WixId "Cmp" $relative
        $fileId = New-WixId "Fil" $relative
        $componentGuid = New-StableGuid $relative
        $componentIds.Add($componentId)
        $source = ConvertTo-WixLiteral $file.FullName
        $lines.Add("$pad  <Component Id=`"$componentId`" Guid=`"{$componentGuid}`">")
        $lines.Add("$pad    <File Id=`"$fileId`" Source=`"$source`" KeyPath=`"yes`" />")
        $lines.Add("$pad  </Component>")
    }

    foreach ($child in Get-ChildItem -LiteralPath $directory.FullName -Directory | Sort-Object Name) {
        $relative = Get-RelativePathCompat $Staging $child.FullName
        $directoryId = New-WixId "Dir" $relative
        $name = ConvertTo-WixLiteral $child.Name
        $lines.Add("$pad  <Directory Id=`"$directoryId`" Name=`"$name`">")
        foreach ($childLine in Write-WixDirectory $child ($indent + 4)) {
            $lines.Add($childLine)
        }
        $lines.Add("$pad  </Directory>")
    }

    return $lines
}

$installFolderContent = Write-WixDirectory (Get-Item $Staging) 12
$componentRefs = New-Object System.Collections.Generic.List[string]
foreach ($componentId in $componentIds) {
    $componentRefs.Add("      <ComponentRef Id=`"$componentId`" />")
}
$componentRefs.Add("      <ComponentRef Id=`"StartMenuShortcut`" />")
$componentRefs.Add("      <ComponentRef Id=`"DesktopShortcut`" />")

$wxs = New-Object System.Collections.Generic.List[string]
$wxs.Add("<?xml version=`"1.0`" encoding=`"UTF-8`"?>")
$wxs.Add("<Wix xmlns=`"http://wixtoolset.org/schemas/v4/wxs`" xmlns:ui=`"http://wixtoolset.org/schemas/v4/wxs/ui`">")
$wxs.Add("  <Package Name=`"SciPlot`" Manufacturer=`"SciPlot`" Version=`"$ProductVersion`" UpgradeCode=`"{$UpgradeCode}`" Scope=`"perMachine`">")
$wxs.Add("    <MajorUpgrade DowngradeErrorMessage=`"A newer version of SciPlot is already installed.`" />")
$wxs.Add("    <MediaTemplate EmbedCab=`"yes`" />")
$iconSource = ConvertTo-WixLiteral (Join-Path $Root "logo\SciPlot.ico")
$wxs.Add("    <Icon Id=`"SciPlotIcon`" SourceFile=`"$iconSource`" />")
$wxs.Add("    <Property Id=`"ARPPRODUCTICON`" Value=`"SciPlotIcon`" />")
$wxs.Add("    <Property Id=`"ARPURLINFOABOUT`" Value=`"https://github.com/Kevin-kaiquan/SciPlot`" />")
$wxs.Add("    <ui:WixUI Id=`"WixUI_InstallDir`" InstallDirectory=`"INSTALLFOLDER`" />")
$wxs.Add("    <WixVariable Id=`"WixUILicenseRtf`" Value=`"$([System.Security.SecurityElement]::Escape($LicensePath))`" />")
$wxs.Add("    <StandardDirectory Id=`"ProgramFiles64Folder`">")
$wxs.Add("      <Directory Id=`"INSTALLFOLDER`" Name=`"SciPlot`">")
foreach ($line in $installFolderContent) {
    $wxs.Add($line)
}
$wxs.Add("      </Directory>")
$wxs.Add("    </StandardDirectory>")
$wxs.Add("    <StandardDirectory Id=`"ProgramMenuFolder`">")
$wxs.Add("      <Directory Id=`"ApplicationProgramsFolder`" Name=`"SciPlot`">")
$shortcutGuid = New-StableGuid "StartMenuShortcut"
$wxs.Add("        <Component Id=`"StartMenuShortcut`" Guid=`"{$shortcutGuid}`">")
$wxs.Add("          <Shortcut Id=`"ApplicationStartMenuShortcut`" Name=`"SciPlot`" Description=`"Create scientific plots`" Target=`"[INSTALLFOLDER]SciPlot.exe`" WorkingDirectory=`"INSTALLFOLDER`" />")
$wxs.Add("          <RemoveFolder Id=`"RemoveApplicationProgramsFolder`" On=`"uninstall`" />")
$wxs.Add("          <RegistryValue Root=`"HKLM`" Key=`"Software\SciPlot`" Name=`"installed`" Type=`"integer`" Value=`"1`" KeyPath=`"yes`" />")
$wxs.Add("        </Component>")
$wxs.Add("      </Directory>")
$wxs.Add("    </StandardDirectory>")
$wxs.Add("    <StandardDirectory Id=`"DesktopFolder`">")
$desktopGuid = New-StableGuid "DesktopShortcut"
$wxs.Add("      <Component Id=`"DesktopShortcut`" Guid=`"{$desktopGuid}`">")
$wxs.Add("        <Shortcut Id=`"ApplicationDesktopShortcut`" Name=`"SciPlot`" Description=`"Create scientific plots`" Target=`"[INSTALLFOLDER]SciPlot.exe`" WorkingDirectory=`"INSTALLFOLDER`" />")
$wxs.Add("        <RegistryValue Root=`"HKLM`" Key=`"Software\SciPlot`" Name=`"desktopShortcut`" Type=`"integer`" Value=`"1`" KeyPath=`"yes`" />")
$wxs.Add("      </Component>")
$wxs.Add("    </StandardDirectory>")
$wxs.Add("    <Feature Id=`"MainFeature`" Title=`"SciPlot`" Level=`"1`">")
foreach ($line in $componentRefs) {
    $wxs.Add($line)
}
$wxs.Add("    </Feature>")
$wxs.Add("  </Package>")
$wxs.Add("</Wix>")

New-Item -ItemType Directory -Path $MsiRoot -Force | Out-Null
$licenseText = "{\rtf1\ansi\deff0{\fonttbl{\f0 Segoe UI;}}\f0\fs20 SciPlot is provided as a local scientific plotting application.\par\par No license has been added to this repository yet. Add a license before broad public distribution.\par}"
$licenseText | Set-Content -Path $LicensePath -Encoding ASCII
$wxs | Set-Content -Path $WxsPath -Encoding UTF8

$LocalDotNet = Join-Path $Root ".dotnet\dotnet.exe"
if (Test-Path $LocalDotNet) {
    $DotNetExe = $LocalDotNet
} else {
    $DotNetCommand = Get-Command dotnet -ErrorAction SilentlyContinue
    if (-not $DotNetCommand) {
        throw "No .NET SDK is available. Install .NET 8 or place a local SDK in .dotnet."
    }
    $DotNetExe = $DotNetCommand.Source
}

$dotnetSdks = & $DotNetExe --list-sdks 2>$null
if ($LASTEXITCODE -ne 0 -or -not $dotnetSdks) {
    throw "No .NET SDK is available. Install .NET 8, place a local SDK in .dotnet, or build the MSI in GitHub Actions."
}

$ToolDir = Join-Path $MsiRoot "tools"
& $DotNetExe tool install wix --version $WixVersion --tool-path $ToolDir
Assert-NativeCommand "Installing WiX $WixVersion"
$WixExe = Join-Path $ToolDir "wix.exe"

& $WixExe extension add -g "WixToolset.UI.wixext/$WixVersion"
Assert-NativeCommand "Installing WiX UI extension"
& $WixExe extension list -g
Assert-NativeCommand "Listing WiX extensions"
& $WixExe build $WxsPath -arch x64 -ext WixToolset.UI.wixext -o $OutputPath
Assert-NativeCommand "Building MSI"
Write-Host "MSI build complete:" -ForegroundColor Green
Write-Host $OutputPath
