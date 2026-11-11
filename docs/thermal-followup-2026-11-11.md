# Thermal: воспроизведён kernel fault, подготовлен source-кандидат

**Статус:** исследование продолжено без установки, перезагрузки или изменения настроек планшета. Найден конкретный ранний kernel defect; исправление подготовлено и проверено на ПК, **не собрано в полное ядро и не установлено**. Android thermal reporting остаётся недоступным, старый `thermald` работает.

## Что теперь установлено

Существующий boot-раздел совпадает с сохранённым до эксперимента образом по SHA-256:

`5d7dd05fd96a1e8041c456ba1ff5018ac98bb0418cf38b521f8e602651316e62`

После распаковки XZ kernel Image версия совпала с работающим ядром: `3.4.113-sweet-4.0`, build 6 марта 2023. Никаких изменений boot image не сделано.

В этой самой бинарной сборке:

1. `tsens_set_tz_warm_temp_degC` проверяет наличие `tmdev` и допустимость номера sensor, но **не проверяет** `tmdev->sensor[7].tz_dev` перед передачей в callback.
2. Callback `tsens_tz_set_trip_temp` в `0xc0761a68` выполняет `ldr r3, [r0, #0x188]` до проверки указателя. В сохранённом crash `r0=0`, fault address `0x188`.
3. Эмуляция неизменённых байтов существующего ядра с инициализированным `tmdev`, числом sensors 11 и ещё пустым `sensor[7].tz_dev` воспроизводит **тот же PC, тот же address и тот же размер чтения 4 bytes**.

Это воспроизводимый kernel NULL-zone defect, а не просто предположение по имени упавшей функции. Эмуляция моделирует состояние указателей, но не воспроизводит весь физический boot или точный источник задержки.

## Откуда берётся ранний вызов

Найдены публичные исходники [Den147/Sweet_kernel_rebase, Sweet 4.0](https://github.com/Den147/Sweet_kernel_rebase/tree/c1ec835b37a8ef39232cee7c4199d3b6b7196148), ветка sweet-q. В commit `c1ec835b37a8ef39232cee7c4199d3b6b7196148` config устанавливает `-sweet-4.0`. Это подходящий source reference; полного byte-for-byte соответствия всех файлов ядра не заявляется.

- [board-duma.c](https://github.com/Den147/Sweet_kernel_rebase/blob/c1ec835b37a8ef39232cee7c4199d3b6b7196148/arch/arm/mach-msm/asustek/duma/board-duma.c) задаёт 11 sensors, control sensor 7, затем вызывает `msm_tsens_early_init` и `msm_thermal_init` ещё при machine initialization.
- [msm_thermal.c](https://github.com/Den147/Sweet_kernel_rebase/blob/c1ec835b37a8ef39232cee7c4199d3b6b7196148/drivers/thermal/msm_thermal.c) запускает первый worker через фиксированные **5 секунд**. После чтения температуры он устанавливает trip points.
- [msm8960_tsens.c](https://github.com/Den147/Sweet_kernel_rebase/blob/c1ec835b37a8ef39232cee7c4199d3b6b7196148/drivers/thermal/msm8960_tsens.c) заполняет `tz_dev` позднее, в `tsens_tm_probe`, зарегистрированном через `module_init`. Early init выделяет обнулённую структуру и калибрует hardware, но thermal zones ещё не создаёт.
- В [drivers/Makefile](https://github.com/Den147/Sweet_kernel_rebase/blob/c1ec835b37a8ef39232cee7c4199d3b6b7196148/drivers/Makefile) input находится раньше thermal. При неудачной загрузке touch-driver handshake ещё продолжался после шестой секунды; kernel thermal fault уже произошёл на 5.205 s. В сохранённом журнале нет сообщений Android init или `Freeing unused kernel memory`.

**Вывод из совокупности данных:** загрузка успела пройти early hardware init, но worker сработал до завершения регистрации sensor zone. Фиксированная задержка оказалась недостаточной. Это сильное объяснение startup race в существующем ядре. Точную причину замедления touch/driver initialization в том запуске отдельно не установили.

Соответственно, успешная загрузка после удаления reporting-кандидата сама по себе не доказывает, что именно его исполнение вызвало fault. Найденный путь находится в раннем kernel initialization; нет подтверждения, что новый userspace service вообще успел стартовать. Предыдущую формулировку о связи с установленным thermal-кандидатом следует читать с этим уточнением. Его собственная ABI/registration совместимость всё ещё не проверена полной успешной загрузкой.

## Сравнение с официальным ASUS source

В ранее загруженном ASUS `kernel_10_10_3_41.zip` (вложенный tar.gz) есть настоящие `drivers/thermal/msm8960_tsens.c` и `msm_thermal.c`. Исходный callback тоже обращается к `thermal->devdata` без предварительной проверки самого `thermal`.

Однако исходный ASUS thermal controller использует повторный polling, а Sweet controller заменяет его на interrupt/trip-driven схему с первым запуском через 5 секунд. Найденный прямой вызов warm/cool setup из worker относится к Sweet-изменениям. Поэтому подмена целого драйвера/ядра стоковым не является обоснованным точечным ремонтом. Официальный source полезен для сравнения; он не содержит готовый modern Android reporting HAL.

## Подготовленный кандидат

[experiments/thermal-startup](../experiments/thermal-startup) содержит source patch и два воспроизводимых инструмента для ПК:

- Guard на NULL/error thermal-zone pointer возвращает `-EAGAIN` **до** callback.
- Controller обрабатывает этот результат, повторяя температурную проверку и попытку установки trip points через 100 ms. Просто вернуть ошибку и забыть об этом опасно: можно потерять дальнейшее interrupt-driven throttling.
- Исходные limits `80,85,92,102`, частоты `1512000,1350000,918000,384000` и hysteresis 5 сохранены. Обычный режим после успешной настройки не получает постоянного нового polling.

Проверки: patch cleanly applies к pinned source; host harness извлекает реальные изменённые функции, assertions включены. **718 сценариев** прошли, включая задержанную регистрацию на 0–100 retry steps, восстановление после `-EAGAIN`, error pointers/invalid IDs, обычные trip branches, hardware-error propagation и sweep temperature/hysteresis. Отдельная Unicorn-эмуляция исходного ядра воспроизвела saved crash.

Ограничения: hardware I/O и scheduler в host harness заменены; IRQ concurrency, полная готовность/lifetime драйвера и реальный throttling не проверены. Кандидат защищает наблюдённый путь, но не объявляется полным устранением всех probe/remove races. Полное ядро не собрано, boottest не выполнен. Не является adb-патчем для прямой записи в boot.img.

## Что важно для будущего reporting HAL

В живой системе sensor0 включён и читается, sensor7 sysfs mode — disabled, чтение temp возвращает `EINVAL`. Source подтверждает: sysfs getter отвергает disabled zones, тогда как внутренний `tsens_get_temp` не делает такую проверку mode. Поэтому `EINVAL` в sysfs **не доказывает** отсутствие внутреннего температурного контроля sensor7. Для этого исследования sensors не включались.

Нельзя смешивать пороги разных sensors: нынешний thermald для sensor0 начинает реальное снижение CPU frequency при 90 °C и задаёт shutdown action при 105 °C; Sweet kernel limits относятся к sensor7 (первое снижение при 85 °C). Ранее отклонённый reporting-кандидат считал sensor0, но прикреплял к нему kernel threshold 85 — это неверное сопоставление источников порога, его не следует переносить в следующий вариант. Raw temperature values имеют разные единицы: TSENS — °C, battery — десятые °C.

Практическая последовательность продолжения:

1. Review readiness/IRQ/error handling кандидата; собрать kernel в совместимом build environment, сохранив исходный boot/recovery и точный rollback.
2. Отдельно проверить загрузку и температурный контроль. Не объединять первый kernel boottest с reporting service.
3. Разрабатывать report-only HAL отдельно, с корректным ABI, сопоставлением sensors/порогов и без изменения mode/trip points существующей защиты. Проверка через временный userspace запуск после полной загрузки предпочтительнее первой установки в autostart.

Наличие runtime sysfs температур делает reporting технически возможным, но готового проверенного решения сейчас нет.

## Итог устройства после исследования

Новых файлов/настроек на планшете нет, перезагрузок в этом раунде не было. System state 1 clean, error count 0, read-only; совпадают восемь прежних repair hashes; sensors и thermald работают; текущий crash buffer пуст; `/data/local/tmp` пуст. Google configurator overlay предыдущего этапа сохранён. Сырые журналы, firmware images и персональные данные остаются на ПК.

[Краткое evidence](../evidence/thermal-followup-2026-11-11.json).
