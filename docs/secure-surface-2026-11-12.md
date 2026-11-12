# Secure AVC: SurfaceControl, выходные буферы и Widevine

Продолжение: [аудит совместимости официальной библиотеки](secure-official-library-audit-2026-11-12.md).

12 ноября 2026. Продолжение [исправления входных буферов](secure-buffer-port-2026-11-12.md). Собственный защищённый фильм для этих проверок не нужен.

## Новый тест вывода

`CodecSurfaceProbe.java` создаёт скрытый secure SurfaceControl через SurfaceFlinger, копирует его Surface, затем вызывает create/configure/start/stop/release. Слой удаляется при завершении. Это проверяет настройку декодера, а не показ кадров. Обычный AVC прошёл все стадии до и после эксперимента; после отката — за 225 мс.

С временным патчем входного порта и официальным VIDC firmware:

- Surface создаётся, secure decoder открывается, configure проходит.
- Два защищённых входных буфера создаются без прежнего падения.
- Прежняя ошибка `consumer cannot handle protected buffers` отсутствует.
- Первый выходной GraphicBuffer не регистрируется: `ION ALLOC failed ... errno = 12`, затем `ERROR in allocating meta buffers` и `InsufficientResources`. Start не проходит.
- Release завершился; общее время 40,6 секунды. Исходные firmware и библиотека восстановлены и проверены; PIL refcount 0. Ядро, XML codecs и рабочий пакет ремонтов не менялись.

## Где теперь блокировка

Дизассемблирование установленного `libOmxVdec.so` показывает вызов `vdec_alloc_meta_buffers`: защищённые metadata направляются в ION heap mask `0x1000` (MFC, id 12), с secure flag `0x80000000`. Live debugfs показывает размер MFC всего `0x2000` (8192 байта). Однако **и официальный ASUS kernel, и установленный kernel имеют такой размер в статической таблице heaps**. Поэтому нельзя объявлять это простым урезанием памяти в Lineage или без проверки увеличивать carveout.

Официальная ASUS `libOmxVdec.so` отличается: нет экспортированной функции `vdec_alloc_meta_buffers`, а просмотренный защищённый путь allocator использует MM mask `0x100`. Это указывает на различие поколений vendor stack. Не доказано, что достаточно заменить одну библиотеку или перенаправить metadata в MM: адресные ограничения firmware, защита памяти и ABI должны совпадать. Точный размер отказавшего allocation в этом тесте не инструментировался. `ENOMEM` относится к конкретному ION allocation, а не к общему дефициту RAM.

Следующий предметный шаг — проверить совместимость официального decoder/firmware/kernel metadata-протокола и зависимости библиотеки. Не отключать защиту буферов и не менять secure heap на обычную память для обхода ошибки.

## Widevine проверен отдельно

Read-only helper сообщает: supported=true, vendor Google, version 1.0, securityLevel L3. `openSession()` завершается `NotProvisionedException`. Provisioning и получение лицензии не запускались; ключи и идентификаторы устройства не читались. Это отдельная блокировка DRM-теста. L3 сам по себе не подтверждает возможность проверки аппаратного secure AVC.

В официальном [списке ExoPlayer](https://github.com/google/ExoPlayer/blob/release-v2/demos/main/src/main/assets/media.exolist.json) есть публичные Widevine samples и тестовые license endpoints. Они позволяют обойтись без личной подписки/фильма, но не устраняют проблемы provisioning и совместимости аппаратного пути. Ролик и лицензия на этом этапе не загружались.

## Состояние после проверки

Все временные mounts сняты, исходная библиотека восстановлена, диагностическое свойство очищено, оба dex helper удалены. Обычный AVC прошёл create/configure/start/stop/release. Новых постоянных исправлений на планшете нет. Результат — устранённое ограничение предыдущего теста и локализованный следующий отказ, а не работающий secure playback.

[Обезличенные результаты](../evidence/secure-surface-2026-11-12.json). Helpers: [SurfaceControl](../experiments/secure-codec-open/CodecSurfaceProbe.java), [Widevine capabilities](../experiments/secure-codec-open/DrmCapabilityProbe.java). Сырые логи и бинарники остаются приватными.
