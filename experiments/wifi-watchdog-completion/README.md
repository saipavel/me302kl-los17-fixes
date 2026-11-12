# Candidate: complete the Wi-Fi watchdog's failed-reset exit

**Exact-boot candidate built and installed through TWRP on the owner’s tablet. See the [runtime report](../../docs/wifi-watchdog-repair-2026-11-12.md). The initial NV-download timeout and screen-off discovery remain separate issues.**

During the PNO kernel experiment, reloading Prima hit WDI_NV_DOWNLOAD_RESP
timeout and WCNSS subsystem recovery. Logs then recorded `Failed to re-init
WLAN` and `Watchdog Thread Failed to Reset, Exiting!!!!`. The Wi-Fi HAL's
kernel wait channel was `vos_watchdog_close`, and a separate Wi-Fi-enable
request did not recover service before reboot.

In [pinned Sweet vos_sched.c](https://github.com/Den147/Sweet_kernel_rebase/blob/c1ec835b37a8ef39232cee7c4199d3b6b7196148/drivers/staging/prima/CORE/VOSS/src/vos_sched.c),
`VosWDThread` normally calls `complete_and_exit(&pWdContext->WdShutdown, 0)`.
Its `err_reset` label instead returns without completing `WdShutdown`.
`vos_watchdog_close` waits on that completion. If the thread has already
exited through `err_reset`, nobody remains to complete it.

The original installed kernel's disassembly confirms both behaviours:
normal completion at `0xc096ab94..0xc096ab9c`, the failed-reset log and return branch at `0xc096acec..0xc096ad0c`, and the close wait at `0xc096b0c0`. An earlier note incorrectly labelled `0xc096ad9c` as the reset-error diagnostic: it belongs to the NULL-argument path and is left untouched. The return epilogue is shared with other exits: blindly
redirecting every return to completion would be unsafe, including for NULL
thread arguments. The proposed source change touches only `err_reset`.

The patch preserves the fatal diagnostic, then uses the same completion and
exit as the normal path. It addresses a shutdown deadlock, **not the initial
NV-download failure or screen-off network discovery**. Watchdog open zeroes the context and initializes the shutdown completion. This change does not clear recovery flags prematurely; it uses the existing normal completion/exit operation before the close caller can finish cleanup.

## Exact binary implementation

`build.py` requires the same exact original 16 MiB boot snapshot as the PNO
experiment. It preserves the original PNO mode; that rejected experiment is
not combined with this repair. The source patch applies to the pinned file.

The compiled reinit-error path uses R4 for a diagnostic string, overwriting
the watchdog context. Five register-only changes use R6 for that string
instead, preserving every diagnostic call argument and R4 as the context.
The reset-error exit branch then uses the existing normal completion code.
The normal and NULL-argument paths remain unchanged. R7 is not used to
recover the context: an already-posted event can bypass its initialization.

Exact before/after words are in `exact-kernel-edits.json`. There are six
changed ARM instructions, no new kernel worker or userspace service, and no
repeated polling added. Existing log messages are preserved.

```text
python build.py ORIGINAL_BOOT.img PRIVATE_WATCHDOG_BOOT.img
python test_emulation.py ORIGINAL_BOOT.img PRIVATE_WATCHDOG_BOOT.img
```

The second command requires Python package `unicorn`. It executes original
and patched instructions, stubbing only the diagnostic callees and stopping
at completion/return. There are 128 executions covering 16 contexts, shutdown
failure, reinit failure, normal exit and NULL arguments. It verifies the
correct completion pointer, retained return behaviour and identical log,
printk and warning arguments. It is not a Linux scheduler simulation.

The builder checks the original image digest, applies only the six edits,
recompresses ARM BCJ/LZMA2 with CRC32 within the original allocation and
recomputes the original legacy boot ID convention. Stronger compression is
used if necessary; dictionary size remains 32 MiB. It verifies decompression,
unchanged zImage layout, original PNO word, ramdisk and trailing image bytes.
No device is accessed by the builder. Full images are private firmware.

Test image SHA-256:
`d2cacd5c413e13a17489b7161062f2e9edbe53c3044c33368380d66df80b8cfc`.
Original/rollback SHA-256:
`5d7dd05fd96a1e8041c456ba1ff5018ac98bb0418cf38b521f8e602651316e62`.

Use only the exact owner's kernel/ROM. Android 13 and other kernels are not
supported. The system-file working-repairs ZIP does not include a boot image;
this kernel experiment is separate. The runtime report states what was and
was not verified before deciding whether to keep or roll back this image.
