# 第 5 篇 中断、延迟工作与时间

> 目标：理解硬件事件的异步处理链路（上半部/下半部）、内核线程与工作队列的分工，以及时间子系统怎么做到"空闲时不打 tick、需要时精确到纳秒"。

## 1. 中断的基本流程

```
设备触发（MSI-X 写内存 / 传统 INTx 拉线 / GPIO）
   → 中断控制器（x86: APIC/LAPIC，arm64: GIC）
   → CPU 在指令边界响应：关中断（清 IF）、压入返回现场、按 IDT 向量号跳转
   → entry_64.S 的 stub：保存寄存器成 pt_regs
   → common_interrupt() → irq_enter() → generic_handle_irq_desc()
        → 中断控制器驱动（如 x86 的 irq_matrix / GIC 的 irqchip）
        → 设备驱动注册的 handler（request_irq 的第二个参数）
   → irq_exit() → invoke_softirq()  ← 下半部在这里开始
   → iretq 返回被中断的代码
```

要点：

- **中断上下文没有进程上下文**：不能用 `current`（虽然 x86 上 `current` 名义上是被打断的任务，但语义上不是"你"），不能睡眠，不能调用 `copy_to_user`，不能拿 mutex。
- **`IRQF_*` 标志**：`IRQF_SHARED`（多个设备共享一条线，需要快速判断"是不是我的"）、`IRQF_ONESHOT`（线程化中断在线程跑完前保持中断线屏蔽，防止电平触发中断反复触发；只提供线程函数、不提供上半部时必须设置）、`IRQF_NO_THREAD`。
- **MSI/MSI-X** 是 PCIe 设备的主流方式：设备通过写一个特定地址（LAPIC）触发中断，不占用物理引脚、支持多向量（每个队列一个向量）→ 天然支持多队列网卡的每核中断。
- **中断亲和性**：`/proc/irq/<n>/smp_affinity`（位图）或 `smp_affinity_list`（CPU 列表）。高性能场景常配合 `RPS`（软件收包分发，见第 9 篇）和 `irqbalance`。

## 2. 上半部与下半部

| 机制 | 运行上下文 | 可睡眠 | 适用 |
|---|---|---|---|
| **hardirq（上半部）** | 中断上下文 | 否 | 必须极快：应答设备、把数据/描述符挂到队列、调度下半部 |
| **softirq** | 中断返回时或 `ksoftirqd` | 否 | 静态编号、对延迟敏感、高频（网络收发、块 I/O 完成、定时器、RCU、tasklet） |
| **tasklet** | 基于 softirq（`TASKLET_SOFTIRQ`） | 否 | 老的"延迟一点做"接口，正在被淘汰，新代码用 workqueue |
| **workqueue** | 内核线程（进程上下文） | **能** | 需要睡眠/拿 mutex/长时间运行的工作 |
| **threaded IRQ** | 内核线程 | **能** | 上半部只做 `request_threaded_irq` 的 handler 判断是否本设备，其余逻辑放线程 |

### softirq 编号（`include/linux/interrupt.h`）

`HI_SOFTIRQ`、`TIMER_SOFTIRQ`、`NET_TX_SOFTIRQ`、`NET_RX_SOFTIRQ`、`BLOCK_SOFTIRQ`、`IRQ_POLL_SOFTIRQ`、`TASKLET_SOFTIRQ`、`SCHED_SOFTIRQ`、`HRTIMER_SOFTIRQ`、`RCU_SOFTIRQ`。

softirq 是**每 CPU 一个位图**（`irq_cpustat_t.__softirq_pending`），同一编号在多个 CPU 上可并行、但同一 CPU 上不可重入。数量固定（编译期），不能用模块新增——这就是为什么新需求都转向 workqueue。

**`ksoftirqd/N`**：如果 softirq 处理时间超过 `MAX_SOFTIRQ_TIME`（2ms）或次数超过 `MAX_SOFTIRQ_RESTART`（10 轮），剩下的部分被挪到 `ksoftirqd` 内核线程里跑，避免中断上下文长时间占用（否则会造成调度延迟和 soft lockup）。`/proc/softirqs` 显示每 CPU 每编号的累计次数。

### workqueue

- **`system_wq`**（`schedule_work`）：通用队列，很多驱动共用，一个慢工作可能拖累同队列的其它工作。
- **自定义 workqueue**（`alloc_workqueue("name", flags, max_active)`）：建议驱动使用，避免互相干扰。
- 标志：`WQ_UNBOUND`（不受 CPU 亲和限制，由调度器决定在哪跑，适合可能长时间阻塞的工作）、`WQ_HIGHPRI`、`WQ_MEM_RECLAIM`（内存回收路径必需，防止死锁）、`WQ_SYSFS`（在 `/sys/bus/workqueue/` 下暴露可调参数）。
- 并发上限由 `max_active`（每 CPU 默认 256）与全局 worker 池共同决定；worker 线程 `kworker/uN:M` 与 `kworker/N:M` 在 `top -H` 里可见。
- **BH workqueue**（6.9 起）：在 softirq 上下文执行的 workqueue（`system_bh_wq`），用来逐步替代 tasklet，让"不能睡眠的延迟工作"也统一到 workqueue 接口下。

### 中断线程化（`CONFIG_PREEMPT_RT`）

RT 内核把所有中断处理都变成内核线程（`irq/N-name`），只保留极短的"硬"部分。这样中断处理可以被抢占，最坏延迟大幅下降。代价是每次中断多一层调度开销。

## 3. 定时与时间

### 3.1 时钟源与时钟事件

| 抽象 | 作用 | x86 实现 |
|---|---|---|
| **clocksource** | 提供单调递增的时间读数 | `tsc`（最快）、`hpet`、`acpi_pm` |
| **clockevent** | 提供"在未来某个时刻触发中断"的能力 | LAPIC timer、HPET、TSC deadline timer |

`clocksource` 有 `rating` 字段，内核选评分最高的；`/sys/devices/system/clocksource/clocksource0/` 可查看当前选择与被黑名单（`unstable` 的 TSC 会被降级）。

### 3.2 时间基准

| 时钟 | 语义 | syscall |
|---|---|---|
| `CLOCK_REALTIME` | 墙上时间，可被 `settimeofday`/NTP 调整（可回跳） | `clock_gettime` |
| `CLOCK_MONOTONIC` | 从启动起的单调时间，受 NTP 慢调整影响 | 同上 |
| `CLOCK_BOOTTIME` | 单调 + 包含 suspend 时间 | 同上 |
| `CLOCK_PROCESS/THREAD_CPUTIME` | CPU 时间 | 同上 |

- **jiffies**：以 `HZ`（`CONFIG_HZ`，通常 250 或 1000）递增的计数器，用于粗粒度定时（`schedule_timeout` 的粒度）。`wrap` 问题用 `time_after()`/`time_before()` 宏处理（不要直接比较大小）。
- **ktime_t**（纳秒，64 位）与 **timespec64** 是内核内部的标准时间类型；`ktime_get()` 基于 clocksource + `timekeeper` 的 seqcount 保护快照。
- **NTP/PTP**：在 `timekeeping` 里做频率和相位校正（`adjtimex`），`PTP` 硬件时钟通过 `phc2sys` 等用户态工具同步。内核提供 `SO_TIMESTAMPING` 给应用获取高精度收包时间戳。

### 3.3 定时器

| 接口 | 精度 | 上下文 | 说明 |
|---|---|---|---|
| `timer_list`（`timer_setup`/`add_timer`） | jiffies 级 | softirq | 老接口，仍广泛使用 |
| **hrtimer**（`hrtimer_start`） | 纳秒 | 硬中断或 softirq（`HRTIMER_MODE_SOFT`） | 高精度，红黑树按到期时间排序，配合 clockevent 编程 |
| `del_timer_sync` / `hrtimer_cancel` | — | 进程上下文 | 删除并等待正在运行的 callback 结束（防止 UAF） |
| POSIX timer（`timer_create`） | 纳秒 | 用户态 | 基于 hrtimer，可选 `SIGEV_THREAD_ID` 把信号发给指定线程 |
| `timerfd` | 纳秒 | 用户态 fd | 可放进 `epoll`，事件循环友好 |

**tickless（`NO_HZ_IDLE` / `NO_HZ_FULL`）**：空闲 CPU 停掉周期性 tick；`nohz_full` 让某些 CPU 连 tick 都不要，配合 `isolcpus` 做 CPU 隔离。`/sys/devices/system/cpu/nohz_full` 查看。

## 4. 驱动里正确的中断写法

```c
static irqreturn_t my_handler(int irq, void *dev_id)
{
    struct my_dev *d = dev_id;
    u32 status = readl(d->base + REG_STATUS);
    if (!(status & IRQ_PENDING))
        return IRQ_NONE;              /* 共享中断：不是我的，必须返回 NONE */
    writel(status, d->base + REG_ACK); /* 先应答，避免中断线被拉死 */
    queue_work(d->wq, &d->work);       /* 下半部：可睡眠的工作 */
    return IRQ_HANDLED;
}

ret = request_threaded_irq(irq, my_handler, my_thread_fn,
                           IRQF_SHARED | IRQF_ONESHOT, "mydev", d);
```

常见错误：

- 上半部里 `msleep`/`kmalloc(GFP_KERNEL)`/`mutex_lock` → 触发 `BUG: scheduling while atomic`。
- 忘记 ack → 中断风暴（`irq N: nobody cared`）。
- `free_irq` 前忘记 `del_timer_sync`/`cancel_work_sync` → 使用已释放内存。
- 在中断里唤醒进程用 `wake_up_interruptible` 是**可以**的（它本身可在中断上下文调用）。

## 5. 与中断相关的故障排查

| 现象 | 排查手段 |
|---|---|
| 中断风暴、CPU 100% 在 `si`/`hi` | `watch -n1 'grep -E "CPU|mydev" /proc/interrupts'`；`cat /proc/softirqs` |
| 中断分不到核，全堆在 CPU0 | `cat /proc/interrupts` 看每 CPU 计数；调 `smp_affinity_list`，或启用多队列 + `RPS` |
| 网络/块设备抖动、延迟尖峰 | `perf sched latency`；`bpftrace` 统计 `softirq` 到 `ksoftirqd` 的分布 |
| 时钟漂移 | `chronyc tracking`；`cat /sys/devices/system/clocksource/clocksource0/current_clocksource` |
| 硬死锁（soft lockup / hard lockup） | `lockup_detector`：`/proc/sys/kernel/watchdog`，panic 时出 backtrace；`hardlockup` 靠 NMI/perf 采样实现 |
| 中断耗时 | `perf record -g -e irq:softirq_entry` 或 ftrace 的 `irq_handler_entry/exit` tracepoint |

## 6. 关键文件

| 路径 | 内容 |
|---|---|
| `kernel/irq/` | 通用中断子系统：`manage.c`（`request_irq`/`free_irq`）、`chip.c`（irqchip 抽象）、`desc.c` |
| `kernel/softirq.c` | softirq、tasklet、`ksoftirqd` |
| `kernel/workqueue.c` | workqueue 与 worker 池 |
| `arch/x86/kernel/apic/` | LAPIC/IOAPIC 驱动 |
| `kernel/time/` | `timekeeping.c`、`hrtimer.c`、`timer.c`、`tick-*.c`、`clocksource.c` |
| `include/linux/interrupt.h` | `request_irq`、`IRQF_*`、softirq 编号 |

## 小结

异步事件的处理是一个**"尽快脱身、分级延后"**的分层结构：hardirq 只做到"应答 + 记录 + 排队"，softirq 做不允许睡眠的高频搬运，workqueue/线程化中断做需要睡眠的复杂逻辑。时间子系统则是"最快的时钟源 + 可编程的一次性时钟事件 + 按需唤醒"的组合，tickless 与 `nohz_full` 是对调度延迟与能耗的直接优化。
