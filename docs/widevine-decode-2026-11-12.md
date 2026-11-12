# Widevine L3: лицензия и декодирование зашифрованных кадров проверены

12 ноября 2026. После [регистрации Widevine](widevine-provisioning-2026-11-12.md) получена и принята лицензия публичного тестового ролика Google, зашифрованные samples расшифрованы и декодированы.

Источник: публичный Widevine sample `2015_tears`, представление `tears_h264_baseline_240p_800.mp4` из [списка ExoPlayer](https://github.com/google/ExoPlayer/blob/release-v2/demos/main/src/main/assets/media.exolist.json). Для локального теста загружены первые 4 MiB файла через HTTP Range. License server — штатный Widevine test proxy, provider `widevine_test`.

Одноразовый [helper](../experiments/secure-codec-open/DrmDecodeProbe.java) открывает MediaExtractor, MediaDrm session, получает PSSH и license request. Лицензия получена на ПК и передана обратно в тот же живой объект MediaDrm. Затем MediaCrypto подключён к обычному `OMX.qcom.video.decoder.avc`, вывод — скрытая compositor Surface. Результат финального запуска:

```text
START_SAMPLE_US=24000000
LICENSE_REQUEST_READY
LICENSE_ACCEPTED
REQUIRES_SECURE=false
DECODE_RESULT encrypted_inputs=76 queued=76 output_frames=72
CLEANUP_DONE
```

Первые запуски выдали кадры из clear lead с `encrypted_inputs=0`, поэтому не считались подтверждением расшифрования. Во втором seek был ошибочно выполнен до selectTrack и не обеспечил переход. В финальной версии seek выполняется после selectTrack, фактическая позиция проверена: 24 секунды. Все 76 входных samples имели CryptoInfo и переданы через queueSecureInputBuffer; получены 72 output buffers без EOS. Лицензия принята без ошибок, cleanup завершён.

Это подтверждает короткий локальный decode зашифрованного AVC в Widevine L3. Output buffers освобождены без rendering: изображение на экране, звук, длительное воспроизведение и коммерческие сервисы не проверялись. Аппаратный secure AVC/L1 этим не проверен: MediaCrypto сообщил requiresSecureDecoderComponent=false. Рабочее ядро `d2cacd5c413e13a17489b7161062f2e9edbe53c3044c33368380d66df80b8cfc` оставалось установленным, экспериментальный MFC kernel не требовался.

На планшете удалены sample, dex и временные license request/response, `/data/local/tmp` пуст. Штатное provisioning Widevine сохранено. Сырые DRM-запросы, ответы и сертификаты не публикуются. Helper ловит ошибки и может завершиться exit 0 при неуспехе: оценивать нужно явные результаты стадий и счётчики, а не один exit code.
