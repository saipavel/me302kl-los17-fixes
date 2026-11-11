# Применимость ремонтов к Android 13 ME302KL v1.0

Исследован фактический [release kout651 v1.0](https://github.com/kout651/android13-asus-me302kl/releases/tag/v1.0), опубликованный 31 октября 2026, и дерево commit `0d991739f582b1240fa65c7777ab9ea5af8173bb`. Загружены system.img, boot_a13_v9.img, duma_firmware_a13.zip, README и source/config references. Android 13 на планшет **не устанавливался**.

**Вывод: весь Android 10 комплект применять нельзя. Sensor daemon patch v2 применим к точному бинарному файлу; runtime результат на Android 13 ещё не проверен.** У общего installer есть явный отказ SDK 33/LineageOS 20.

System image — raw ext4, 1,336,934,400 bytes, SHA-256 `589c4ff8fbe0610d8e908578b491c9d6516e5f279a6e80e3425c3ca803e09253`. Его build.prop сообщает SDK 33 и `20.0-20230830-UNOFFICIAL-deb`. Kernel version из boot image — `3.4.113-lineageos-g47d2ae7d-dirty`, build 29 октября 2026. [Описание автора](https://github.com/kout651/android13-asus-me302kl/blob/0d991739f582b1240fa65c7777ab9ea5af8173bb/README.md) подтверждает базу Nexus 7 deb/flo, а не нашу Sweet LOS17.

| Ремонт | Что найдено в образе Android 13 | Применимость |
|---|---|---|
| Sensor crash + logmask v2 | `/vendor/bin/sensors.qcom` — **точно тот же** исходный файл, 220508 bytes, SHA `9c0382d044af946ce755feaa7938e1a48c6773edc2ef8a6396a6443634b55f9b` | Да, на уровне точной бинарной дельты. Offline transform дал ожидаемый v2 SHA. Нужен отдельный on-device test |
| Bluetooth HFP | Наш `/system/lib/libbluetooth.so` отсутствует; код Bluetooth находится в flattened APEX, `libbluetooth_jni.so` размером 10043128 bytes | Нет прямого переноса. Неработающий Bluetooth из release notes не доказывает прежний HFP bounds bug |
| GNSS NMEA ownership | Другой файл: `/vendor/lib/hw/android.hardware.gnss@1.0-impl.legacy.so`, 86720 bytes, другой SHA | Наша дельта не подходит. Найден похожий потенциально опасный вызов; нужен отдельный port/verification |
| Восстановление GPS HAL/utils | Уже присутствуют другие GPS HAL (19708 bytes) и utils (20040 bytes); автор сообщает рабочий GPS | Наши vendor libraries не подменять; совместимость ABI и modem lifecycle отдельно не доказана |
| GPS power + Wi-Fi-only | Другие vendor build.prop, legacy HAL и kernel/init base | Можно изучать идею, но adapter/config не переносить автоматически. Сотовое отключение — выбор владельца, не универсальный ремонт |
| Assistance/codec config | Другие gps_debug.conf и media_codecs.xml, оба с несовпадающими хешами | Не заменять целиком Android 10 версиями. XTRA настройки исследовать при реальной проблеме |
| Google configurator | Framework resource ID уже `0x01040253` вместо LOS17 `0x0104016b`, значение пустое; в проверенных priv-app каталогах нет GmsCore, есть SimpleDeviceConfig | Нет подтверждённой той же GMS ошибки. Старый APK не устанавливать; проверять реально установленный Google stack, grants и overlay policy |
| Thermal startup experiment | Другое ядро flo lineageos; этот кандидат не входит в рабочий комплект | Не применять Sweet patch к boot A13 без нового source audit |

## Sensor patch: наиболее обоснованный перенос

В образе Android 13 также совпали с нашим Android 10:

- `libdiag.so`: `0a4ef218e4263cd2a92d0a6633de50a055df989755a3ef942365bc2cb424ada3`.
- `libsensor1.so`: `277399a1606b856cfc022fdb840298eb1760941cca29c163aaceddc39fa7f7a5`.
- `dsps.mdt` и `dsps.b00` из release firmware ZIP совпадают с файлами на нашем планшете.

Sensor HAL `sensors.msm8960.so` при этом другой. Совпадение daemon, его диагностических dependencies и указанных DSP файлов — сильное основание для переноса этих двух исправлений daemon, но не замена runtime тесту Android 13/framework/HAL.

Без установки можно воспроизвести преобразование на ПК, используя sensor daemon именно из этого release:

```
python tools/patch_rom.py --manifest patches/2026-11-11.json sensors-v2-from-original sensors.qcom sensors.qcom.patched
```

Ожидаемый output SHA-256 — `6bb266619a744ca166f1e71e39897fb0205a4ddaecb993034f96711ce9228607`. Эта команда уже выполнена на извлечённом файле и дала нужный результат. Исходный daemon и patched binary не публикуются; дельта и проверка хешей доступны в репозитории. При несовпадении input SHA инструмент откажет.

Это инструкция **offline patch generation**, не подтверждение безопасной установки всего bundle в Android 13. Для отдельного device test нужны backup sensor daemon, правильный SELinux label, остановка sensors, atomic replacement и перезагрузка, затем rotation/crash/sleep comparisons. Такой on-device test сейчас не выполнялся.

## GNSS: перенос идеи имеет основания, готовой дельты пока нет

В `Gnss::nmeaCb` Android 13 legacy implementation найден вызов на `0xe952` → PLT `0x13b70`. Разбор relocation/GOT подтверждает `_ZN7android8hardware11hidl_string13setToExternalEPKcj` (GOT `0x161f0`), как в проблемном LOS17 ownership path. Следом строка передаётся GNSS callback. Это повод исследовать owned-copy repair; сам факт импорта такого метода не доказывает пользовательский crash в Android 13. Нужно проверить подходящую `copyFrom` ABI/export, NMEA buffer contract и поведение runtime, подготовить другую exact-build дельту. Наш 96692-byte HIDL файл и его offsets не используются для 86720-byte A13 файла.

Описанные автором Bluetooth/microSD/blue stripes не считаются исправленными каким-либо из наших патчей. Сравнение выполнено без прошивки Android 13 и без обещания устранить эти отдельные проблемы.

[Хеши и sanitized evidence](../evidence/android13-compatibility-2026-11-11.json).
