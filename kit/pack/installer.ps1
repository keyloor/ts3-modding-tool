<#
  @@NAME@@ for Toy Story 3 - installer and uninstaller
  ----------------------------------------------------------------------------------------------------------------
  "Install @@NAME@@.bat" and "Uninstall @@NAME@@.bat" only start this script (plain Windows PowerShell),
  so every step it takes is written below.

  It changes only the game archive listed in patches\manifest.txt (@@ARCHIVE@@), plus a
  "@@NAME@@ backup" folder it makes in the game folder. Nothing outside the game folder, no downloads,
  no Windows settings. Log: %TEMP%\@@NAME@@ Setup.log

  Made with TS3 Modding Tool by keyloor.

  It doesn't swap whole archives: it puts the mod's files into each archive as it is now and leaves every other file
  in it alone, so it also works on a game that has other mods.

  Install
    1. Find the game folder (through Steam, or ask).
    2. For each archive, build the new one next to it (<archive>.kit_new) and read it back to check it. Nothing in
       the game has changed yet: if any archive can't take the mod, it stops here.
    3. Copy each archive into the backup folder, then put the new one in its place. If anything fails, every
       archive already changed is put back.
  Uninstall
    An archive still as the install left it gets its backup back. One changed since (another mod, a game update,
    Steam's file check) only has the mod's files taken out of it. Then the backup folder is deleted.
#>
param(
    [ValidateSet('install', 'uninstall')] [string]$Action = 'install',
    [string]$Game = '',          # the game folder; found through Steam when left out
    [switch]$Yes                 # don't ask (for testing)
)
$ErrorActionPreference = 'Stop'
$Name = '@@NAME@@'
$Version = '@@VERSION@@'
$BackupName = "$Name backup"
$GameExe = 'Toy Story 3 Complete Edition'
$Marker = '@@MARKER@@'
$Patches = Join-Path $PSScriptRoot 'patches'
$LogFile = Join-Path $env:TEMP "$Name Setup.log"
$Latin1 = [System.Text.Encoding]::GetEncoding(28591)
$Md5 = [System.Security.Cryptography.MD5]::Create()

function Log([string]$t) { try { Add-Content -LiteralPath $LogFile -Value ((Get-Date -Format 'HH:mm:ss ') + $t) } catch { } }
function Say([string]$t) { Write-Host $t; Log $t }
function HexOf([byte[]]$b) { return ([BitConverter]::ToString($b) -replace '-', '').ToLowerInvariant() }
function Md5Bytes([byte[]]$b) { return HexOf ($Md5.ComputeHash($b)) }
function Md5File([string]$p) { return (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLowerInvariant() }
function FromHex([string]$h) {
    $b = New-Object byte[] ($h.Length / 2)
    for ($i = 0; $i -lt $b.Length; $i++) { $b[$i] = [Convert]::ToByte($h.Substring(2 * $i, 2), 16) }
    return ,$b
}
function LivePath([string]$game, [string]$rel) { return Join-Path $game ($rel -replace '/', '\') }
function BakPath([string]$game, [string]$rel) { return Join-Path (Join-Path $game $BackupName) ($rel -replace '/', '\') }
function Denied($err) {
    $e = $err.Exception
    while ($e) { if ($e -is [System.UnauthorizedAccessException]) { return $true }; $e = $e.InnerException }
    return $false
}
function Put-File([string]$from, [string]$to) {
    # through a temporary name, so a half-written game file never stays behind
    $tmp = "$to.kit_tmp"
    [System.IO.File]::Copy($from, $tmp, $true)
    if (Test-Path -LiteralPath $to) { [System.IO.File]::SetAttributes($to, 'Normal') }
    [System.IO.File]::Copy($tmp, $to, $true)
    [System.IO.File]::Delete($tmp)
}

# ------------------------------------------------------------------------------------------------------------ zips
# The game's archives: end record + directory at the front, the files, directory + end record at the back; each
# directory entry has an extra field 'KF' = "MD5" + the MD5 of the unpacked file.
function Read-Zip([byte[]]$d) {
    $e = $d.Length - 22
    $stop = [Math]::Max(0, $d.Length - 65557)
    while ($e -ge $stop -and [BitConverter]::ToUInt32($d, $e) -ne 0x06054B50) { $e-- }
    if ($e -lt $stop) { throw 'it is not a zip archive' }
    $n = [BitConverter]::ToUInt16($d, $e + 10)
    $p = [int64][BitConverter]::ToUInt32($d, $e + 16)
    if (($p + 4 -gt $d.Length -or [BitConverter]::ToUInt32($d, $p) -ne 0x02014B50) -and [BitConverter]::ToUInt32($d, 0) -eq 0x06054B50) { $p = 22 }
    $list = New-Object System.Collections.ArrayList
    for ($i = 0; $i -lt $n; $i++) {
        if ($p + 46 -gt $d.Length -or [BitConverter]::ToUInt32($d, $p) -ne 0x02014B50) { throw 'its directory is damaged' }
        $method = [BitConverter]::ToUInt16($d, $p + 10)
        $cs = [int64][BitConverter]::ToUInt32($d, $p + 20)
        $us = [int64][BitConverter]::ToUInt32($d, $p + 24)
        $nl = [BitConverter]::ToUInt16($d, $p + 28); $xl = [BitConverter]::ToUInt16($d, $p + 30); $cl = [BitConverter]::ToUInt16($d, $p + 32)
        $lho = [int64][BitConverter]::ToUInt32($d, $p + 42)
        $name = New-Object byte[] $nl
        [Array]::Copy($d, $p + 46, $name, 0, $nl)
        $md5 = $null
        $q = $p + 46 + $nl; $xe = $q + $xl
        while ($q + 4 -le $xe) {
            $tag = [BitConverter]::ToUInt16($d, $q); $sz = [BitConverter]::ToUInt16($d, $q + 2)
            if ($tag -eq 0x464B -and $sz -eq 19 -and $d[$q + 4] -eq 77 -and $d[$q + 5] -eq 68 -and $d[$q + 6] -eq 53) {
                $md5 = New-Object byte[] 16; [Array]::Copy($d, $q + 7, $md5, 0, 16)
            }
            $q += 4 + $sz
        }
        if ($method -ne 0 -and $method -ne 8) { throw "a file in it uses compression $method" }
        if ([BitConverter]::ToUInt32($d, $lho) -ne 0x04034B50) { throw 'a file in it is damaged' }
        $data = $lho + 30 + [BitConverter]::ToUInt16($d, $lho + 26) + [BitConverter]::ToUInt16($d, $lho + 28)
        if ($data + $cs -gt $d.Length) { throw 'a file in it is cut off' }
        [void]$list.Add([pscustomobject]@{ Name = $name; Key = $Latin1.GetString($name).ToLowerInvariant(); Method = [int]$method
            Time = [int][BitConverter]::ToUInt16($d, $p + 12); Date = [int][BitConverter]::ToUInt16($d, $p + 14)
            Crc = [uint32][BitConverter]::ToUInt32($d, $p + 16); CSize = $cs; USize = $us; Md5 = $md5; Src = $d; At = $data })
        $p += 46 + $nl + $xl + $cl
    }
    return ,$list
}

function Get-Md5Of($z) {
    if ($null -ne $z.Md5) { return ,$z.Md5 }
    $raw = New-Object System.IO.MemoryStream($z.Src, [int]$z.At, [int]$z.CSize, $false)
    $out = New-Object System.IO.MemoryStream
    if ($z.Method -eq 8) {
        $inf = New-Object System.IO.Compression.DeflateStream($raw, [System.IO.Compression.CompressionMode]::Decompress)
        $inf.CopyTo($out); $inf.Dispose()
    } else { $raw.CopyTo($out) }
    return ,($Md5.ComputeHash($out.ToArray()))
}

function Write-Zip($ents) {
    $cdSize = 0
    foreach ($z in $ents) { $cdSize += 46 + $z.Name.Length + 23 }
    $bodyM = New-Object System.IO.MemoryStream; $cdM = New-Object System.IO.MemoryStream
    $body = New-Object System.IO.BinaryWriter($bodyM); $cd = New-Object System.IO.BinaryWriter($cdM)
    $kf = $Latin1.GetBytes('MD5')
    $pos = [int64](22 + $cdSize)
    foreach ($z in $ents) {
        $h = Get-Md5Of $z
        $body.Write([uint32]0x04034B50); $body.Write([uint16]20); $body.Write([uint16]0); $body.Write([uint16]$z.Method)
        $body.Write([uint16]$z.Time); $body.Write([uint16]$z.Date); $body.Write([uint32]$z.Crc)
        $body.Write([uint32]$z.CSize); $body.Write([uint32]$z.USize); $body.Write([uint16]$z.Name.Length); $body.Write([uint16]0)
        $body.Write($z.Name); $body.Write($z.Src, [int]$z.At, [int]$z.CSize)
        $cd.Write([uint32]0x02014B50); $cd.Write([uint16]20); $cd.Write([uint16]20); $cd.Write([uint16]0)
        $cd.Write([uint16]$z.Method); $cd.Write([uint16]$z.Time); $cd.Write([uint16]$z.Date); $cd.Write([uint32]$z.Crc)
        $cd.Write([uint32]$z.CSize); $cd.Write([uint32]$z.USize); $cd.Write([uint16]$z.Name.Length); $cd.Write([uint16]23)
        $cd.Write([uint16]0); $cd.Write([uint16]0); $cd.Write([uint16]0); $cd.Write([uint32]0); $cd.Write([uint32]$pos)
        $cd.Write($z.Name); $cd.Write([uint16]0x464B); $cd.Write([uint16]19); $cd.Write($kf); $cd.Write($h)
        $pos += 30 + $z.Name.Length + $z.CSize
    }
    $body.Flush(); $cd.Flush()
    $endM = New-Object System.IO.MemoryStream; $end = New-Object System.IO.BinaryWriter($endM)
    $end.Write([uint32]0x06054B50); $end.Write([uint16]0); $end.Write([uint16]0); $end.Write([uint16]$ents.Count)
    $end.Write([uint16]$ents.Count); $end.Write([uint32]$cdSize); $end.Write([uint32]$pos); $end.Write([uint16]0); $end.Flush()
    $out = New-Object System.IO.MemoryStream
    $endM.WriteTo($out); $cdM.WriteTo($out); $bodyM.WriteTo($out); $cdM.WriteTo($out); $endM.WriteTo($out)
    return ,($out.ToArray())
}

function Check-Zip([byte[]]$new, $planned) {
    $got = Read-Zip $new
    if ($got.Count -ne $planned.Count) { throw 'the new archive came out wrong (number of files)' }
    for ($k = 0; $k -lt $got.Count; $k++) {
        $a = $got[$k]; $b = $planned[$k]
        if ($a.Key -ne $b.Key -or $a.Crc -ne $b.Crc -or $a.CSize -ne $b.CSize -or
            (HexOf ($Md5.ComputeHash($a.Src, [int]$a.At, [int]$a.CSize))) -ne (HexOf ($Md5.ComputeHash($b.Src, [int]$b.At, [int]$b.CSize)))) {
            throw "the new archive came out wrong ($($b.Key))"
        }
    }
}

# ------------------------------------------------------------------------------------------------------------ parts
function Read-Manifest([string]$dir) {
    $l = @()
    foreach ($line in [System.IO.File]::ReadAllLines((Join-Path $dir 'manifest.txt'))) {
        if ($line.Trim() -eq '' -or $line.StartsWith('#')) { continue }
        $f = $line.Split('|')
        $l += [pscustomobject]@{ Path = $f[0]; Parts = $f[1]; Shipped = $f[2]; Result = $f[3] }
    }
    return ,$l
}

function Read-Parts([string]$dir, $m) {
    $bin = $null
    $bp = Join-Path $dir ($m.Parts + '.bin')
    if (Test-Path -LiteralPath $bp) { $bin = [System.IO.File]::ReadAllBytes($bp) }
    $parts = New-Object System.Collections.ArrayList
    foreach ($line in [System.IO.File]::ReadAllLines((Join-Path $dir ($m.Parts + '.txt')))) {
        if ($line.Trim() -eq '' -or $line.StartsWith('#')) { continue }
        $f = $line.Split('|')
        if ($f[0] -ne 'put') { throw "unknown line in $($m.Parts).txt" }
        [void]$parts.Add([pscustomobject]@{ Name = $Latin1.GetBytes($f[1]); Key = $f[1].ToLowerInvariant(); Src = $bin
            At = [int64]$f[2]; CSize = [int64]$f[3]; Method = [int]$f[4]; Time = [int]$f[5]; Date = [int]$f[6]
            Crc = [uint32]([Convert]::ToUInt32($f[7], 16)); USize = [int64]$f[8]; Md5 = (FromHex $f[9]) })
    }
    return ,$parts
}

function Merge-In([byte[]]$cur, $parts) {
    $ents = Read-Zip $cur
    $by = @{}; foreach ($p in $parts) { $by[$p.Key] = $p }
    $out = New-Object System.Collections.ArrayList; $used = @{}
    foreach ($e in $ents) {
        $p = $by[$e.Key]
        if ($null -eq $p) { [void]$out.Add($e); continue }
        $used[$e.Key] = $true
        $c = $p.PSObject.Copy(); $c.Name = $e.Name; [void]$out.Add($c)
    }
    foreach ($p in $parts) { if (-not $used.ContainsKey($p.Key)) { [void]$out.Add($p) } }
    $new = Write-Zip $out
    Check-Zip $new $out
    return ,$new
}

function Merge-Out([byte[]]$cur, [byte[]]$bak, $parts) {
    # each of the mod's files still in the archive goes back to the backed-up archive's version
    $ents = Read-Zip $cur
    $old = @{}; foreach ($b in (Read-Zip $bak)) { $old[$b.Key] = $b }
    $mine = @{}; foreach ($p in $parts) { $mine[$p.Key] = $p }
    $out = New-Object System.Collections.ArrayList; $taken = 0
    foreach ($e in $ents) {
        $p = $mine[$e.Key]
        if ($null -ne $p -and $e.Crc -eq $p.Crc -and $e.USize -eq $p.USize) {
            $taken++
            if ($old.ContainsKey($e.Key)) { [void]$out.Add($old[$e.Key]) }
        } else { [void]$out.Add($e) }
    }
    if ($taken -eq 0) { return $null }
    $new = Write-Zip $out
    Check-Zip $new $out
    return ,$new
}

# ------------------------------------------------------------------------------------------------------------ game
function Is-Game([string]$d) { return ($d -and (Test-Path -LiteralPath (Join-Path $d $Marker))) }

function Find-Game {
    $c = @()
    $d = $PSScriptRoot
    for ($i = 0; $i -lt 4 -and $d; $i++) { $c += $d; $d = Split-Path -Parent $d }
    $steam = $null
    try { $steam = (Get-ItemProperty -Path 'HKCU:\Software\Valve\Steam').SteamPath } catch { }
    if (-not $steam) { try { $steam = (Get-ItemProperty -Path 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam').InstallPath } catch { } }
    if ($steam) {
        $steam = $steam -replace '/', '\'
        $libs = @($steam)
        $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf) {
            foreach ($line in [System.IO.File]::ReadAllLines($vdf)) {
                if ($line -match '^\s*"path"\s*"(.+)"') { $libs += $Matches[1].Replace('\\', '\') }
            }
        }
        foreach ($l in $libs) { $c += Join-Path $l "steamapps\common\$GameExe" }
    }
    foreach ($x in $c) { if (Is-Game $x) { return (Resolve-Path -LiteralPath $x).Path.TrimEnd('\') } }
    return $null
}

function Ask-Game {
    Say "  Couldn't find Toy Story 3 Complete Edition through Steam."
    if ($Yes) { return $null }
    Say "  Pick the game's folder, the one with '$GameExe.exe' (Steam: right-click the game > Manage > Browse local files)."
    $chosen = $null
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
        $dlg.Description = "Pick the $GameExe folder"
        $dlg.ShowNewFolderButton = $false
        if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $chosen = $dlg.SelectedPath }
    } catch { Log "folder dialog: $($_.Exception.Message)" }
    if (-not $chosen) {
        $typed = Read-Host '  Or paste the folder path here (Enter to cancel)'
        if ($typed) { $chosen = $typed.Trim().Trim('"') }
    }
    if ($chosen -and (Is-Game $chosen)) { return (Resolve-Path -LiteralPath $chosen).Path.TrimEnd('\') }
    if ($chosen) { Say "  That isn't the game folder (no $Marker in it)." }
    return $null
}

function Wait-Closed {
    while (Get-Process -Name $GameExe -ErrorAction SilentlyContinue) {
        Say '  Toy Story 3 is running. Close the game, then press Enter (or type Q and Enter to quit).'
        if ($Yes) { return $false }
        if ((Read-Host ' ') -match '^\s*q') { return $false }
    }
    return $true
}

# ------------------------------------------------------------------------------------------------------------ install
function Install-Mod([string]$game, $manifest) {
    $backup = Join-Path $game $BackupName
    if (Test-Path -LiteralPath (Join-Path $backup 'installed.txt')) {
        Say "  $Name is already installed: taking that copy out first..."
        if (-not (Uninstall-Mod $game $false)) { return $false }
    }
    $missing = @($manifest | Where-Object { -not (Test-Path -LiteralPath (LivePath $game $_.Path)) })
    if ($missing.Count) { Say '  Game files are missing:'; $missing | ForEach-Object { Say "    $($_.Path)" }; Say '  Nothing was changed.'; return $false }
    # 1. build every new archive next to the game's own
    $plan = @()
    try {
        foreach ($m in $manifest) {
            $live = LivePath $game $m.Path
            Write-Host "  Preparing  $(Split-Path $live -Leaf)"
            $cur = [System.IO.File]::ReadAllBytes($live)
            $before = Md5Bytes $cur
            try { $new = Merge-In $cur (Read-Parts $Patches $m) } catch { throw "$($m.Path) can't take the mod: $($_.Exception.Message)" }
            $after = Md5Bytes $new
            if ($before -eq $m.Shipped -and $after -ne $m.Result) { throw "the new $($m.Path) didn't come out right (MD5 check)" }
            $tmp = "$live.kit_new"
            [System.IO.File]::WriteAllBytes($tmp, $new)
            if ((Md5File $tmp) -ne $after) { throw "the new $($m.Path) didn't get written correctly" }
            $plan += [pscustomobject]@{ M = $m; Live = $live; Tmp = $tmp; Before = $before; After = $after }
            Log "prepared $($m.Path) $before -> $after"
        }
    } catch {
        foreach ($m in $manifest) { Remove-Item -LiteralPath ((LivePath $game $m.Path) + '.kit_new') -Force -ErrorAction SilentlyContinue }
        Log ($_ | Out-String); Say "  $($_.Exception.Message)"
        if (Denied $_) { Say "  Windows refused to write to the game folder: right-click 'Install $Name.bat' > Run as administrator." }
        Say '  Nothing was changed.'
        return $false
    }
    $modded = @($plan | Where-Object { $_.Before -ne $_.M.Shipped })
    if ($modded.Count) {
        Say '  These archives were already changed (another mod or a game update); the characters go in, the rest stays:'
        $modded | ForEach-Object { Say "    $($_.M.Path)" }
    }
    # 2. back up each archive, then put the new one in its place
    New-Item -ItemType Directory -Force -Path $backup | Out-Null
    $done = @()
    try {
        foreach ($p in $plan) {
            Write-Host "  Installing $(Split-Path $p.Live -Leaf)"
            $bak = BakPath $game $p.M.Path
            New-Item -ItemType Directory -Force -Path (Split-Path $bak) | Out-Null
            [System.IO.File]::Copy($p.Live, $bak, $true)
            if ((Md5File $bak) -ne $p.Before) { throw "the backup of $($p.M.Path) doesn't match the game's file" }
            Put-File $p.Tmp $p.Live
            [System.IO.File]::Delete($p.Tmp)
            if ((Md5File $p.Live) -ne $p.After) { throw "$($p.M.Path) didn't get written correctly" }
            $done += $p
        }
        $lists = Join-Path $backup 'parts'
        New-Item -ItemType Directory -Force -Path $lists | Out-Null
        [System.IO.File]::Copy((Join-Path $Patches 'manifest.txt'), (Join-Path $lists 'manifest.txt'), $true)
        foreach ($p in $plan) { [System.IO.File]::Copy((Join-Path $Patches ($p.M.Parts + '.txt')), (Join-Path $lists ($p.M.Parts + '.txt')), $true) }
        $state = @("$Name|$Version") + @($plan | ForEach-Object { "$($_.M.Path)|$($_.Before)|$($_.After)" })
        [System.IO.File]::WriteAllLines((Join-Path $backup 'installed.txt'), [string[]]$state)
    } catch {
        Say "  Install failed: $($_.Exception.Message)"; Log ($_ | Out-String)
        $ok = $true
        foreach ($p in $done) { try { Put-File (BakPath $game $p.M.Path) $p.Live } catch { $ok = $false } }
        foreach ($p in $plan) { Remove-Item -LiteralPath $p.Tmp -Force -ErrorAction SilentlyContinue }
        if ($ok) { Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue; Say '  The game files were put back as they were.' }
        else { Say "  Some files couldn't be put back: they are in '$BackupName' in the game folder (Steam's 'Verify integrity of game files' also restores them)." }
        if (Denied $_) { Say "  Windows refused to write to the game folder: right-click 'Install $Name.bat' > Run as administrator." }
        return $false
    }
    Say ''
    Say ('  Done - @@WHAT@@ ' + "'Uninstall $Name.bat' puts the game back.")
    return $true
}

# ------------------------------------------------------------------------------------------------------------ uninstall
function Uninstall-Mod([string]$game, [bool]$alone) {
    $backup = Join-Path $game $BackupName
    $state = Join-Path $backup 'installed.txt'
    if (-not (Test-Path -LiteralPath $state)) { Say "  $Name is not installed - nothing to do."; return $true }
    $lists = Join-Path $backup 'parts'
    if (-not (Test-Path -LiteralPath (Join-Path $lists 'manifest.txt'))) { $lists = $Patches }
    $byPath = @{}; foreach ($m in (Read-Manifest $lists)) { $byPath[$m.Path] = $m }
    $problems = @()
    foreach ($row in ([System.IO.File]::ReadAllLines($state) | Select-Object -Skip 1)) {
        if ($row -notmatch '\|') { continue }
        $f = $row.Split('|'); $rel = $f[0]; $before = $f[1]; $after = $f[2]
        $live = LivePath $game $rel; $bak = BakPath $game $rel
        $now = ''; if (Test-Path -LiteralPath $live) { $now = Md5File $live }
        if ($now -eq $before) { continue }
        if (-not (Test-Path -LiteralPath $bak) -or (Md5File $bak) -ne $before) { $problems += "$rel (its backup is missing)"; continue }
        Write-Host "  Restoring $(Split-Path $live -Leaf)"
        if ($now -eq $after) {
            Put-File $bak $live
            if ((Md5File $live) -ne $before) { throw "couldn't put back $rel" }
            continue
        }
        # changed since the install: take only the mod's files out
        $m = $byPath[$rel]
        if (-not $now -or $null -eq $m) { Say "    $rel was changed since; left as it is"; continue }
        try { $new = Merge-Out ([System.IO.File]::ReadAllBytes($live)) ([System.IO.File]::ReadAllBytes($bak)) (Read-Parts $lists $m) }
        catch { $problems += "$rel (couldn't read it: $($_.Exception.Message))"; continue }
        if ($null -eq $new) { Say "    $rel no longer has the mod's files; left as it is"; continue }
        $tmp = "$live.kit_new"
        [System.IO.File]::WriteAllBytes($tmp, $new); Put-File $tmp $live; [System.IO.File]::Delete($tmp)
        Say "    $rel was changed since: the mod's files were taken out, the other changes kept"
    }
    if ($problems.Count) {
        Say "  These couldn't be put back:"; $problems | ForEach-Object { Say "    $_" }
        Say "  Steam's 'Verify integrity of game files' restores them. The backups stay in '$BackupName'."
        return $false
    }
    try { Remove-Item -LiteralPath $backup -Recurse -Force } catch { Remove-Item -LiteralPath $state -Force -ErrorAction SilentlyContinue }
    if ($alone) { Say ''; Say "  Done - $Name is uninstalled and the game's characters are back." }
    return $true
}

# ------------------------------------------------------------------------------------------------------------ main
$ok = $false
try {
    Log "==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Action $PSScriptRoot"
    $manifest = Read-Manifest $Patches
    Say ''
    Say "  $Name for Toy Story 3   (version $Version)"
    Say '  @@WHAT@@'
    Say ''
    if ($Game) {
        if (-not (Is-Game $Game)) { Say "  Not the game folder (no $Marker in it): $Game"; exit 1 }
        $dir = (Resolve-Path -LiteralPath $Game).Path.TrimEnd('\')
    } else { $dir = Find-Game }
    if (-not $dir) { $dir = Ask-Game }
    if (-not $dir) { Say '  No game folder - nothing was changed.'; exit 1 }
    Say "  Game folder: $dir"; Say ''
    if (-not $Yes) {
        $ans = Read-Host "  Press Enter to $Action $Name (or type N and Enter to cancel)"
        if ($ans -match '^\s*n') { Say '  Cancelled - nothing was changed.'; exit 1 }
    }
    if (-not (Wait-Closed)) { Say '  Nothing was changed.'; exit 1 }
    if ($Action -eq 'install') { $ok = Install-Mod $dir $manifest } else { $ok = Uninstall-Mod $dir $true }
} catch {
    Say ''; Say "  Something went wrong: $($_.Exception.Message)"; Log ($_ | Out-String); Say "  Details: $LogFile"
}
Log "exit ok=$ok"
if ($ok -eq $true) { exit 0 } else { exit 1 }
