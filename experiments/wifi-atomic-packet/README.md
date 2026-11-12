# Atomic SMD packet prototype — unsuccessful, rolled back

This is the actual ARM assembly used in the 12 November 2026 hardware experiment, not an installable repair. [Results and limits](../../docs/wifi-nv-timeout-2026-11-12.md): the first reload still suffered NV-download timeout. Do not include this prototype in the working bundle.

`packet.S` and `packet-arm.ld` target only the exact LOS17.1 kernel described in that report. Addresses, channel layout and helper ABI are build-specific. The 424-byte replacement occupies the old 488-byte function slot at `0xc003da38`; its remaining bytes were ARM NOP padding. The installed watchdog fix was retained during testing and restored on rollback.

Build the code object with Zig 0.13 from this directory:

```text
zig cc -target arm-linux-gnueabi -mcpu=krait -marm -ffreestanding -fno-builtin -nostdlib -fno-unwind-tables -fno-asynchronous-unwind-tables -Oz -Wl,-T,packet-arm.ld -Wl,--entry=packet packet.S -o packet-arm.elf
```

This command produces an ELF code object, not a boot image. No generic flasher is provided for a failed candidate. Private complete images, raw logs and personalized configuration remain on the owner's PC. The host evidence describes 865 modeled cases / 1730 executions, not a hardware proof of correctness. The packet-level optional SMD debug messages were not reproduced by this prototype.
