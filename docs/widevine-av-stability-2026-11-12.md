# Widevine L3: звук и более длительный video test

12 ноября 2026. На рабочем ядре выполнены два отдельных теста публичного зашифрованного sample Google с новыми штатными лицензиями Widevine. [Счётчики](../evidence/widevine-av-stability-2026-11-12.json).

## Audio

AAC извлечён из первых 2 MiB `tears_audio_eng.mp4`, начальная позиция около 20 секунд. MediaCrypto подключён к audio decoder, PCM передан в AudioTrack 44100 Hz stereo PCM16. Получены 480 decoded buffers из 483 encrypted inputs. AudioTrack принял 1966080 байт и сообщил 491520 проигранных PCM frames (около 11,15 секунды). Пользователь подтвердил нормальный слышимый звук. Громкость тестом не менялась.

## Video

Загружены первые 12 MiB `tears_h264_baseline_240p_800.mp4`, старт 24 секунды. Тот же путь Widevine L3/Qualcomm AVC/SurfaceControl с render callbacks. Цель — 1440 кадров, лимит цикла — 90 секунд. Фактический результат: 1406 encrypted inputs, 1401 output frames, 1397 render callbacks.

При 24 fps это около 58,4 секунды декодированного содержимого. Не следует приравнивать это к подтверждённой минуте плавного воспроизведения: helper использует reflection/IPC и фиксированный sleep 42 мс после выдачи буфера, не управляет показом по аудиочасам. Цель 1440 не достигнута. Конкретная причина выхода (time budget либо EOS частичного файла) отдельно не записывалась. Разница output/render callbacks не исследована. Этот тест не является измерением предельного fps.

## Стабильность и состояние

Между измерением в ходе video test и финалом совпадают PID media.codec и boot ID. Финальный crash buffer пуст. Cleanup helpers завершён. Это не полная диагностика всех журналов/служб или длительный нагрузочный тест. Audio и video шли последовательно: A/V sync ими не проверен.

Sample files, dex и license request/response удалены с планшета, `/data/local/tmp` пуст. Штатная регистрация L3 сохранена; системные библиотеки не менялись. Boot SHA-256 `d2cacd5c413e13a17489b7161062f2e9edbe53c3044c33368380d66df80b8cfc`.

Helpers: [audio](../experiments/secure-codec-open/DrmAudioProbe.java), [video](../experiments/secure-codec-open/DrmLongProbe.java). Ключи, лицензии и приватные журналы не публикуются. Для оценки обычного использования следующий подходящий тест — полноценный плеер с синхронизацией звука и изображения; самодельный helper эту функцию не реализует.
