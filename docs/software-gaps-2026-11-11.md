# DeviceConfig и thermal reporting: 11 ноября 2026

**Продолжение исследования:** [воспроизведён ранний kernel NULL-zone defect и подготовлен source-кандидат](thermal-followup-2026-11-11.md). Новых изменений на планшете нет.

## Итог установленного состояния

Android загружается. Все восемь хешей прежних ремонтов совпадают; system read-only, raw state 1 (clean), error count 0. Crash buffer текущей загрузки пуст. `thermald` и sensors работают. Location и блокировка поворота сохранены, rooted debugging оставлен включённым по просьбе владельца. Временные тесты удалены с планшета; бэкапы и исследовательские материалы находятся на ПК.

**Исправлено назначение Google Play services как DeviceConfig configurator.** Thermal reporting по-прежнему отсутствует: экспериментальный адаптер удалён после неудачной загрузки. Это частичный результат, а не ремонт обеих подсистем.

## Google DeviceConfig: причина и узкий ремонт

До изменения framework resource `config_deviceConfiguratorPackageName` был пуст, а проверка `WRITE_DEVICE_CONFIG` для `com.google.android.gms` возвращала -1. Android 10 PackageManager использует этот resource для выбора configurator; PermissionManager выдаёт выбранному пакету configurator-protected permissions. В проверенном manifest Android 10 этот флаг есть только у `WRITE_DEVICE_CONFIG`. GMS уже запрашивает это право.

Добавлен статический resource overlay с единственной строкой `config_deviceConfiguratorPackageName=com.google.android.gms`:

- Путь: `/system/product/overlay/Me302klConfigurator/Me302klConfiguratorOverlay.apk`.
- SHA-256: `105fa4a3ac1a1d407c23f3f248aca4a1b318039bc20d3ca3a50e3c9422cd88f9`.
- Размер установленного APK: 3478 байт; `hasCode=false`, без служб и исполняемого кода.
- До установки idmap2 с product policy принял overlay и показал ровно одно сопоставление resource `0x0104016b`.
- После отдельной установки и перезагрузки resource возвращает `com.google.android.gms`, PackageManager check возвращает 0; `dumpsys package` подтверждает `granted=true`.
- В захваченном после загрузки журнале нет повторения прежних DeviceConfig denial events. Это наблюдение ограничено текущим интервалом; конкретный пользовательский эффект исходных отказов не был воспроизведён.

`packages.xml`, разрешения произвольных пакетов и проверки безопасности не редактировались. Исходный framework-res.apk не менялся. Overlay не изменяет графику или иконки.

Исходники и сборка: [tools/configurator-overlay](../tools/configurator-overlay). Для сборки нужны aapt2, framework-res.apk именно этой ROM, JDK и собственный signing keystore; параметры описаны в `build.py --help`, пароль передаётся через `ME302KL_OVERLAY_STOREPASS`. Использованный приватный ключ сохранён только на ПК. Пересборка с другим ключом не обязана иметь тот же APK-хеш. Установка требует root/remount и предварительного бэкапа, не обычного `adb install`.

Узкий откат: удалить только указанный APK и опустевший каталог overlay из system в recovery с проверкой точного пути, затем штатно размонтировать system и перезагрузить. Не очищать userdata. Если PackageManager не пересчитает designation сразу, проверить состояние после дополнительной штатной загрузки. Автоматический установщик не опубликован.

Проверенные исходники Android 10: [PackageManagerService](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-10.0.0_r1/services/core/java/com/android/server/pm/PackageManagerService.java), [PermissionManagerService](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-10.0.0_r1/services/core/java/com/android/server/pm/permission/PermissionManagerService.java), [framework config](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-10.0.0_r1/core/res/res/values/config.xml).

## Неудачный thermal-кандидат и восстановление

Был подготовлен read-only legacy thermal HAL, читающий существующие CPU/battery sysfs temperatures, и небольшой native HIDL service с init/VINTF registration. Локальные ABI/buffer/scaling проверки и запуск ограниченного startup-check проходили. Они **не доказали безопасность полной загрузки**.

При первой совместной установке thermal-кандидата и Google overlay планшет остановился на ASUS logo. В сохранённом last_kmsg на uptime 5.205 s зарегистрирован kernel NULL-pointer:

```
tsens_tz_set_trip_temp+0xc/0x248
tsens_set_tz_warm_temp_degC -> check_temp -> process_one_work
process: kworker/1:1
```

Перед этим kernel msm_thermal сообщал установку trip range 0..80 для sensor 7. Лог не указывает на исчерпание RAM. Точная причинная связь с новым адаптером не изолирована; наличие ошибки в thermal kernel path не доказывает конкретный дефект userspace-кода.

Через TWRP удалены все пять добавленных файлов, прежние восемь хешей проверены, offline e2fsck завершён с повторной проверкой exit 0. Android успешно загрузился. Затем **только Google overlay** установлен отдельно: загрузка прошла и право выдано. Четыре thermal-файла отсутствуют:

```
/vendor/lib/hw/thermal.msm8960.so
/vendor/bin/hw/me302kl-thermal-service
/vendor/etc/vintf/manifest/me302kl-thermal.xml
/vendor/etc/init/me302kl-thermal.rc
```

Неудачные исходники сохранены вне deployable репозитория, на ПК, для исследования; готовым ремонтом они не являются. Старые thermald, thermald.conf, thermal HIDL implementation и framework-res.apk не изменялись: их хеши после восстановления совпали с исходными.

`HAL Ready: false` остаётся. Старый thermald и kernel msm_thermal присутствуют; это не заменяет физический тест throttling. Современный thermal reporting требует дальнейшего исследования совместимости ядра/драйвера и изолированных проверок. Повторять неудачную установку в текущую рабочую систему не следует.

## Нагрузка

В оставленном исправлении Google нет нового процесса, таймера или опроса датчиков. APK занимает 3478 байт на system; это размер файла, не измерение суммарной RAM overlay. Дополнительная работа GMS после разрешения DeviceConfig возможна, её длительное влияние на батарею не измерено. Новый thermal service **не оставлен**, его реальное потребление RAM после полной загрузки не измерялось. Прежний sensor v2, напротив, уменьшил диагностические wake-ups в сравнительном тесте.

[Санитизированные результаты](../evidence/software-gaps-2026-11-11.json). Сырые журналы, ключи, ROM-библиотеки и персональные данные не опубликованы.
