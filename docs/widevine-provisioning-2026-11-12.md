# Widevine L3: регистрация выполнена, DRM-сессия открывается

12 ноября 2026. До проверки `MediaDrm.openSession()` завершался `NotProvisionedException`. После штатной регистрации через Google открывается успешно, в том числе из нового процесса после освобождения первоначального MediaDrm.

## Что выполнено

Пользователь отдельно разрешил отправить подписанный provisioning request планшета на сервер Google. Запрос отправлен на HTTPS endpoint, возвращённый штатным `MediaDrm.getProvisionRequest()`. Получен HTTP 200. Запросы, ответы, сертификаты, полный URL и данные устройства не публикуются.

Для этого старого plugin важно сохранить живой MediaDrm между получением запроса и применением ответа. Первые попытки применить ответ в другом объекте дали ошибки `provisioning object missing` и `RewrapDeviceRSAKey fails`. Финальный тест сохранил объект, дождался ответа Google и вызвал `provideProvisionResponse` на том же объекте: `PROVISION_APPLIED`, `SESSION_OPEN_OK`, `AVC_REQUIRES_SECURE=false`.

Повторный read-only capability helper в новом процессе независимо подтвердил:

```text
WIDEVINE_SUPPORTED=true
vendor=Google
version=1.0
securityLevel=L3
SESSION_OPEN_OK
AVC_REQUIRES_SECURE=false
```

Регистрация меняет штатное хранилище Widevine на планшете. Оно намеренно сохранено; это выполненное исправление состояния provisioning, а не временный binary patch. Ключи и сертификаты не извлекались для публикации. Проверка после перезагрузки ещё не выполнена.

## Что это даёт и чего ещё нет

Теперь приложения могут открыть Widevine L3 session. Получение контентной лицензии, расшифрование и воспроизведение тестового ролика ещё не проверены; совместимость конкретных стриминговых сервисов и качество видео этим не гарантируются.

Plugin сообщил отказ при запросе securityLevel L1. Его журнал указывает на отсутствующий `liboemcrypto.so` и fallback на L3. Значит, успешная регистрация L3 не проверяет ранее восстановленный аппаратный secure AVC. В официальной ASUS ROM есть старый `system/vendor/lib/libwvdrm_L1.so`; его наличие само по себе не доказывает совместимость с Android 10 или наличие рабочего современного OEMCrypto ABI.

Временные dex и provisioning request/response на планшете удалены, `/data/local/tmp` пуст. Boot по-прежнему рабочий `d2cacd5c413e13a17489b7161062f2e9edbe53c3044c33368380d66df80b8cfc`. Experimental MFC kernel, VIDC firmware и decoder patch не установлены постоянно.

API: [Android MediaDrm](https://developer.android.com/reference/android/media/MediaDrm). Предыдущий аппаратный этап: [secure AVC lifecycle с увеличенным MFC heap](secure-mfc-kernel-2026-11-12.md).
