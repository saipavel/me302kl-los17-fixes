<#
  me302kl-los17-fix.ps1
  Исправления для ASUS MeMO Pad FHD 10 LTE (ME302KL, duma) на LineageOS 17.1 (DYo1, 20230306).
  Написан ИИ-ассистентом Claude (Anthropic). Проверялся на одном планшете. Используйте на свой риск.

  Что делает:
    1. Bluetooth: отключает профиль Headset/HFP (bluetooth_disabled_profiles |= 2), из-за которого
       Bluetooth падает при каждой загрузке. Музыка в наушники (A2DP) не затрагивается.
    2. WebView: если из Play Маркета установлен "Android System WebView", делает его активным;
       если нет, открывает его страницу в Play Маркете.
    3. В TWRP: бэкап EFS/IMEI-разделов на ПК (с проверкой MD5).
    4. В TWRP: e2fsck раздела system (старые ошибки EXT4 с 2023 года).
    5. В TWRP: скрывает защищённый видеодекодер OMX.qcom.video.decoder.avc.secure в media_codecs.xml
       (104 ошибки vidc при каждой загрузке). Оригинал файла сохраняется на ПК.

  Запуск (планшет загружен в Android с включённой отладкой USB, либо уже в TWRP):
    powershell -ExecutionPolicy Bypass -File .\me302kl-los17-fix.ps1
  Параметры:
    -CheckOnly  только проверка, ничего не меняется
    -Undo       откат: возвращает Bluetooth и декодер как было
    -SkipEfs    не делать бэкап EFS
    -SkipFsck   не запускать e2fsck
  Нужен adb (platform-tools) в PATH или рядом со скриптом.
#>
param([switch]$CheckOnly, [switch]$Undo, [switch]$SkipEfs, [switch]$SkipFsck)

$Marker  = 'ME302KL-FIX'
$CodecRe = '(?s)[ \t]*<MediaCodec\s+name="OMX\.qcom\.video\.decoder\.avc\.secure".*?</MediaCodec>'
$ByName  = '/dev/block/platform/msm_sdcc.1/by-name'
$EfsParts = 'fsg','m9kefs1','m9kefs2','m9kefs3','m9kefsc','modemst1','modemst2','persist','misc'

# ---------- media_codecs.xml (чистые функции, без adb) ----------
function Get-SecureDecoderState([string]$Xml) {
    $m = [regex]::Match($Xml, $CodecRe)
    if (-not $m.Success) { return 'absent' }
    $before = $Xml.Substring(0, $m.Index)
    if ($before.LastIndexOf('<!--') -gt $before.LastIndexOf('-->')) { return 'disabled' }
    return 'active'
}

function Test-XmlOk([string]$Xml) { try { [void][xml]$Xml; return $true } catch { return $false } }

function Disable-SecureDecoder([string]$Xml) {
    $m = [regex]::Match($Xml, $CodecRe)
    if (-not $m.Success) { throw 'Блок декодера не найден' }
    if ($m.Value.Contains('--')) { throw 'В блоке есть "--", закомментировать безопасно нельзя' }
    $nl = if ($Xml.Contains("`r`n")) { "`r`n" } else { "`n" }
    $new = $Xml.Substring(0, $m.Index) +
           "        <!-- ${Marker}: secure decoder disabled (vidc secure firmware fails TrustZone auth, no Widevine L1)$nl" +
           $m.Value + "$nl        $Marker -->" +
           $Xml.Substring($m.Index + $m.Length)
    if ((Test-XmlOk $Xml) -and -not (Test-XmlOk $new)) { throw 'После правки XML не разбирается, отмена' }
    return $new
}

function Enable-SecureDecoder([string]$Xml) {
    $re = '(?s)[ \t]*<!-- ' + $Marker + ':[^\n]*\n(.*?)\r?\n[ \t]*' + $Marker + ' -->'
    $m = [regex]::Match($Xml, $re)
    if (-not $m.Success) { return $null }
    return $Xml.Substring(0, $m.Index) + $m.Groups[1].Value + $Xml.Substring($m.Index + $m.Length)
}

# ---------- adb ----------
function Find-Adb {
    foreach ($p in @("$PSScriptRoot\adb.exe", "$PSScriptRoot\platform-tools\adb.exe")) { if (Test-Path $p) { return $p } }
    $c = Get-Command adb -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    return $null
}
function Sh([string]$Cmd) { (& $script:Adb shell $Cmd 2>$null) | ForEach-Object { "$_".TrimEnd("`r") } }
function Get-State { "$(& $script:Adb get-state 2>$null)".Trim() }
function Wait-State([string]$Want, [int]$Timeout = 240) {
    $t0 = Get-Date
    while (((Get-Date) - $t0).TotalSeconds -lt $Timeout) {
        if ((Get-State) -eq $Want) { return $true }
        Start-Sleep 3
    }
    return $false
}
function Wait-Boot([int]$Timeout = 400) {
    if (-not (Wait-State 'device' $Timeout)) { return $false }
    $t0 = Get-Date
    while (((Get-Date) - $t0).TotalSeconds -lt $Timeout) {
        if ((Sh 'getprop sys.boot_completed') -eq '1') { return $true }
        Start-Sleep 3
    }
    return $false
}
function Say([string]$Text, [string]$Color = 'Gray') { Write-Host $Text -ForegroundColor $Color }
function Stop-Script([string]$Text) { Say "ОШИБКА: $Text" Red; try { Stop-Transcript | Out-Null } catch {}; exit 1 }

# ---------- Этап в Android ----------
function Invoke-AndroidStage {
    Say "`n== Android: Bluetooth и WebView" Cyan
    $bt = Sh 'settings get global bluetooth_disabled_profiles'
    $btVal = 0; if ($bt -match '^\d+$') { $btVal = [int]$bt }
    if ($CheckOnly) {
        Say ("Bluetooth HFP: " + $(if ($btVal -band 2) { 'отключён (исправлено)' } else { 'включён (не исправлено)' }))
    } elseif ($Undo) {
        $old = Get-ChildItem -Path $PSScriptRoot -Directory -Filter 'me302kl-backup-*' -ErrorAction SilentlyContinue |
               Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName 'bt_old.txt' } |
               Where-Object { Test-Path $_ } | Select-Object -First 1
        $restore = if ($old) { (Get-Content $old -Raw).Trim() } else { 'null' }
        if ($restore -eq 'null' -or $restore -eq '') { Sh 'settings delete global bluetooth_disabled_profiles' | Out-Null }
        else { Sh "settings put global bluetooth_disabled_profiles $restore" | Out-Null }
        Say "Bluetooth: значение возвращено ($restore)" Green
    } elseif ($btVal -band 2) {
        Say 'Bluetooth HFP уже отключён' Green
    } else {
        Set-Content -Path (Join-Path $script:Bak 'bt_old.txt') -Value $bt
        Sh "settings put global bluetooth_disabled_profiles $($btVal -bor 2)" | Out-Null
        Say 'Bluetooth HFP отключён (подействует после перезагрузки)' Green
    }

    $wvInstalled = (Sh 'pm path com.google.android.webview') -match '^package:'
    # webview_provider = null, пока используется вариант по умолчанию, поэтому активный берём из dumpsys
    $wvLine = (Sh 'dumpsys webviewupdate') | Where-Object { $_ -match 'Current WebView package' } | Select-Object -First 1
    $wvCur = if ($wvLine -match '\):\s*\(([\w\.]+),\s*([^\)]+)\)') { $Matches[1] } else { '' }
    $wvCurVer = if ($wvCur) { $Matches[2] } else { '' }
    Say ("WebView сейчас: " + $(if ($wvCur) { "$wvCur $wvCurVer" } else { 'не определён' }))
    if (-not $CheckOnly -and -not $Undo) {
        if ($wvInstalled -and $wvCur -ne 'com.google.android.webview') {
            Sh 'cmd webviewupdate set-webview-implementation com.google.android.webview' | Out-Null
            Say 'Активный WebView: com.google.android.webview' Green
        } elseif (-not $wvInstalled) {
            Say 'Android System WebView не установлен. Открываю Play Маркет: установите и запустите скрипт ещё раз.' Yellow
            Sh 'am start -a android.intent.action.VIEW -d market://details?id=com.google.android.webview -p com.android.vending' | Out-Null
        }
    }
}

# ---------- Этап в TWRP ----------
function Invoke-RecoveryStage {
    Say "`n== TWRP" Cyan
    if (-not (Sh 'command -v twrp')) { Stop-Script 'Похоже, это не TWRP. Нужен TWRP recovery.' }
    $sys = (Sh "readlink -f $ByName/system") | Select-Object -First 1
    if (-not $sys -or -not ((Sh "test -b $sys && echo ok") -eq 'ok')) { Stop-Script "Не найден раздел system в $ByName" }
    Say "Раздел system: $sys"

    if (-not $CheckOnly -and -not $Undo -and -not $SkipEfs) {
        Say 'Бэкап EFS/IMEI...'
        $efsDir = Join-Path $script:Bak 'efs'; New-Item -ItemType Directory -Force $efsDir | Out-Null
        foreach ($p in $EfsParts) {
            if ((Sh "test -e $ByName/$p && echo ok") -ne 'ok') { Say "  $p - нет такого раздела, пропуск" DarkGray; continue }
            Sh "dd if=$ByName/$p of=/tmp/efs_$p.img" | Out-Null
            $md5dev = ((Sh "md5sum /tmp/efs_$p.img") -split '\s+')[0]
            & $script:Adb pull "/tmp/efs_$p.img" (Join-Path $efsDir "$p.img") 2>$null | Out-Null
            Sh "rm -f /tmp/efs_$p.img" | Out-Null
            $md5pc = (Get-FileHash (Join-Path $efsDir "$p.img") -Algorithm MD5).Hash.ToLower()
            if ($md5pc -ne $md5dev) { Stop-Script "MD5 не совпал для $p" }
            Add-Content (Join-Path $efsDir 'efs.md5') "$md5pc  $p.img"
            Say "  $p OK" Green
        }
        Say "  Сохранено в $efsDir. Не выкладывайте эти файлы: в них IMEI." Yellow
    }

    # system должен быть отмонтирован для e2fsck
    Sh "umount $sys; umount /system_root; umount /system; umount /mnt/sys" | Out-Null
    if ((Sh "grep -c '^$sys ' /proc/mounts") -ne '0') { Stop-Script 'Не удалось отмонтировать system' }

    if (-not $SkipFsck -and -not $Undo) {
        $mode = if ($CheckOnly) { '-n' } else { '-y' }
        Say "e2fsck -f $mode $sys ..."
        $out = Sh "e2fsck -f $mode $sys; echo EXIT=`$?"
        $exitLine = $out | Where-Object { $_ -match '^EXIT=\d+$' } | Select-Object -Last 1
        if (-not $exitLine) { Stop-Script 'e2fsck не вернул код завершения' }
        $code = [int]($exitLine -replace 'EXIT=', '')
        $out | Where-Object { $_ -notmatch '^EXIT=' -and $_.Trim() } | Select-Object -Last 4 | ForEach-Object { Say "  $_" DarkGray }
        switch ($code) {
            0 { Say 'Файловая система чистая' Green }
            { $_ -in 1, 2 } { Say 'Ошибки исправлены' Green }
            default {
                if ($CheckOnly -and $code -eq 4) { Say 'Найдены ошибки (запустите без -CheckOnly, чтобы исправить)' Yellow }
                else { Stop-Script "e2fsck вернул код $code, дальше не продолжаю" }
            }
        }
    }

    $opt = if ($CheckOnly) { 'ro' } else { 'rw' }
    Sh "mkdir -p /mnt/sys; mount -t ext4 -o $opt $sys /mnt/sys" | Out-Null
    $target = $null
    foreach ($t in '/mnt/sys/system/vendor/etc/media_codecs.xml', '/mnt/sys/vendor/etc/media_codecs.xml') {
        if ((Sh "test -f $t && echo ok") -eq 'ok') { $target = $t; break }
    }
    if (-not $target) { Sh 'umount /mnt/sys' | Out-Null; Stop-Script 'media_codecs.xml не найден' }

    $cur = Join-Path $script:Bak 'media_codecs.current.xml'
    & $script:Adb pull $target $cur 2>$null | Out-Null
    $xml = [IO.File]::ReadAllText($cur)
    $state = Get-SecureDecoderState $xml
    Say "Защищённый декодер: $state"

    $new = $null
    if ($Undo) {
        $new = Enable-SecureDecoder $xml
        if (-not $new) { Say 'Метка скрипта не найдена: декодер не отключался этим скриптом. Если нужно, восстановите media_codecs.orig.xml вручную.' Yellow }
    } elseif (-not $CheckOnly -and $state -eq 'active') {
        Copy-Item $cur (Join-Path $script:Bak 'media_codecs.orig.xml')
        $new = Disable-SecureDecoder $xml
    }

    if ($new) {
        $nf = Join-Path $script:Bak 'media_codecs.new.xml'
        [IO.File]::WriteAllText($nf, $new, (New-Object Text.UTF8Encoding $false))
        & $script:Adb push $nf /tmp/media_codecs.new.xml 2>$null | Out-Null
        # cat, а не cp/mv: сохраняются владелец и SELinux-контекст файла
        Sh "cat /tmp/media_codecs.new.xml > $target; sync" | Out-Null
        $md5dev = ((Sh "md5sum $target") -split '\s+')[0]
        $md5pc  = (Get-FileHash $nf -Algorithm MD5).Hash.ToLower()
        if ($md5dev -ne $md5pc) { Sh 'umount /mnt/sys' | Out-Null; Stop-Script 'Файл записался неверно. Оригинал: media_codecs.orig.xml' }
        Say $(if ($Undo) { 'Декодер возвращён' } else { 'Декодер скрыт' }) Green
    }
    Sh 'umount /mnt/sys' | Out-Null
}

# ---------- Основной сценарий ----------
if ($MyInvocation.InvocationName -eq '.') { return }   # при dot-source только загрузить функции

$script:Adb = Find-Adb
if (-not $script:Adb) { Write-Host 'adb не найден. Положите platform-tools рядом со скриптом или добавьте в PATH.' -ForegroundColor Red; exit 1 }
$script:Bak = Join-Path $PSScriptRoot ('me302kl-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force $script:Bak | Out-Null
try { Start-Transcript -Path (Join-Path $script:Bak 'log.txt') | Out-Null } catch {}

$devs = @(& $script:Adb devices 2>$null | Select-Object -Skip 1 | Where-Object { $_ -match '\t(device|recovery)$' })
if ($devs.Count -ne 1) { Stop-Script "Нужно ровно одно устройство в adb (найдено: $($devs.Count))" }
$state = Get-State
$prod = Sh 'getprop ro.product.device'
if ($prod -notmatch 'duma') { Stop-Script "Это не ME302KL/duma (ro.product.device=$prod)" }

$modeText = if ($CheckOnly) { 'ТОЛЬКО ПРОВЕРКА' } elseif ($Undo) { 'ОТКАТ' } else { 'ИСПРАВЛЕНИЕ' }
Say "ME302KL найден ($state). Режим: $modeText. Папка для бэкапов и лога: $script:Bak" Cyan
if ($state -eq 'device') {
    $los = Sh 'getprop ro.lineage.version'
    Say "LineageOS: $los"
    if ($los -notmatch '^17\.1') { Say 'Скрипт рассчитан на LineageOS 17.1.' Yellow }
}
if (-not $CheckOnly) {
    Say 'Планшет перезагрузится в TWRP и обратно. Перед этим лучше сделать полный бэкап в TWRP.' Yellow
    if ((Read-Host 'Продолжить? (y/n)') -ne 'y') { Stop-Script 'Отменено пользователем' }
}

if ($state -eq 'device') {
    Invoke-AndroidStage
    Say "`nПерезагрузка в TWRP..."
    & $script:Adb reboot recovery
    if (-not (Wait-State 'recovery' 240)) { Stop-Script 'TWRP не появился в adb за 4 минуты' }
    Invoke-RecoveryStage
    Say "`nПерезагрузка в Android..."
    & $script:Adb reboot
    if (-not (Wait-Boot)) { Stop-Script 'Android не загрузился за отведённое время (проверьте планшет)' }
} elseif ($state -eq 'recovery') {
    Invoke-RecoveryStage
    Say "`nПерезагрузка в Android..."
    & $script:Adb reboot
    if (-not (Wait-Boot)) { Stop-Script 'Android не загрузился (проверьте, включена ли отладка USB)' }
    Invoke-AndroidStage
} else { Stop-Script "Неизвестное состояние adb: $state" }

Say "`nГотово. Бэкапы и лог: $script:Bak" Green
if (-not $CheckOnly -and -not $Undo) { Say 'Откат: запустите скрипт с параметром -Undo.' }
try { Stop-Transcript | Out-Null } catch {}
