.syntax unified
.arm
.section .text.probe,"ax",%progbits
.global probe
.type probe,%function
probe:
    push {r0-r7,ip,lr}
    sub sp,sp,#8
    cmp r6,#52
    bne done
    ldr r4,=0xc1488584
    ldr r4,[r4]
    cmp r4,#0
    beq done
    ldr r0,[r4,#0x28]
    cmp r0,#0
    beq done
    ldrb r3,[r4,#0x2c]
    cmp r3,#0
    beq done
    cmp r3,#73
    beq done
    ldrb r3,[r4,#0x49]
    cmp r3,#0
    bne done
    bl smd_write_avail
    cmp r0,#8
    movlt r7,r0
    movlt r3,#3
    strblt r3,[r4,#0x49]
    blt report
    mov r3,#1
    strb r3,[r4,#0x49]
    dmb ish
    mov r3,#0x01000000
    str r3,[sp]
    mov r2,#8
    str r2,[sp,#4]
    mov r1,sp
    ldr r0,[r4,#0x28]
    bl smd_write
    mov r7,r0
    cmp r7,#8
    bne report
    mov r0,#250
    bl msleep
report:
    dmb ish
    ldrb r2,[r4,#0x49]
    mov r1,r7
    ldr r0,=message
    bl printk
done:
    add sp,sp,#8
    pop {r0-r7,ip,lr}
    ldr r3,=0x002e3cd0
    bx lr
.size probe,.-probe
.global response_gate
.type response_gate,%function
response_gate:
    push {r0,ip,lr}
    ldr r0,[r6]
    ldrb ip,[r0,#0x49]
    cmp ip,#1
    bne normal_response
    mov ip,#2
    strb ip,[r0,#0x49]
    dmb ish
    pop {r0,ip,lr}
    ldr pc,=0xc0605240
normal_response:
    pop {r0,ip,lr}
    ldrb r3,[sp,#0x18]
    bx lr
.size response_gate,.-response_gate
.global show_probe
.type show_probe,%function
show_probe:
    push {r0-r3,r6,lr}
    mov r6,#52
    bl probe
    pop {r0-r3,r6,lr}
    ldr r3,=0x00e835e4
    ldr pc,=0xc0604f98
.size show_probe,.-show_probe
message:
    .asciz "<6>me302kl_ctrl_probe tx=%d state=%u (1=no reply,2=reply,3=no space)\n"
.balign 4
.ltorg
