# Linux 内核整体设计（总览）

> 这是「Linux 内核整体设计与子系统详解」系列的总览篇。入门概念（用户态/内核态、五大子系统）见 [Linux 内核的构成（入门版）](linux-kernel-architecture.md)；本系列在此基础上讲**设计思想**和**每个子系统的内部细节**。
>
> 内容以 6.x 主线内核、x86-64 架构为主，文中涉及的版本号和数值请以实际内核版本为准。

## 系列目录

| 篇目 | 主题 | 核心问题 |
|---|---|---|
| [第 1 篇 启动与初始化](01-boot-and-init.md) | 固件 → 引导 → `start_kernel` → PID 1 | 内核是怎么跑起来的 |
| [第 2 篇 系统调用与内核入口](02-syscall-and-entry.md) | syscall、异常、vDSO | 用户态怎么进内核、怎么出来 |
| [第 3 篇 进程管理与调度](03-process-and-scheduling.md) | `task_struct`、fork/exec、调度类、EEVDF | 谁在 CPU 上跑 |
| [第 4 篇 内存管理](04-memory-management.md) | 页表、伙伴系统、SLUB、缺页、回收 | 内存怎么分、怎么映射、怎么回收 |
| [第 5 篇 中断、延迟工作与时间](05-interrupts-and-time.md) | 硬中断、softirq、workqueue、定时器 | 异步事件怎么处理 |
| [第 6 篇 并发与同步](06-synchronization.md) | 原子操作、自旋锁、mutex、RCU、内存屏障 | 多核下怎么不出错 |
| [第 7 篇 VFS 与文件系统](07-vfs-and-filesystems.md) | inode/dentry/file、page cache、ext4 | 文件抽象怎么实现 |
| [第 8 篇 块设备层与 I/O](08-block-layer-and-io.md) | bio、blk-mq、I/O 调度、io_uring | 读写怎么落到磁盘 |
| [第 9 篇 网络协议栈](09-networking-stack.md) | sk_buff、NAPI、TCP/IP、netfilter、XDP | 包怎么收发 |
| [第 10 篇 设备驱动模型](10-device-driver-model.md) | bus/device/driver、sysfs、设备树、DMA | 驱动怎么接入内核 |
| [第 11 篇 进程间通信与信号](11-ipc-and-signals.md) | pipe、信号、共享内存、futex | 进程之间怎么协作 |
| [第 12 篇 安全、命名空间与 cgroup](12-security-and-containers.md) | 权限、LSM、seccomp、namespace、cgroup | 隔离和访问控制 |
| [第 13 篇 观测与调试](13-tracing-and-debugging.md) | ftrace、kprobe、perf、eBPF | 怎么看清内核在做什么 |

---

## 1. 内核要解决的根本问题

一台机器上有多个程序共享**有限且异构**的硬件。内核要同时满足三个目标：

1. **复用（Multiplexing）**：CPU、内存、磁盘、网卡被很多程序共享，需要分时、分区复用。
2. **隔离（Isolation）**：一个程序不能读写别人的内存，不能独占 CPU，崩溃了也不能拖垮别人。
3. **抽象（Abstraction）**：把五花八门的硬件统一成进程、虚拟地址空间、文件、socket 等少量抽象。

Linux 的全部设计，基本都可以看成是在**性能、通用性、可维护性**之间为这三个目标做的取舍。

## 2. 分层视图

```
              用户程序 / glibc / musl
──────────────────────────────────────────────────────  系统调用 ABI（稳定，不破坏用户态）
  系统调用分发层 (entry_64.S → do_syscall_64 → sys_call_table)
┌─────────────────────────────────────────────────────┐
│ 进程/调度   内存管理   VFS        网络栈     IPC       │  通用子系统（与硬件无关）
│ kernel/    mm/        fs/        net/       ipc/      │
│              │         │ 具体文件系统 │ 协议族          │
│              │         ▼            ▼                 │
│              │      块设备层 block/  网络设备层          │  通用设备框架
│              ▼         ▼            ▼                 │
│        设备驱动模型 (drivers/base) + 各类驱动 drivers/  │  驱动
├─────────────────────────────────────────────────────┤
│ 架构相关层 arch/<x86|arm64|riscv>：启动、页表、中断、    │  硬件相关
│ 上下文切换、原子指令、系统调用入口                       │
└─────────────────────────────────────────────────────┘
                       硬件
```

关键点：

- **上层通用、下层专用**。调度器、VFS、TCP 协议都不关心 CPU 是 x86 还是 ARM；与具体硬件相关的部分被压缩到 `arch/` 和 `drivers/`。
- **两条稳定性规则不同**：
  - 用户态 ABI（系统调用、`/proc`、`/sys` 的语义）**承诺永不破坏**——"We do not break userspace"。
  - 内核内部 API（函数签名、结构体）**完全不稳定**，随时可以改。改接口的人负责把树内所有调用者一起改掉。这也是 Linux 鼓励驱动进入主线（in-tree）、不提供稳定驱动 ABI 的原因。

## 3. 核心设计决策

### 3.1 宏内核 + 可加载模块

所有子系统运行在同一地址空间、同一特权级，子系统之间是**直接函数调用**，没有消息传递开销。代价是任何一处内存越界都可能破坏整个内核。

模块（`.ko`）只是"延迟链接"：加载后与内核其它代码完全平等，没有隔离。模块只能使用内核用 `EXPORT_SYMBOL` / `EXPORT_SYMBOL_GPL` 导出的符号。

| 方案 | 代表 | 优点 | 缺点 |
|---|---|---|---|
| 宏内核 | Linux、FreeBSD | 快，子系统间可深度优化（如零拷贝、page cache 共享） | 故障域大，单点 bug 致命 |
| 微内核 | seL4、QNX、Minix 3 | 隔离好，可形式化验证 | IPC 开销大，性能调优难 |
| 混合内核 | Windows NT、XNU | 折中 | 边界模糊 |

Linux 也在吸收微内核的一部分思路，例如 FUSE（用户态文件系统）、UIO/VFIO（用户态驱动）、eBPF（在受校验的沙箱里扩展内核）。

### 3.2 "面向对象"的 C：操作表（ops table）

内核用 C 写，但大量使用**函数指针表**实现多态。这是理解 Linux 源码最重要的一种模式：

```c
/* 简化示意：VFS 不知道具体文件系统，只调用 file->f_op->read_iter */
struct file_operations {
    ssize_t (*read_iter)(struct kiocb *, struct iov_iter *);
    ssize_t (*write_iter)(struct kiocb *, struct iov_iter *);
    int     (*mmap)(struct file *, struct vm_area_struct *);
    int     (*open)(struct inode *, struct file *);
    /* ... */
};
```

同样的模式随处可见：

| 抽象 | 操作表 | 实现者 |
|---|---|---|
| 文件 | `file_operations`、`inode_operations` | ext4、xfs、procfs、字符设备驱动 |
| 调度策略 | `sched_class` | fair、rt、deadline、idle |
| 网络协议 | `proto_ops`、`proto` | TCP、UDP、Unix socket |
| 网卡 | `net_device_ops` | 各网卡驱动 |
| 总线上的驱动 | `struct device_driver` 的 probe/remove | PCI、USB、platform 驱动 |

配合 `container_of()` 宏（由内嵌成员的指针反推外层结构体），就得到了"继承"：

```c
struct ext4_inode_info {
    /* ext4 私有字段 ... */
    struct inode vfs_inode;      /* 内嵌通用 inode = "基类" */
};
#define EXT4_I(inode) container_of(inode, struct ext4_inode_info, vfs_inode)
```

### 3.3 机制与策略分离

内核提供**机制**，尽量把**策略**交给用户态或可配置参数：

- 内核提供 cgroup 接口，限多少资源由 systemd / Kubernetes 决定。
- 内核提供 netfilter 钩子，防火墙规则由 nftables 下发。
- 内核提供 uevent，设备节点命名由 udev 决定。
- 调度器、I/O 调度器、TCP 拥塞控制都是可插拔的，并有大量 sysctl 参数。

### 3.4 一切皆文件（以及它的边界）

设备、进程信息、内核参数都通过文件接口暴露：`/dev`（设备）、`/proc`（进程与杂项）、`/sys`（设备模型与内核对象）、`/sys/kernel/tracing`（追踪）。

这个抽象并不完美：socket 需要 `bind`/`connect` 等专用调用，设备控制常常要靠 `ioctl`。新接口越来越多地采用**文件描述符化**（fd-based）的设计：`eventfd`、`signalfd`、`timerfd`、`pidfd`、`io_uring`、`bpf` 对象都以 fd 表示，从而能统一放进 `epoll` 里等待。

### 3.5 性能优先的数据结构

- **Per-CPU 数据**：每个 CPU 一份，避免加锁和缓存行争用（运行队列、页分配器的 per-CPU 页列表、统计计数）。
- **RCU**：读多写少场景下读者完全无锁（路由表、文件描述符表、进程链表）。
- **侵入式数据结构**：`list_head`、`hlist`、`rb_tree`、`xarray`、`maple tree` 都嵌入在宿主结构体中，不额外分配节点。
- **缓存**：page cache、dentry cache、inode cache、slab 对象缓存，尽量让热路径不访问磁盘、不调用通用分配器。

## 4. 执行上下文：代码"在哪种身份下"运行

这是写内核代码最容易出错的地方。同一段函数，在不同上下文中能做的事情完全不同：

| 上下文 | 何时出现 | 有 `current` 进程吗 | 能睡眠吗 | 典型代码 |
|---|---|---|---|---|
| 进程上下文（用户线程陷入） | 系统调用、缺页异常 | 有，就是调用者 | 能 | `sys_read`、`do_page_fault` |
| 内核线程 | `kthreadd` 创建的线程 | 有，但没有用户地址空间 | 能 | `kswapd`、`ksoftirqd`、worker |
| 硬中断上下文 | 设备中断、IPI | 被打断的那个，不能用 | **不能** | 中断处理函数 top half |
| 软中断上下文 | 硬中断退出时 / ksoftirqd | 同上 | **不能** | 网络收包、定时器回调、tasklet |
| NMI | 不可屏蔽中断 | 不能用 | **不能**，连普通锁都不能拿 | perf 采样、看门狗 |

一条经验规则：**持有自旋锁、关中断或处于原子上下文时，不能调用任何可能睡眠的函数**（如 `mutex_lock`、`kmalloc(GFP_KERNEL)`、`copy_from_user`）。`CONFIG_DEBUG_ATOMIC_SLEEP` 能在运行时检查这类错误。

## 5. 各子系统如何拼在一起

以"一个 HTTP 服务器从磁盘读文件并通过网络发出去"为例：

```
nginx 线程
  │ sendfile(sock_fd, file_fd, ...)              ── 第 2 篇：系统调用入口
  ▼
VFS：fd → struct file → f_op                       ── 第 7 篇
  │ 先查 page cache（mm）                          ── 第 4 篇
  │ 未命中 → ext4 计算块号 → submit_bio            ── 第 8 篇：块层
  │          → NVMe 驱动提交命令 → 线程睡眠          ── 第 3 篇：调度
  │          → 磁盘完成 → MSI-X 中断 → 唤醒线程      ── 第 5 篇：中断
  ▼
网络栈：page 直接挂到 sk_buff（零拷贝）             ── 第 9 篇
  │ TCP 分段 → IP → qdisc → 网卡驱动 → DMA 发送      ── 第 10 篇：驱动/DMA
  ▼
全程：锁和 RCU 保护共享数据                        ── 第 6 篇
      cgroup 记账 CPU/内存/IO，LSM 做权限检查        ── 第 12 篇
```

## 6. 配置、构建与源码组织

- **Kconfig**：上万个配置项（`CONFIG_*`）决定编译哪些功能，每项可选 `y`（编进内核）、`m`（编成模块）或 `n`。`make menuconfig` 编辑，结果写入 `.config`。
- **Kbuild**：每个目录的 `Makefile` 写 `obj-$(CONFIG_FOO) += foo.o`，配置直接决定参与编译的文件。
- 产物：`vmlinux`（带符号的 ELF）、`arch/x86/boot/bzImage`（压缩后可引导的镜像）、`*.ko` 模块。
- 语言：以 C（GNU C11 方言）为主，少量汇编；6.1 起合入 Rust 支持基础设施，目前主要用于部分新驱动。

## 7. 开发流程（简要）

- **约 9～10 周一个版本**：2 周合并窗口（merge window）后发布 `-rc1`，之后每周一个 rc，通常到 `-rc7` 或 `-rc8` 后正式发布。
- **层级维护者**：补丁发到邮件列表 → 子系统维护者树 → `linux-next` 集成测试 → Linus 合并。`MAINTAINERS` 文件记录每个目录的负责人，`scripts/get_maintainer.pl` 可自动查询。
- **stable / LTS**：修复补丁回移到稳定分支；每年最后一个主线版本通常成为 LTS。

## 8. 阅读源码的建议

1. 从**数据结构**入手而不是函数：`task_struct`、`mm_struct`、`vm_area_struct`、`page`/`folio`、`inode`、`dentry`、`file`、`sk_buff`、`device`。理解了它们之间的指针关系，就理解了一大半设计。
2. 从**系统调用入口**往下追：`SYSCALL_DEFINE3(read, ...)` 在 `fs/read_write.c`。
3. 找**操作表**的赋值点，就知道多态调用最终落到哪个实现。
4. 工具：<https://elixir.bootlin.com> 在线跳转；本地用 `make tags` / `cscope` / clangd（`scripts/clang-tools/gen_compile_commands.py` 生成 `compile_commands.json`）；运行时用 ftrace 的 `function_graph` 直接看调用树（见第 13 篇）。

## 结论

Linux 是一个**宏内核**：用**分层**把硬件相关代码压到底部，用**操作表 + `container_of`** 在 C 里实现多态，用 **per-CPU、RCU、各种缓存**换取多核性能，并坚持**用户态 ABI 稳定、内核内部 API 自由演进**。后续各篇按子系统展开这些设计在具体代码中的形态。
