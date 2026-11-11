# Thermal startup: исследовательский кандидат, НЕ установлен

Это **не готовая прошивка и не проверенный на планшете kernel patch**. Он предназначен для дальнейшего review/build/test. Полное ядро с этим изменением не собиралось; загрузка и физическая thermal protection не испытывались. Он не добавляет Android thermal HAL.

База: `Den147/Sweet_kernel_rebase`, commit `c1ec835b37a8ef39232cee7c4199d3b6b7196148` (Sweet 4.0, sweet-q). [Контекст и точные результаты](../../docs/thermal-followup-2026-11-11.md).

Файлы:

- `0001-retry-unregistered-tsens-zone.patch`: при отсутствующем/error thermal-zone pointer вернуть `-EAGAIN`; thermal worker повторяет проверку через 100 ms. Сохраняются исходные thresholds, hysteresis, частоты и обычный interrupt-driven режим. Это не постоянный дополнительный polling после успешной установки trip points.
- `reproduce.py`: воспроизводит точный saved fault в Unicorn по байтам существующего boot image. Принимает только проверенный SHA-256 этой сборки. Ни прошивка, ни kernel binary не включены.
- `verify.py`: извлекает реальные изменённые функции из source tree и собирает host C harness с Zig. Assertions принудительно включены. Hardware register access, scheduler и temperature acquisition заменены тестовыми реализациями.

В полном checkout указанного commit сначала выполнить `git apply --check` и `git apply` для patch. Затем:

```
python verify.py --source PATH_TO_PATCHED_KERNEL --zig PATH_TO_ZIG --work TEMP_HOST_DIRECTORY
python reproduce.py PRIVATE_BACKUP_BOOT_IMG
```

Для второго сценария нужны Python bindings Unicorn. Все операции выполняются на ПК. Не переносите адреса в другую сборку и не пытайтесь применять source patch напрямую к boot.img.

Ограничения кандидата: нет kernel integration/IRQ concurrency теста, full-driver readiness/lifetime synchronization не переработана. Guard закрывает наблюдённый NULL pointer и ранний error pointer, но это не доказательство исправности всех возможных probe/remove/failure races. Повторяемый `-EAGAIN` вызывает временные retry и существующий kernel trip-range log; поведение при постоянном отказе probe требует review. Отдельное исследование report-only HAL должно сохранить старый thermald и не включать выключенные sensors ради новых показаний.

Патч изменяет GPLv2-only код Linux Foundation; исходные лицензии базовых файлов сохраняются. В этом каталоге нет автоматического установщика.
