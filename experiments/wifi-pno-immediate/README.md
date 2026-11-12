# EXPERIMENTAL: Prima scheduled scan before host suspend

**Not installed or runtime-tested. Not part of the working-repairs bundle.**

The current tablet's kernel configures PNO with `SIR_PNO_MODE_ON_SUSPEND`.
Android 10 requests PNO while the display is off, including while USB keeps
the host awake. A controlled test showed successful driver initialization,
no reconnection within 57.9 seconds, and a PNO-start event. Waking only the
display restored validated internet within four seconds, without another
Wi-Fi toggle. The host was Dozing before that wake. This supports the mode
mismatch hypothesis; it does not prove it or repair the separate NV timeout.

Reference source, pinned to Sweet commit:

- [Scheduled-scan setup](https://github.com/Den147/Sweet_kernel_rebase/blob/c1ec835b37a8ef39232cee7c4199d3b6b7196148/drivers/staging/prima/CORE/HDD/src/wlan_hdd_cfg80211.c)
- [PNO mode enum](https://github.com/Den147/Sweet_kernel_rebase/blob/c1ec835b37a8ef39232cee7c4199d3b6b7196148/drivers/staging/prima/CORE/MAC/inc/sirApi.h)

The source patch uses the existing IMMEDIATE mode (0), replacing ON_SUSPEND
(1). Scan intervals and repeat count remain unchanged. The exact compiled
store was verified in the owner's uncompressed kernel at `0xc0847cbc`:
`str ip,[r7,#4]` becomes `str lr,[r7,#4]`; ip is 1, lr is 0. The adjacent
scan-timer count still uses ip. Twelve ARM execution cases across six scan
intervals preserved the rest of the request and call arguments.

`build.py` requires the exact original 16 MiB boot snapshot, SHA-256
`5d7dd05fd96a1e8041c456ba1ff5018ac98bb0418cf38b521f8e602651316e62`:

```text
python build.py ORIGINAL_BOOT.img PRIVATE_TEST_BOOT.img
```

This is an exact binary experiment, not a full kernel source build. It
decompresses the existing XZ payload, changes one ARM instruction, compresses
with ARM BCJ/LZMA2 and CRC32, and verifies the decoded result. The new stream
fits the original allocation; zero padding preserves all zImage offsets and
the original tail, including the decompressed-size word. The kernel's
`decompress_unxz.c` accepts XZ_STREAM_END without consuming trailing padding.
The legacy boot ID is recomputed with this image's original convention,
including zero-length second and DT components. Ramdisk, image length and
trailing bytes are preserved. Recompression bytes may vary by liblzma version.

The prepared private candidate on the owner's PC has SHA-256
`3d099f722ddffac15bc8e41d2791cc8af15fc9e990db6b43280840369d2ddc21`.
Full images contain the owner's firmware and are not published.

## Required next test

Use a PC with a working signed ASUS bootloader driver. The attempted driver
installation on the current PC was not performed because administrator
rights were unavailable. The original boot partition was verified unchanged
after returning to Android. The candidate has never been sent to fastboot.

First use **temporary RAM boot only**, if the bootloader supports it:

```text
fastboot boot PRIVATE_TEST_BOOT.img
```

Do not flash this untested candidate. A normal reboot returns the original
boot partition. Confirm that the modified kernel actually ran before judging
the result: its version string is deliberately unchanged. Compare the mode
store in a privileged read-only running-kernel capture, or another reliable
runtime attestation; a changed boot ID alone proves only a reboot.

Then test saved-network reconnection with the screen off and USB connected,
and separately with USB unplugged. Verify that connection cancels PNO as
usual, ordinary scans still work, and sleep/battery behaviour does not
regress. Firmware IMMEDIATE-mode behaviour on this exact WCNSS firmware is
not yet verified. No battery improvement or power neutrality is claimed.

The separate WDI_NV_DOWNLOAD_RESP/Prima reinitialization failure still needs
its own diagnosis. This candidate must not be described as a complete Wi-Fi
repair, applied to Android 13, or added to the working-repairs package until
runtime validation is complete.
