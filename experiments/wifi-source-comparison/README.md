# ASUS / Sweet source comparison

This read-only Python standard-library tool compares 15 selected function definitions in both copies of Prima in the ASUS source archive against the pinned Sweet reference. It also compares the entire `smd.c` byte for byte. It does not build, flash, preprocess C or prove semantic equivalence.

[Report, provenance and limitations](../../docs/wifi-official-driver-comparison-2026-11-12.md).

Extract the nested tar.gz in the owner's ASUS `kernel_10_10_3_41.zip` into a private reference directory. Preserve both `drivers/net/wireless/prima` and `drivers/staging/prima`. Obtain the four corresponding Sweet files from commit `c1ec835b37a8ef39232cee7c4199d3b6b7196148`: `wlan_qct_wdi.c`, `wlan_qct_wdi_cts.c`, `wlan_qct_pal_device.c` (under `drivers/staging/prima`) and `arch/arm/mach-msm/smd.c`. Place these four files in one Sweet reference directory.

```text
python compare.py --asus-tree /private/asus/kernel --sweet /private/sweet --output comparison.json
```

Comments and whitespace are ignored, and the identifier `__FUNCTION__` is normalized to `__func__`. All other tokens, including preprocessing directives and string literals, are retained. Missing or duplicate selected definitions fail instead of being reported as equal. Types, includes, feature flags and compiler output require separate inspection. The script never connects to a device.
