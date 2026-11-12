# Candidate: complete the Wi-Fi watchdog's failed-reset exit

**Source patch only. Not built into a new image, fault-injection tested, or installed.**

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
normal completion at `0xc096ab94..0xc096ab9c`, error-log call at
`0xc096ad9c` followed by a plain return, and the close wait at
`0xc096b0c0`. The return epilogue is shared with other exits: blindly
redirecting every return to completion would be unsafe, including for NULL
thread arguments. The proposed source change touches only `err_reset`.

The patch preserves the fatal diagnostic, then uses the same completion and
exit as the normal path. It addresses a shutdown deadlock, **not the initial
NV-download failure or screen-off network discovery**. Recovery flags and
concurrent cleanup still require review before any binary implementation.

The source patch applies to the pinned reference file. It has not undergone
runtime or concurrency validation. A useful next test is an isolated model
with a closer already waiting and a failed-reset worker: completion must
release the closer exactly once. Hardware validation must then confirm a
real timeout can finish cleanup without leaving the HAL blocked. The PNO
experiment was rolled back separately and is not bundled with this change.
