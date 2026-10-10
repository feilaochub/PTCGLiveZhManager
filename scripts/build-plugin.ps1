# Requires PowerShell 7 with the bundled Roslyn compiler assemblies.
param(
 [Parameter(Mandatory=$true)][string]$GameManagedDir,
 [Parameter(Mandatory=$true)][string]$BepInExDir,
 [string]$OutputPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'work/dist/PTCGLiveZhMod.dll')
)
$ErrorActionPreference = 'Stop'
$managed = (Resolve-Path -LiteralPath $GameManagedDir).Path
$core = (Resolve-Path -LiteralPath $BepInExDir).Path
$repo = Split-Path $PSScriptRoot -Parent
Add-Type -Path (Join-Path $PSHOME 'Microsoft.CodeAnalysis.dll')
Add-Type -Path (Join-Path $PSHOME 'Microsoft.CodeAnalysis.CSharp.dll')
$trees = [System.Collections.Generic.List[Microsoft.CodeAnalysis.SyntaxTree]]::new()
foreach ($file in (Get-ChildItem (Join-Path $repo 'mod') -Recurse -Filter *.cs | Where-Object { $_.FullName -notmatch '[\\/](obj|bin)[\\/]' })) {
 $trees.Add([Microsoft.CodeAnalysis.CSharp.CSharpSyntaxTree]::ParseText([IO.File]::ReadAllText($file.FullName), $null, $file.FullName))
}
$version = ([xml](Get-Content (Join-Path $repo 'mod/PTCGLiveZhMod.csproj') -Raw)).Project.PropertyGroup.FileVersion
$metadata = '[assembly: System.Reflection.AssemblyVersion("{0}")] [assembly: System.Reflection.AssemblyFileVersion("{0}")] [assembly: System.Runtime.Versioning.TargetFramework(".NETStandard,Version=v2.1")]' -f $version
$trees.Add([Microsoft.CodeAnalysis.CSharp.CSharpSyntaxTree]::ParseText($metadata))
$refs = [System.Collections.Generic.List[Microsoft.CodeAnalysis.MetadataReference]]::new()
foreach ($name in @('mscorlib','System','System.Core','System.Data','netstandard','CardDatabase.DataAccess','SharedLogicUtils','TPCI.RainierClient','TPCIAssetBundleSystem','TPCIBuildtoolsRuntime','TPCICardShaders','TPCILocalization','Unity.TextMeshPro','UnityEngine','UnityEngine.AssetBundleModule','UnityEngine.CoreModule','UnityEngine.UI')) {
 $refs.Add([Microsoft.CodeAnalysis.MetadataReference]::CreateFromFile((Join-Path $managed "$name.dll")))
}
foreach ($name in @('BepInEx','0Harmony')) { $refs.Add([Microsoft.CodeAnalysis.MetadataReference]::CreateFromFile((Join-Path $core "$name.dll"))) }
$options = [Microsoft.CodeAnalysis.CSharp.CSharpCompilationOptions]::new([Microsoft.CodeAnalysis.OutputKind]::DynamicallyLinkedLibrary).WithOptimizationLevel([Microsoft.CodeAnalysis.OptimizationLevel]::Release).WithDeterministic($true)
$compilation = [Microsoft.CodeAnalysis.CSharp.CSharpCompilation]::Create('PTCGLiveZhMod', $trees, $refs, $options)
New-Item -ItemType Directory -Path (Split-Path $OutputPath -Parent) -Force | Out-Null
$stream = [IO.File]::Create($OutputPath)
try { $result = $compilation.Emit($stream) } finally { $stream.Dispose() }
$result.Diagnostics | Where-Object Severity -eq 'Error' | ForEach-Object { $_.ToString() }
$result.Diagnostics | Group-Object Id | ForEach-Object { Write-Output ("{0}: {1} compiler diagnostics" -f $_.Name, $_.Count) }
if (-not $result.Success) { throw 'Source compilation failed.' }
Write-Output "Compiled current C# sources successfully: $OutputPath"

$sourceHashes = @{}
foreach ($file in (Get-ChildItem (Join-Path $repo 'mod') -Recurse -File | Where-Object { $_.Extension -in @('.cs','.csproj') -and $_.FullName -notmatch '[\\/](obj|bin)[\\/]' })) {
 $relative = [IO.Path]::GetRelativePath($repo, $file.FullName).Replace('\','/')
 $sourceHashes[$relative] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
$buildRecord = @{version=$version; dll_sha256=(Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash.ToLowerInvariant(); sources_sha256=$sourceHashes; compiler='PowerShell 7 bundled Roslyn'; compiler_errors=0; runtime_verified_on_macos=$false}
$buildRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ($OutputPath+'.build.json') -Encoding utf8
