# 第 1 篇 启动与初始化

> 目标：搞清楚从上电到 shell 出现之间，内核自己做了什么、又把控制权交给了谁。

## 1. 全景流程

```
上电复位
 │
 ├─ BIOS / UEFI 固件：POST、初始化内存、枚举设备
 │      · BIOS：读 MBR（512B）→ bootloader 的第一阶段
 │      · UEFI：直接加载 \EFI\BOOT\BOOTX64.EFI（PE 格式），提供 Boot Services / Runtime Services
 │
 ├─ bootloader（GRUB2 / systemd-boot / U-Boot）
 │      · 读取 /boot/vmlinuz-*（bzImage，压缩的内核）
 │      · 从文件系统里把 initramfs（/boot/initrd.img-*）加载到内存
 │      · 填充 boot_params 结构，把内核命令行（cmdline）与 initrd 地址传给内核
 │      · 跳转到内核入口：arch/x86/boot/header.S 的 startup_32
 │
 ├─ 内核自解压（arch/x86/boot/compressed/）：解压到高地址，转向 startup_64 → 进入 C 代码
 │
 ├─ init/main.c: start_kernel()   ← 真正意义上的"内核开始运行"
 │      逐层调用初始化函数（见第 3 节）
 │
 ├─ rest_init()：
 │      · kernel_thread(kernel_init)  → PID 1
 │      · kernel_thread(kthreadd)     → PID 2（所有内核线程之母）
 │      · 调用 cpu_startup_entry(CPUHP_ONLINE) → 当前 CPU 变成 idle 线程
 │
 └─ PID 1 (kernel_init)：
        ① 若存在 initramfs：执行 /init（rootfs），由它加载存储驱动、挂载真实根文件系统，
           再 switch_root 到真实根并重新执行 /sbin/init
        ② 执行 ramdisk_execute_command / execute_command / /sbin/init / /etc/init.d/rcS ...
        ③ 一个都没成功 → kernel panic
```

## 2. bootloader 与内核之间的契约

bzImage 头部（`arch/x86/boot/header.S` 里的 `boot_header`）规定了内核期望的加载方式：

- **实模式/保护模式入口**：`startup_32`，由 bootloader 设置 `%esi` 指向 `boot_params`。
- **`boot_params`**（`arch/x86/include/uapi/asm/bootparam.h`）：记录 cmdline 指针、initrd 地址与大小、e820 内存映射（物理内存布局）、EFI 系统表指针、屏幕参数等。
- **内核命令行**：`console=ttyS0`、`root=UUID=...`、`quiet`、`init=/bin/bash`、`mem=4G`、`maxcpus=1`、`mitigations=off` 等，解析代码在 `init/main.c` 的 `setup_command_line` 与各 `__setup()` / `early_param()` 宏注册的函数里。

> 调试启动问题的常用手段：加 `earlyprintk=serial,ttyS0,115200`、去掉 `quiet`、`loglevel=8`、`initcall_debug`（打印每个 initcall 的耗时）。

## 3. `start_kernel()` 做了什么

`init/main.c` 的 `start_kernel()` 是核心初始化序列，顺序有严格依赖，大致可分为几段：

| 阶段 | 代表性调用 | 说明 |
|---|---|---|
| 早期架构初始化 | `setup_arch()` | 解析 `boot_params`、建立最早的页表、初始化内存模型（e820）、ACPI/设备树 |
| 基础环境 | `trap_init`、`mm_init`、`sched_init`、`rcu_init` | 建立异常向量、页分配器与 `kmem_cache`、运行队列、RCU |
| 中断与时间 | `early_irq_init`、`init_IRQ`、`time_init`、`tick_init` | 中断控制器、clocksource/clockevent、tick 设备 |
| 各类基础设施 | `vfs_caches_init`、`fork_init`、`proc_caches_init`、`signals_init` | VFS 缓存（inode/dentry）、进程相关缓存 |
| `rest_init()` | 创建 PID 1/2，变身 idle | 见上图 |

### 初始化函数分级：`initcall` 机制

大量子系统不用在 `start_kernel` 里逐个手写调用，而是注册宏，由链接器按级别排好序：

```c
static int __init e1000_init_module(void) { ... return pci_register_driver(&e1000_driver); }
module_init(e1000_init_module);        /* 编进内核时 → device_initcall；编成模块时 → 加载时调用 */
```

级别顺序（`include/linux/init.h`）：`early_initcall` → `pure_initcall` → `core_initcall` → `postcore_initcall` → `arch_initcall` → `subsys_initcall` → `fs_initcall` → `device_initcall` → `late_initcall`。

- 这些函数放在 `.initcall.init` 段；启动完成后，`free_initmem()` 会把 `.init.*` 段整块释放，回收可观的内存。
- `__init` / `__initdata` 标记的代码/数据只在初始化期有效，启动日志中的 `Freeing unused kernel image (initmem) memory` 就是在释放它们，之后再访问就是非法访问。

## 4. initramfs：为什么需要

真实根文件系统可能在 RAID、LUKS 加密卷、NVMe、NFS 上，驱动可能只是模块。于是用一个内存文件系统做"跳板"：

1. bootloader 把 `initrd.img`（现代是 **cpio + gzip/zstd 压缩的 initramfs**）放进内存。
2. 内核把它解压成一个 `tmpfs`（rootfs），内容就是 initramfs 里的目录树。
3. 执行里面的 `/init`（一般由 dracut / initramfs-tools / mkinitcpio 生成）：
   - 加载 `modules.dep` 里必需的模块（存储、加解密、文件系统）
   - udev 建立 `/dev` 节点、解析 `root=UUID=...`
   - 挂载真实根到 `/sysroot`，`mount --move` 关键挂载点，`switch_root` 切换并 `exec` 真实 init
4. 内存中的 tmpfs 释放。

## 5. PID 1 与 PID 2

| 进程 | 内核视角 | 用户态视角 |
|---|---|---|
| PID 0 | `swapper`/`idle`：静态定义的 `init_task`（启动 CPU）及每个 CPU 各自的 idle 任务，只在无事可做时运行 | 看不到 |
| PID 1 | `kernel_init` 内核线程，最后 `execve` 成用户态 init | `/sbin/init`（systemd 等） |
| PID 2 | `kthreadd` | 不可见（在 `top` 中按 `I`/`H` 可见）；它 fork 出 `kworker`、`kswapd`、`ksoftirqd`、`migration/N` 等 |

PID 1 的几项特权（这些行为定义了 PID 1 的地位，也解释了为什么容器里的 PID 1 行为怪异）：

- 被内核视为孤儿进程的最终收养者（`reparent` 到 PID 1 或其 `subreaper`）。
- **没有默认信号处理**：内核不会对 PID 1 施加 `SIGKILL`/`SIGSTOP` 等，除注册了处理函数的信号外一律忽略。所以容器里 PID 1 不处理 `SIGTERM` 时 `docker stop` 会等到超时。
- PID 1 退出会导致内核 panic（`Attempted to kill init!`）；容器里则是该 PID 命名空间内的所有进程被杀掉。

## 6. 用户态初始化

PID 1 启动后的用户态链条：

```
systemd（或 sysvinit / OpenRC）
  ├─ 挂载 /proc /sys /dev /dev/pts /run（cgroup2 在 /sys/fs/cgroup）
  ├─ 启动 udev（内核发 uevent → udev 创建 /dev 节点、加载驱动、设置权限）
  ├─ 启动 dbus、journald、networkd/NetworkManager、sshd...
  └─ 进入默认 target（multi-user.target / graphical.target）
```

内核侧的 `uevent` 机制：设备注册时通过 netlink 广播一个设备事件包，udevd 收到后匹配规则（`/usr/lib/udev/rules.d/*.rules`），决定设备名、符号链接、权限、要加载的模块、要执行的程序。这是"内核只报事实、用户态定策略"的典型例子。

## 7. 关停与崩溃

- 正常关机：由 systemd 等 init 先停止服务、向剩余进程发 `SIGTERM`/`SIGKILL`、`sync` 并卸载或只读重挂文件系统，最后调用 `reboot()` 系统调用。
- `reboot()`（`kernel/reboot.c`）：`kernel_restart()` / `kernel_power_off()` 依次通知 reboot notifier、调用各设备的 `shutdown` 回调、下线其它 CPU，最后经 `machine_restart` / `machine_power_off`（ACPI、键盘控制器、EFI 等方式，可用 `reboot=` 指定）复位或断电。
- **panic**：内核处于不可继续状态。行为由 `panic=`、`panic_on_oops`、`panic_timeout` 控制，可配置自动重启（服务器上常见）、kdump 转储 vmcore。
- **oops**：检测到非法操作但还能继续，杀掉当前进程、打印寄存器与栈回溯，内核状态可能已被污染（`tainted`）。
- **kdump**：预保留一块 `crashkernel=` 内存，panic 时引导**第二个内核**（kexec）进入该内存，把第一个内核的内存镜像写成 `/var/crash/vmcore`。

## 8. 关键文件

| 路径 | 内容 |
|---|---|
| `arch/x86/boot/header.S` | bzImage 头部与实模式入口 |
| `arch/x86/boot/compressed/head_64.S` | 自解压 stub |
| `arch/x86/kernel/setup.c` | `setup_arch()`：e820、ACPI、initrd 解析 |
| `init/main.c` | `start_kernel`、`rest_init`、`kernel_init`、cmdline 解析 |
| `include/linux/init.h` | `__init`、`module_init` 等宏定义 |
| `kernel/reboot.c` | 重启/关机/panic 流程 |
| `init/initramfs.c` | initramfs 解包（cpio） |

## 小结

启动过程本质是一条**逐步把设施点亮**的长链：固件负责最基本的硬件，bootloader 负责装载镜像并传递参数，`start_kernel` 按依赖顺序初始化内核各子系统，`initcall` 机制让每个子系统自己注册初始化函数，最后 PID 1 把世界交给用户态。理解这条链的价值在于：任何一个子系统初始化失败（例如驱动 probe 报错、根文件系统认不出来），你都能在启动 log 里对应到具体阶段，并用 `earlyprintk`、`initcall_debug`、`dmesg` 逐段排查。
