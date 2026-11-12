ENTRY(probe)
SECTIONS { . = 0xc0cff000; .text : { *(.text*) } /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }
smd_write_avail = 0xc003edac;
smd_write = 0xc003eca8;
msleep = 0xc00af710;
printk = 0xc0c676c8;
