# 第 13 篇 观测与调试

> 目标：把内核提供的观测手段分层理清——从 `dmesg` 到 ftrace、perf、eBPF，以及它们各自能回答什么问题、代价多大。

## 1. 观测手段的分层

```
最轻量        日志（dmesg / printk）          只能看"作者想让你看的"
              计数器（/proc、/sys、tracepoint 计数）
              tracepoint / static key         ~几十 ns 一次
              kprobe / uprobe（动态插桩）      ~几百 ns 到 μs
              函数图追踪（ftrace function_graph）  开销大，但能看调用树
              事件采样（perf）                 按频率采样
最重          完整指令级 trace（Intel PT）     极大开销
```

选择原则：**先看计数器，再看 tracepoint，最后才动态插桩**；能在用户态定位就不要动内核。

## 2. 日志：printk 与 pstore

- `printk()` 写入环形缓冲区（`__log_buf`，大小 `CONFIG_LOG_BUF_SHIFT`），`dmesg`/`/dev/kmsg`/journald 读取。
- 级别 `KERN_EMERG`(0) ~ `KERN_DEBUG`(7)，`console_loglevel` 决定哪些同时打到控制台（`/proc/sys/kernel/printk` 的四个数）。
- 格式化：`pr_info`、`dev_info(&pdev->dev, ...)`（自动带设备前缀）、`pr_fmt` 宏。
- **动态调试**（`CONFIG_DYNAMIC_DEBUG`）：`dev_dbg` 默认零开销（编译成 `nop`，由 static key 控制），可运行时按文件/函数/行号打开：

```bash
echo 'file drivers/net/* +p' > /sys/kernel/debug/dynamic_debug/control
echo 'func my_probe +pfl' > /sys/kernel/debug/dynamic_debug/control   # p=启用 f=函数 l=行号 m=模块名
```

- **pstore**：panic 后把日志留在 `/sys/fs/pstore/`（EFI 变量、ACPI ERST、RAMoops）。
- 内核日志格式：`[时间戳] [级别] [可选：CPU/PID/命令/设备] 消息`。

## 3. ftrace：内置的追踪框架

位于 `/sys/kernel/tracing`（或 `/sys/kernel/debug/tracing`）。**零额外依赖，几乎任何内核都可用**。

### 3.1 核心文件

| 文件 | 作用 |
|---|---|
| `available_tracers` | 可用 tracer：`function`、`function_graph`、`nop`、`hwlat`、`osnoise`、`mmiotrace`、`wakeup*` |
| `current_tracer` | 当前 tracer |
| `set_ftrace_filter` / `set_ftrace_notrace` | 只追踪哪些函数（支持 `*` 通配，`module:func`） |
| `set_graph_function` | function_graph 的根函数（只展开它以下的调用） |
| `available_filter_functions` | 可追踪函数列表（近十万条） |
| `trace` | 文本输出 |
| `trace_pipe` | 流式输出（读取即消费，可 `cat` 到管道） |
| `events/` | 所有 tracepoint，可按子系统/事件开关与过滤 |
| `instances/` | 创建多个独立实例，各自配置（多用户/多场景并行） |
| `tracing_on` | 总开关 |
| `options/` | `func_stack_trace`、`record-cmd`、`sym-addr`、`irq-info`、`latency-format` 等 |

### 3.2 常用姿势

```bash
# 1) 看某函数的调用栈（谁调用了它）
echo 'schedule' > set_ftrace_filter
echo 1 > options/func_stack_trace
echo function > current_tracer

# 2) 看某函数的调用树与耗时
echo 'do_page_fault' > set_graph_function
echo function_graph > current_tracer
cat trace

# 3) 只追踪某个 tracepoint，并按参数过滤
echo 1 > events/sched/sched_switch/enable
echo 'prev_comm == "nginx"' > events/sched/sched_switch/filter

# 4) 直方图（注意需要 hist 触发器支持）
echo 'hist:keys=call_site:vals=hitcount' > events/kmem/kmalloc/trigger

# 5) 最大延迟（max latency）
echo 0 > tracing_max_latency
echo irqsoff > current_tracer    # 或 preemptoff / wakeup_rt
```

**`function_graph` 输出示例**（缩进表示深度，`;` 后是耗时 μs）：

```
 0)  nginx-1234  |   0.512 us    |  copy_user_enhanced_fast_string();
 0)  nginx-1234  |               |  do_sys_openat2() {
 0)  nginx-1234  |               |    getname_flags() {
 0)  nginx-1234  |   0.187 us    |      kmem_cache_alloc();
```

**底层机制**：编译期用 `-pg`/`-mfentry` 在每个函数入口放一个 `nop`，启用时改成跳转到 trampoline（`ftrace_caller`）。**dynamic ftrace** 保证未启用时零成本；`CONFIG_FUNCTION_TRACER` 打开后仍有轻微的代码尺寸与分支预测影响。

**tracepoint** 是作者预埋的静态钩子（`TRACE_EVENT` 宏生成），开销只有 static key 检查，且能把结构化字段写进 trace 缓冲区（支持过滤、触发、直方图）。**这是优先使用的观测点**。

## 4. kprobe / kretprobe / uprobe

```bash
# 在任意函数入口插桩（x86 上把指令首字节替换为 int3）
echo 'p:myprobe do_sys_open file=%di flags=%si' >> kprobe_events
echo 1 > events/kprobes/myprobe/enable

# 返回值探针
echo 'r:myret do_sys_open ret=$retval' >> kprobe_events

# 用户态函数（按 ELF 符号或偏移）
echo 'p:my_uprobe /usr/bin/nginx:0x1234' >> uprobe_events
```

- **kprobe** 会临时改写代码（`int3` → 单步执行原指令），开销较大；热点函数上大规模使用会显著影响性能。
- **fentry/fexit**（基于 ftrace 的 BPF 挂载点）比 kprobe 快得多，是现代 eBPF 追踪的首选。
- 内联函数、被编译器优化的参数（`%di` 可能已不存在）会让探针取不到期望值——这时要去看汇编或改用 tracepoint。

## 5. perf：采样与计数

```bash
perf stat -e cycles,instructions,cache-misses,branch-misses ./app
perf top                                  # 全局热点函数
perf record -F 999 -g --call-graph dwarf -p <pid>   # 采样并记录调用栈
perf report --stdio
perf trace -e 'syscalls:sys_enter_read' -- sleep 1   # 系统调用追踪
perf sched latency                        # 调度延迟
perf mem record / perf c2c record         # 内存访问与缓存行争用
perf lock                                 # 锁争用
perf stat -a -e 'uncore_imc/cas_count_read/'   # PMU 计数器
```

- 依赖 **PMU（性能监控单元）** 的硬件事件：周期、指令、缓存缺失、分支预测失败、`uncore`（内存控制器、QPI/UPI）。
- **数据来源**：`perf_events` 子系统（`kernel/events/core.c`），支持按时间频率采样、精确事件（PEBS/IBS，能记录出错的指令地址）、`--call-graph dwarf`（用用户态栈展开）、`BPF` 程序挂到事件上做过滤与聚合。
- `perf_event_paranoid`（`/proc/sys/kernel/perf_event_paranoid`）控制未授权访问；`CAP_PERFMON` 可替代 root。
- 能看内核栈：`perf record -g` + `--symfs`/`/proc/kallsyms`（需要 `kptr_restrict=0` 或 root）。

## 6. eBPF：可编程的内核观测

### 6.1 基本形态

```c
/* 伪代码：统计每个进程的 read 耗时 */
SEC("fentry/vfs_read")
int BPF_PROG(trace_read, struct file *f, char *buf, size_t n, ...)
{
    bpf_map_update_elem(&start, &pid, &ts, 0);
    return 0;
}
```

- 程序由内核**验证器**（verifier）静态检查（无越界、无无限循环、有界栈），然后 JIT 编译成机器码。
- **挂载点**：`kprobe`/`kretprobe`、`fentry`/`fexit`、`tracepoint`、`perf_event`、`cgroup` 钩子、`XDP`、`tc`、`socket`、`LSM`、`sched_ext`（自定义调度器）、`struct_ops`（自定义 TCP 拥塞控制）。
- **与用户态交互**：map（哈希、数组、per-CPU、环形缓冲 `ringbuf`）+ `bpf()` 系统调用；`bpftrace` 是最常用的高阶接口，`bcc` 是 Python/C 工具集。

### 6.2 bpftrace 速查

```
bpftrace -e 'kprobe:vfs_read { @[comm] = count(); }'                 # 谁在读
bpftrace -e 'tracepoint:sched:sched_switch { @[prev_comm] = count(); }'
bpftrace -e 'kretprobe:vfs_read /retval < 0/ { @errors[errno] = count(); }'
bpftrace -e 'profile:hz:99 /pid == $1/ { @[ustack] = count(); }'      # 用户态火焰图
bpftrace -e 'kfunc:tcp_retransmit_skb { printf("%s\n", comm); }'      # kfunc（BTF）
```

`-l kprobe:*tcp*` 列出可用探针；`BTF`（`/sys/kernel/btf/vmlinux`）让程序无需内核头文件即可访问结构体字段，这是 CO-RE（一次编译到处运行）的基础。

### 6.3 常用 bcc 工具

| 工具 | 用途 |
|---|---|
| `execsnoop` / `opensnoop` | 谁在执行/打开什么 |
| `biolatency` / `biosnoop` / `biostack` | 块 I/O 延迟与栈 |
| `ext4slower` / `xfsslower` | 慢文件操作 |
| `tcpconnect` / `tcpaccept` / `tcpretrans` / `tcplife` | 连接与重传 |
| `runqlat` / `runqlen` | 运行队列延迟（调度） |
| `offcputime` / `offwaketime` | 阻塞时间与其唤醒源（火焰图关键） |
| `cachestat` / `cachetop` | page cache 命中 |
| `memleak` | 内核内存泄漏追踪 |
| `hardirqs` / `softirqs` | 中断耗时 |
| `profile` / `funccount` / `stackcount` | 采样、函数计数、栈计数 |

## 7. 崩溃与故障分析

| 工具/机制 | 用途 |
|---|---|
| `oops` 消息 + `scripts/decode_stacktrace.sh` | 把地址解析成符号与源码行（`addr2line` + 内核镜像） |
| `kallsyms`（`/proc/kallsyms`） | 符号表；`kptr_restrict` 控制可见性 |
| `crash` + `vmcore` | 分析 kdump 转储：`bt`（栈）、`ps`、`kmem`、`foreach` |
| `pstore` | panic 后的最后一段日志 |
| `syzkaller` | 内核 fuzzer（找 bug 的标准手段），配合 KASAN/KCSAN 效果最好 |
| `CONFIG_KASAN` / `KFENCE` | 内存越界/UAF 检测（KASAN 慢但全，KFENCE 采样开销低） |
| `CONFIG_KCSAN` | 数据竞争检测 |
| `CONFIG_UBSAN` | 未定义行为（移位越界、对齐） |
| `kmemleak` | 内存泄漏扫描（`/sys/kernel/debug/kmemleak`） |
| `lockdep` / `DEBUG_ATOMIC_SLEEP` | 锁顺序与原子上下文错误 |
| `hung_task` / `soft lockup` / `hard lockup` | 卡死与长占用检测，输出所有 CPU 栈 |
| `magic SysRq` | `echo t > /proc/sysrq-trigger`（打印全部任务栈）、`echo w`（D 态任务）、`c`（crash） |
| `nmi_watchdog` | 用 NMI 检测 CPU 硬锁死 |

### 典型排查：进程卡在 D 态

```bash
cat /proc/<pid>/stack            # 内核栈（需要 CONFIG_STACKTRACE）
echo w > /proc/sysrq-trigger && dmesg | tail -100   # 所有 D 态任务
cat /proc/<pid>/wchan            # 在等哪个函数
```

## 8. 观测接口的取舍

| 手段 | 是否需要重编内核 | 开销 | 灵活性 |
|---|---|---|---|
| `/proc`、`/sys` 计数器 | 否 | 极低 | 低（作者定义的语义） |
| tracepoint | 否 | 低 | 中（可按字段过滤、触发直方图） |
| ftrace function/function_graph | 需要 `CONFIG_FUNCTION_TRACER`（多数发行版已开） | 中~高 | 高（任意函数） |
| kprobe/uprobe | 否 | 中~高 | 很高（任意地址） |
| perf 采样 | 否 | 低~中 | 高（采样与 PMU） |
| eBPF | 否 | 低~中（JIT 后接近原生） | 最高（可编程） |
| 打印日志 + 重编译 | 是 | 视频率 | 低 |

## 9. 关键文件

| 路径 | 内容 |
|---|---|
| `kernel/trace/` | `trace.c`（核心）、`trace_events.c`、`trace_functions_graph.c` |
| `kernel/trace/trace_kprobe.c`、`trace_uprobe.c` | 动态探针 |
| `include/linux/tracepoint.h`、`include/trace/events/*.h` | tracepoint 定义（如 `sched.h`、`block.h`、`kmem.h`） |
| `kernel/events/core.c` | perf events |
| `kernel/bpf/` | BPF 子系统、验证器 |
| `Documentation/trace/` | ftrace 官方文档（`ftrace.rst`、`events.rst`、`histogram.rst`） |
| `Documentation/bpf/` | BPF 文档与 `btf.rst` |

## 小结

内核观测的现代分工很清晰：**计数器看趋势，tracepoint 看事件，ftrace 看调用树，perf 看热点与 PMU，eBPF 做任意自定义统计**。这些手段的共同基础设施是 tracepoint + BPF + ftrace trampoline，理解它们的开销模型（static key、JIT、采样 vs 逐次）才能在生产环境里既看到问题又不把问题弄得更严重。
