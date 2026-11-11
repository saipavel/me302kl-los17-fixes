# Готовый приватный комплект рабочих ремонтов

Подготовлен по просьбе владельца **для всех рабочих ремонтов**, без экспериментального thermal startup patch. Это ZIP для распаковки на ПК и запуска Python/ADB, **не flashable ZIP для кнопки Install в TWRP** и не полная ROM. Полная установка выполняется через ADB в recovery; отдельный шаг Android применяет настройки.

Целевая сборка: `17.1-20230306-UNOFFICIAL-duma`, Android 10. Формат включает 11 файлов и GPS config symlink. Нужна Wi-Fi-only конфигурация: телефония и mobile data отключаются, общий модем сохраняется для GPS. Для использования SIM этот набор не предназначен.

## Содержимое

- Sensor daemon v2: устранение crash и неполной disabled-log mask.
- Bluetooth HFP: bounds/profile repair, микрофон гарнитуры.
- GNSS NMEA ownership repair, восстановленные legacy GPS libraries и адаптер питания через Location.
- GPS assistance configuration и cellular-disabled init/build.prop.
- Google configurator resource overlay.
- Существующий на планшете codec workaround от 6 ноября: скрыт неработающий secure AVC decoder. Это обход, не ремонт DRM или TrustZone.

Не включены kernel/thermal experiments, приложения, чистка кешей, обновления Android/WebView, firmware радио/bootloader/EFS или изменения пользовательских файлов. Wi-Fi autojoin не объявляется исправленным этим комплектом; sensor v2 уменьшает известные sensor wake-ups.

GPS adapter повторно собран из опубликованных исходников: SHA-256 совпал с установленным и проверенным `0dc65723709bac4b8574bcedb9285a72405f6ee7d4d7f26965d5405667e70016`. Остальные бинарные payload — точные проверенные файлы с уже исправленного планшета. Экспорт проверяет хеши всех файлов и четырёх GPS-зависимостей.

## Установка и откат

Полная инструкция находится в [repair-bundle-install.txt](repair-bundle-install.txt) и включена в ZIP как `INSTALL.txt`. Краткая последовательность:

1. Распаковать ZIP на ПК, выполнить `check` из работающего Android. При 0 изменений **не переустанавливать**: файлы уже установлены. Проверка хешей не заменяет проверку настроек и физических функций.
2. На поддерживаемой ещё не исправленной установке выполнить `prepare --backup ...`: точные исходные файлы/метаданные/links и перечисленные настройки сохраняются и проверяются **на ПК до любых записей в system**.
3. Войти в TWRP, снять галку System в Mount и запустить `install` на ПК. Installer подтверждает recovery, block device и offline build.prop, повторно проверяет все состояния, записывает/проверяет файлы и labels, размонтирует system и выполняет offline e2fsck. Перед каждой проверкой убеждается, что раздел не смонтирован. Автоматической перезагрузки нет.
4. Загрузить Android, выполнить `configure` с тем же PC backup и перезагрузиться. Этот шаг меняет HFP и перечисленные Wi-Fi-only/GPS параметры и package states; Location/Wi-Fi/Bluetooth/rotation switches сохраняются.
5. Повторить `check` и функциональные проверки.

При неудаче оставаться в TWRP и выполнить `rollback` с тем же bundle/serial/backup, затем после загрузки Android — `restore-settings`. Восстанавливается **точное состояние до prepare**, включая частично исправленную установку, если prepare был выполнен на ней. Неизвестные изменения после backup останавливают операцию. Wipe/Factory Reset не требуется.

Installer не предназначен для запуска внутри recovery без ПК: Python работает на ПК, ADB — транспорт. Полные команды с расположением опций приведены в INSTALL.txt.

## Проверки и пределы

Проверены целостность ZIP/payload, поддерживаемая версия, совпадение всех файлов на реальном планшете (0 изменений), отсутствие экспериментов и boot image. На планшете ничего не устанавливалось и не перезагружалось в этом раунде.

[Host regression tests](../tools/test_repair_bundle.py) проверяют настоящий Python orchestration с in-memory backend: полную установку и точный откат файлов/метаданных/настроек; прерывание после трёх записей и восстановление; отказ неизвестных файлов до записи; отказ повреждённого PC backup до mount; отказ Android 13; отказ неподходящей offline ROM с размонтированием. Эти тесты **не выполняют реальные mount/write/fsck**. Индивидуальные ремонты проверялись ранее, но совокупный installer на чистом втором устройстве не испытывался.

## Приватный ZIP и публичные исходники

Готовый ZIP сохранён у владельца на ПК, его SHA-256 и результаты находятся в [evidence](../evidence/repair-bundle-2026-11-11.json). Он содержит vendor libraries из частной копии ROM. Сам ZIP, firmware libraries, PC backups, serial и сырые журналы в публичный git не добавлены.

Публичный [repair_bundle.py](../tools/repair_bundle.py) умеет экспортировать комплект **с уже исправленного планшета этой сборки**:

```
python tools/repair_bundle.py --adb PATH_TO_ADB --serial SERIAL --output PRIVATE_OUTPUT.zip build
```

Для применения готового комплекта дополнительные Python packages и toolchains не нужны. Для повторной сборки собственного GPS adapter исходники и build.py находятся в tools/gps-power; экспорт требует точного хеша проверенного результата.

[Совместимость с опубликованным Android 13](android13-compatibility-2026-11-11.md): sensor binary patch подходит по точным байтам, весь набор — нет.
