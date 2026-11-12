# Widevine L3: проверен вывод зашифрованного видео

12 ноября 2026. Продолжение [проверки decode](widevine-decode-2026-11-12.md): тестовая SurfaceControl показана на основном layer stack, output buffers передавались на отображение. MediaCodec OnFrameRenderedListener подтвердил показ кадров.

Публичный sample и license endpoint те же, что в предыдущем тесте. Лицензия получена для новой живой DRM-сессии и принята. Начальная позиция 24 секунды, входные samples зашифрованы. Установлено штатное рабочее ядро; experimental secure codec repairs для L3 не требуются.

```text
START_SAMPLE_US=24000000
LICENSE_ACCEPTED
REQUIRES_SECURE=false
DISPLAY_TEST_STARTED
RENDERED_CALLBACKS=188
DECODE_RESULT encrypted_inputs=198 queued=198 output_frames=192
CLEANUP_DONE
```

[Helper](../experiments/secure-codec-open/DrmRenderProbe.java) создаёт отдельный HandlerThread для callbacks. Surface показана в позиции 100×100 с увеличением 2×. Передача кадров замедлена на 42 мс на кадр; тест длится около восьми секунд. 192 output buffers переданы с render=true, 188 callbacks получены после дополнительного ожидания 500 мс. Разница в четыре кадра этим измерением не объяснена: нельзя утверждать, что все декодированные кадры реально показаны или что измерена точность синхронизации.

Это программное Widevine L3 с обычным Qualcomm AVC decoder. Callback подтверждает событие rendering по данным Android, но визуальная оценка пользователем, звук, A/V sync, длительное воспроизведение, HD и коммерческие сервисы в этот тест не входят. Аппаратный L1 и secure AVC остаются отдельными задачами.

Тестовый слой удалён, DRM-сессия закрыта, callback thread остановлен. Sample, dex, license request/response удалены; `/data/local/tmp` пуст. Рабочий boot SHA-256 `d2cacd5c413e13a17489b7161062f2e9edbe53c3044c33368380d66df80b8cfc`.
