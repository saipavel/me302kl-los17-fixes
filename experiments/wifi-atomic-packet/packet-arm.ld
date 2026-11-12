ENTRY(packet)
SECTIONS { . = 0xc003da38; .text : { *(.text*) } /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }
memcpy = 0xc0099510; kernel_stream = 0xc003ce0c; kernel_open = 0xc003c5a4;
