# One-shot MediaCodec lifecycle probe

The Java helper opens a component by exact name and releases it. Compile with javac targeting Java 8, convert with D8 for API 29, and run the resulting dex using Android app_process with CLASSPATH. Reflection avoids requiring an Android SDK stub jar. No APK installation is needed.

This is a component lifecycle test, not playback, secure-surface, MediaCrypto, licence or DRM validation. Calling the hidden secure component still reaches the vendor driver on this exact ROM. The legacy secure path can spend many seconds waiting on unavailable Binder services: a 25-second deadline was insufficient; the complete 90-second-budget test exited successfully. Always capture actual completion and driver reference state before another test.

[A/B report and rollback](../../docs/secure-video-ab-2026-11-12.md). Firmware images and automatic installation are deliberately absent from this test directory; exact private backups and verified file visibility were used for the controlled comparison.
