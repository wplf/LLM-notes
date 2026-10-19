# 第 2 篇 系统调用与内核入口

> 目标：用户态的一行 `read()` 到底怎么变成内核里的一次函数调用，又怎么安全地回到用户态。

## 1. 四种"进入内核"的方式

| 方式 | 触发 | 是否同步 | 典型用途 |
|---|---|---|---|
| 系统调用（syscall） | 软件指令（x86-64: `syscall`） | 同步，返回到下一条指令 | 主动请求服务 |
| 异常（exception） | CPU 执行指令出错（缺页、除零、非法指令、调试断点） | 同步 | 缺页处理、`int3`、信号投递 |
| 硬件中断（IRQ） | 外部设备 | 异步 | 网卡收包、定时器 |
| 陷入式虚拟化（VM exit） | 虚拟机中的敏感操作 | 同步 | 由 hypervisor 处理 |

系统调用是唯一**由程序主动发起、有明确定义语义**的入口，因此它是内核的"官方 API"。

## 2. x86-64 上的系统调用全过程

### 2.1 用户态侧

C 库把系统调用封装成普通函数。以 `read` 为例，寄存器约定（`arch/x86/entry/entry_64.S`）：

| 寄存器 | 含义 |
|---|---|
| `rax` | 系统调用号（如 `read` = 0），返回值也放这里 |
| `rdi, rsi, rdx, r10, r8, r9` | 第 1～6 个参数（注意第 4 个是 `r10`，不是 `rcx`） |
| `rcx` / `r11` | 被 `syscall` 指令用来存返回地址 / RFLAGS，不作为参数 |
| 第 7 个及以后 | 通过栈传递（极少用，如 `mmap` 是 6 参数刚好） |

```asm
; musl/glibc 里 read() 的实际形态（示意）
mov  $0, %eax          ; __NR_read
syscall                ; 进入内核；返回后 rax = 结果或 -errno
cmp  $-4095, %rax
jae  .Lerror           ; -errno 范围：-1 ~ -4095
```

`syscall` 指令做三件事：把 `rip` 存到 `rcx`、把 `rflags` 存到 `r11`、跳到 MSR `LSTAR`（由内核启动时写入 `entry_SYSCALL_64`），按 MSR `FMASK` 清掉 RFLAGS 中的位（Linux 在其中设置了 IF，所以进入时中断已被硬件关闭），同时把权限级从 ring 3 变成 ring 0。**它不会切换栈**——切栈是内核入口代码立刻做的事（先把用户 `rsp` 暂存到 per-CPU 区域，再从 `cpu_current_top_of_stack` 载入内核栈）。

> 传统 `int 0x80` 仍支持（32 位 ABI，参数用 `ebx/ecx/edx/esi/edi/ebp`），但慢得多（要过 IDT，做完整的硬件中断流程），现代程序不用。

### 2.2 内核入口汇编：`entry_SYSCALL_64`

`arch/x86/entry/entry_64.S` 做的事情（简化）：

1. `swapgs`：把 GS 基址切换到内核的 per-CPU 数据（此时中断已由 `FMASK` 关闭）；开启 KPTI 时还要切换到内核页表（CR3）。
2. 切到内核栈，构造一个 `pt_regs` 结构，保存用户态的通用寄存器。
3. 进入 C 代码后再按需开中断。
4. 跳到 `do_syscall_64(regs, nr)`。

### 2.3 C 层分发

```c
/* arch/x86/entry/common.c（简化） */
__visible void do_syscall_64(struct pt_regs *regs, unsigned long nr)
{
    nr &= __SYSCALL_MASK;
    if (likely(nr < NR_syscalls)) {
        nr = array_index_nospec(nr, NR_syscalls);   /* 阻止推测执行越界 */
        regs->ax = sys_call_table[nr](regs);        /* 函数指针表分发 */
    }
    syscall_exit_to_user_mode(regs);                /* 检查信号/需否重新调度等 */
}
```

`sys_call_table` 由 `arch/x86/entry/syscalls/syscall_64.tbl` 生成。表的形状本身是安全隐患（Spectre），所以有 `array_index_nospec`。

### 2.4 定义系统调用的现代写法

不再手写 `asmlinkage long sys_read(...)`，而是用宏：

```c
/* fs/read_write.c */
SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, size_t, count)
{
    struct fd f = fdget_pos(fd);
    ...
}
```

`SYSCALL_DEFINEn(name, type1, arg1, ...)` 展开出 `__x64_sys_read`（接收 `pt_regs`，取出寄存器参数）→ `__se_sys_read`（做符号扩展）→ `__do_sys_read`（真正的函数体）三层包装，并生成 `sys_call_table` 条目与 `syscalls/sys_enter_read` 追踪点。所有系统调用都有对应的 tracepoint，这是 `strace`/ftrace/eBPF 能观测它们的基础。

### 2.5 返回值与错误

- 成功：返回非负值或 0。
- 失败：返回 `-errno`（如 `-EINVAL` = `-22`）。C 库看到 `-4095..-1` 范围就转成 `errno = -ret; return -1`。
- 内核内部函数则普遍**返回 `int` 并用负 errno 表示失败**，指针型返回值失败时用 `ERR_PTR(-ENOMEM)`，检查用 `IS_ERR()` / `PTR_ERR()`。

### 2.6 返回用户态

`syscall_exit_to_user_mode()` → `exit_to_user_mode_loop()` 依次检查：

1. `TIF_NEED_RESCHED`：需要抢占 → 走调度器（这也是 `TIF` 标志在返回路径被处理的原因）。
2. `TIF_SIGPENDING`：有未处理信号 → `do_signal()` 构造信号帧。
3. `TIF_NOTIFY_SIGNAL` / `TIF_NOTIFY_RESUME`：io_uring、`task_work` 等延后工作。
4. 最后执行 `sysretq`（或慢路径 `iretq`；若返回地址不是规范地址等情况必须走 `iretq`，否则会触发 Intel SYSRET 漏洞 CVE-2012-0217）恢复寄存器、`swapgs` 回用户 GS，回到用户态。

> 用户态程序被 `SIGSTOP`/`SIGKILL` 时"C 库函数不返回"就发生在这一步。

## 3. 异常、中断的入口与 `pt_regs`

- **IDT（中断描述符表）**：256 个门，0–31 是 CPU 异常，32–255 是外部中断/`int` 指令。每个门都指向 `entry_64.S` 里生成的一小段 stub（`idtentry` 宏），作用是"压入错误码/伪造错误码 → 保存寄存器成 `pt_regs` → 调用 C 处理函数"。
- **`pt_regs`**：进入内核时寄存器快照的固定布局（`arch/x86/include/asm/ptrace.h`）。它同时是：信号帧的模板、`ptrace` 调试器读写寄存器的接口、内核栈回溯（`unwind`）的起点。
- **内核栈**：x86-64 上每任务 `THREAD_SIZE` = 16KB（4 个 4KB 页，`CONFIG_THREAD_INFO_IN_TASK` 后 `thread_info` 放在 `task_struct` 里）。栈非常小，所以内核代码**禁止大局部数组**、深递归。
- **NMI** 走独立栈（IST，Interrupt Stack Table），防止栈溢出时无法处理。

## 4. vDSO：根本不进内核的系统调用

`gettimeofday`、`clock_gettime`、`time`、`getcpu` 这类调用极其频繁，但数据只是内核维护的共享内存。内核于是映射一页只读代码到每个进程（**vDSO**，`[vdso]` 在 `/proc/self/maps` 里可见）：

```
用户调用 clock_gettime()
  → glibc 检查是否存在 vDSO 符号 __vdso_clock_gettime
  → 直接读 vvar 页面里内核写好的时间数据（配合 seqcount 保证读写一致）
  → 完全不发生 syscall，不做模式切换
```

相关实现：`arch/x86/entry/vdso/`、`arch/x86/entry/vsyscall/`。这体现了一个重要模式：**热路径上把只读数据放进用户可读的共享页，用顺序锁保证一致性**。类似的还有 `rseq`（每线程数据，让 `sched_setaffinity` 类操作无锁）。

## 5. seccomp 与系统调用过滤

`seccomp(SECCOMP_SET_MODE_FILTER)` 允许进程为**自己及后代**安装一个 BPF 程序，对每次系统调用做检查。返回值决定：允许、返回错误码、`SECCOMP_RET_TRAP`（发 `SIGSYS`）、`SECCOMP_RET_TRACE`（交给 ptrace 的监视者）、`SECCOMP_RET_USER_NOTIF`（交给另一个进程裁决——容器运行时常用它来安全地实现 `mount` 之类的调用）。

实现点在系统调用入口（`__secure_computing`），每个进程的过滤器链保存在 `task_struct->seccomp` 中。它是容器安全的重要一层（见第 12 篇）。

## 6. 兼容性：32 位 ABI 与多架构

- x86-64 内核同时提供 32 位 ABI：`sys_call_table` 有 `ia32_sys_call_table`，`int 0x80` 与 `sysenter` 都支持；`CONFIG_IA32_EMULATION`。
- 结构体大小/对齐差异导致的坑（`time_t` 32 位、`stat` 布局不同）由 `compat_*` 系列函数处理（`fs/compat.c`、`include/linux/compat.h`）。
- 其它架构的机制：arm64 用 `svc #0`（`x8` 传调用号），RISC-V 用 `ecall`（`a7`）。分发层与 ABI 编号在 `include/uapi/asm-generic/unistd.h` 里统一（新架构都用 asm-generic 表）。
- **新调用一旦加入就永久保留**（哪怕设计有缺陷），删除它会破坏二进制兼容。已废弃或未实现的编号指向 `sys_ni_syscall`，返回 `-ENOSYS`，但编号永不复用。

## 7. 用户态可见的接口清单

| 接口 | 位置 | 用途 |
|---|---|---|
| 系统调用 | 见 `syscall_64.tbl`，约 400+ 个 | 主要 API |
| `/proc` | `fs/proc/` | 进程信息、内核参数（`/proc/sys/` 即 sysctl） |
| `/sys` | `fs/sysfs/` | 设备模型、驱动参数、内核对象属性 |
| `ioctl` | 各驱动 `unlocked_ioctl` | 设备专用命令（非通用，格式五花八门） |
| netlink | `net/netlink/` | 结构化双向消息（路由、防火墙、设备事件、审计） |
| `sysfs` 之外的 debugfs / tracefs | `fs/debugfs/`、`fs/tracefs/` | 调试与追踪接口 |
| eBPF | `bpf()` 系统调用 | 可编程扩展点（见第 13 篇） |

## 8. 关键文件

| 路径 | 内容 |
|---|---|
| `arch/x86/entry/entry_64.S` | `entry_SYSCALL_64`、所有 IDT stub |
| `arch/x86/entry/common.c` | `do_syscall_64`、`syscall_exit_to_user_mode` |
| `arch/x86/entry/syscalls/syscall_64.tbl` | 系统调用编号表（生成 `sys_call_table`） |
| `include/linux/syscalls.h` | `SYSCALL_DEFINEn` 宏 |
| `arch/x86/include/asm/ptrace.h` | `pt_regs` 布局 |
| `kernel/entry/common.c` | 通用退出路径、`TIF_*` 处理 |
| `kernel/seccomp.c` | seccomp 过滤 |
| `arch/x86/entry/vdso/` | vDSO 实现 |

## 小结

系统调用入口是一条被高度优化过的"窄门"：`syscall` 指令 → per-CPU 切栈 → `pt_regs` 快照 → 查表分发 → 业务函数 → 退出路径统一处理抢占和信号 → `sysretq`。热路径上还有 vDSO 这种"绕过内核"的旁路。所有可见的 syscall 都带 tracepoint，这让我们既能在用户态用 `strace` 看，也能在内核里用 ftrace/eBPF 按耗时和参数过滤统计。
