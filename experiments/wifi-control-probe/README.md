# Temporary WCNSS control-channel diagnostic

This is diagnostic code for one exact LOS17.1 boot, not a Wi-Fi repair or Android 13 patch. It asks whether WCNSS_CTRL still answers when WLAN_CTRL times out. The healthy control succeeded; see the [dated report](../../docs/wifi-control-probe-2026-11-12.md) for fault reproduction and final installed state.

`probe.S` places 368 bytes of ARM code/constants in verified zero text-alignment padding at `0xc0cff000`, before `__start_rodata=0xc0d00000`. No image expansion, ramdisk change, polling service or heap allocation is needed. Three exact-build hooks are used:

- `0xc09920fc`: after WDI timeout logging and before recovery. Only expected response 52 (NV) can trigger the automatic probe.
- `0xc06052d4`: after a valid 12-byte WCNSS version response has been decoded/logged. A diagnostic response bypasses the otherwise automatic second NV upload; normal responses keep the displaced major-byte load and original path.
- `0xc0604f94`: temporary active-control trigger on reading `wcnss_version`; then resumes its original cached-version formatting. **This sysfs read has a diagnostic side effect in this test kernel.**

The source always formats the version as eight hex characters plus NUL in a 30-byte zero-initialized array. For this exact binary experiment only, byte 29 of that array (`penv+0x49`) stores a one-boot flag: 0 unused, 1 request pending, 2 response received, 3 insufficient FIFO space. Cached displayed text is unchanged. A full source implementation should add a dedicated field instead. A failed/late response must not trigger another NV download, so the flag remains until reboot. The trigger is one-shot across both entry points.

The message is exactly `{type=0x01000000, len=8}` on the already-open channel. A successful 8-byte write permits a single 250 ms `msleep` before reading the response flag. The usual 10-second NV timer is unchanged. `tx=8 state=1` is only no reply within this window; it does not prove a permanent whole-chip failure. Later logs and recovery timing must be inspected. `tx=8 state=2` proves this control request received a response. Querying a different core/service cannot prove the WLAN service is healthy.

The watchdog completion repair is retained. The original displaced PC-relative literal and RX major-byte load are replayed. The new code has no unwind-table entry; this is another reason to keep it temporary. Neither full boot images nor an automatic installer are distributed.

Build with Zig 0.13 (the `-g` preserves the ELF symbol table needed by the host test):

```text
zig cc -g -target arm-linux-gnueabi -mcpu=krait -marm -ffreestanding -fno-builtin -nostdlib -fno-unwind-tables -fno-asynchronous-unwind-tables -Oz -Wl,-T,probe.ld -Wl,--entry=probe probe.S -o /private/probe.elf
```

Host test dependencies: `pyelftools`, `unicorn`. Supply the owner's decompressed watchdog kernel (SHA-256 `f9cc7e5ea9d8135204bfb076c05ba9eeacf0e932854d35bbf9a400bd83a89a49`):

```text
python test_probe.py --base-kernel /private/kernel.bin --elf /private/probe.elf --output /private/test-result.json
```

97 modeled cases verify message bytes, response gating, preserved registers/stack, the restored sysfs entry path, one-shot behavior, null/uninitialized state, insufficient space and write failure. The host test never writes a full kernel image or connects to a device. External helpers and response arrival are modeled, not hardware-emulated.
