# 第 3 篇 进程管理与调度

> 目标：理解 `task_struct` 到底描述了什么、fork/exec/exit 的内核实现，以及一个 runnable 的任务如何被选中运行——包括 EEVDF 调度器为什么取代了 CFS。

## 1. `task_struct`：内核里最复杂的结构体

`include/linux/sched.h`，几千字节、两百多个字段。按功能分组记忆最有效：

| 分组 | 字段（举例） | 说明 |
|---|---|---|
| 状态与身份 | `__state`、`pid`、`tgid`、`pid_links[]` | `tgid` 是线程组 ID，即用户态看到的"进程号" |
| 调度 | `prio`、`static_prio`、`se`(`sched_entity`)、`rt`、`dl`、`sched_class`、`policy`、`on_rq` | 见第 4 节 |
| 关系 | `real_parent`、`children`、`sibling`、`group_leader`、`thread_group` | 通过 `list_head` 串成树 |
| 地址空间 | `mm`、`active_mm` | 内核线程 `mm == NULL`，借用前一个任务的 `active_mm`（lazy TLB） |
| 文件 | `files`(`files_struct`)、`fs`(`fs_struct`)、`nsproxy` | `files_struct` 里是 fd 数组 |
| 信号 | `signal`(`signal_struct`)、`sighand`、`pending`、`blocked` | 线程组共享 `signal`，各自有 `pending` |
| 时间与记账 | `utime`/`stime`、`se.sum_exec_runtime`、`nvcsw`/`nivcsw` | 每 tick / 每次切换更新 |
| 内存策略 | `mempolicy`、`flags`（`PF_*`）、`cpus_ptr` | NUMA、`PF_KTHREAD`、`PF_EXITING` |
| 安全 | `cred`(`const struct cred *`)、`seccomp`、`security` | `cred` 是 RCU 保护的常量结构，改权限要 `commit_creds` |
| 内核栈 | `stack`、`thread`(`thread_struct`，保存切换所需的硬件状态) | |
| 调试/追踪 | `seccomp`、`audit_context`、`bpf_*` | |

> **`task_struct` 只由内核创建和写入**，用户态通过 `/proc/<pid>/` 读投影。`task_struct` 本身在 slab 里分配，另有 `thread_info` 与之绑定，`current` 宏在 x86-64 上通过 `gs:current_task` 直接取，O(1)。

### 线程 vs 进程

Linux 没有独立的"线程"概念：**线程就是共享地址空间和许多资源的 `task_struct`**。`clone(2)` 的 `CLONE_*` 标志决定共享哪些部分：

| 标志 | 共享的资源 |
|---|---|
| `CLONE_VM` | `mm_struct`（地址空间） |
| `CLONE_FILES` | fd 表 |
| `CLONE_FS` | cwd / root / umask |
| `CLONE_SIGHAND` | 信号处理函数表 |
| `CLONE_THREAD` | 同一个线程组（同 `tgid`，共享 `signal_struct`） |
| `CLONE_NEWPID` / `CLONE_NEWNS` / `CLONE_NEWNET` … | 创建新的命名空间（第 12 篇） |

`fork()` 就是传 `SIGCHLD` 的 `clone`；`pthread_create` 就是传 `CLONE_VM|CLONE_FILES|CLONE_FS|CLONE_SIGHAND|CLONE_THREAD|...` 的 `clone`。容器就是一个带满 `CLONE_NEW*` 的 `clone`。

## 2. 任务的生命周期

### 2.1 状态机

| 状态 | 含义 | 是否计入 load average |
|---|---|---|
| `TASK_RUNNING` | 正在 CPU 上跑，或就在运行队列里等着 | 是（R 态） |
| `TASK_INTERRUPTIBLE` | 睡眠，可被信号唤醒 | 否（S 态） |
| `TASK_UNINTERRUPTIBLE` | 睡眠，不被信号打断（等 I/O、等锁） | 是（D 态） |
| `__TASK_STOPPED` | 收到 `SIGSTOP`/被 ptrace 停止 | 否（T 态） |
| `EXIT_ZOMBIE` | 已退出，等父进程 `wait` 收尸 | 否（Z 态） |
| `EXIT_DEAD` | 即将被释放 | 否 |

**D 态**特别值得注意：它不可被信号杀死，`kill -9` 无效；大量 D 态通常意味着存储或网络文件系统卡住。Linux 的 load average 把 D 态也算进去，这与很多 Unix 不同。

> 2.6.25 引入 `TASK_KILLABLE`（只响应致命信号的睡眠，NFS 等场景用它来缓解"kill 不掉"的问题）；还有 `TASK_IDLE`（不可中断但不计入 load average，供长期空闲的内核线程使用）。

### 2.2 `fork()`：写时复制

`kernel/fork.c` 的 `copy_process()` 是核心：

1. `dup_task_struct()`：为子任务分配新的内核栈（x86-64 上是 vmalloc 的 16KB 栈），并复制父任务的 `task_struct`（`arch_dup_task_struct`，含 FPU 状态）。
2. 分配新 PID（`alloc_pid`），初始化 `sched_entity`、`cred`（`get_cred` 共享同一份）。
3. **`copy_mm()`**：`CLONE_VM` 时直接共享 `mm_struct` 并把 `mm_users++`；否则 `dup_mmap()` 复制页表——但**只复制页表项并全部标记只读**，物理页不复制，这就是 COW。父/子任一写入触发缺页，`do_wp_page()` 才真正复制一页。
4. `copy_files()`、`copy_fs()`、`copy_sighand()`、`copy_signal()`、`copy_namespaces()`。
5. `copy_thread()`：设置新任务的 `pt_regs`，让它在被调度时从 `ret_from_fork` 开始执行（子进程返回值为 0）。
6. 唤醒新任务（`wake_up_new_task`），放入运行队列。

COW 的代价：写多的负载下，一次 `fork()` 可能引发大量缺页（`/proc/vmstat` 的 `pgfault`、`pgmajfault`）。**`posix_spawn` / `vfork` / `clone3` + `CLONE_VFORK`** 让子进程在 exec 前不复制页表，避免这个问题。

### 2.3 `execve()`：换掉整个用户态

`do_execveat_common()` → `bprm_execve()`：

1. 打开可执行文件、读前 256 字节判断格式（ELF、`#!` 脚本）。
2. `bprm_mm_init()`：**新建**一个 `mm_struct`（旧的地址空间准备丢弃）。
3. `exec_binprm()`：ELF loader 解析 `PT_LOAD` 段，`vm_mmap` 映射代码段（可执行、只读）、数据段（私有可写，按 `p_filesz`/`p_memsz` 补零 = `.bss`）、堆（`brk` 起点）、栈（新的 `vm_area_struct`，随机化 ASLR）。
4. 把 argv/envp 字符串拷到新栈顶部，构建 `argc`/`argv` 布局。
5. 设置解释器（`PT_INTERP` → `ld-linux-x86-64.so.2`）、`AT_*` 辅助向量（含 `AT_RANDOM` 供 stack canary 和 ASLR）。
6. `begin_new_exec()`：切换 `mm`、清理旧信号处理函数（`SIG_DFL`）、重置 `alternate signal stack`、重设 credentials（setuid 位 → `install_exec_creds`）。
7. 回到用户态，从 ELF entry point（或解释器入口）开始执行。

注意 `execve` **不创建新进程**，PID 不变。`#!` 脚本是一个内核层面的"重新 exec 解释器"。

### 2.4 退出与收尸

`do_exit()`：

1. 设 `PF_EXITING`，拆除 `mm`（`exit_mm`）、fd 表（`exit_files`）、信号（`exit_signal`）、命名空间、IO 上下文等。
2. 状态变 `EXIT_ZOMBIE`，**释放除 `task_struct` 与内核栈之外的一切**（因为父进程还要读退出码和资源统计）。
3. `exit_notify()`：通知父进程、把子女 `reparent` 给 `child_reaper`（通常是 PID 1 或 `PR_SET_CHILD_SUBREAPER` 设的进程）。
4. 主动调用 `schedule()` 切到别的任务，永不返回。

父进程 `wait4()` 后 `release_task()` 才真正 `free_task()`。**僵尸进程**就是父进程不 wait 的产物；孤儿进程会被 PID 1 收养（所以 PID 1 必须负责 wait，否则泄漏）。

## 3. 内核线程

- 由 `kthread_create()` / `kthread_run()` 创建（或 `kthreadd` 通过 `kthread_create_on_node` 间接创建），`mm == NULL`。
- 常用：`kworker/N:W`（workqueue）、`kswapdN`（回收）、`ksoftirqd/N`（软中断）、`migration/N`（CPU 迁移）、`rcu_gp`/`rcu_par_gp`（RCU）、`kcompactdN`、`jbd2/*`（ext4 日志）、`ksmd`、`kblockd`。
- 名字格式 `xxx/N` 中的 `N` 通常是 CPU 编号；`top -H` / `ps -eLo pid,tid,comm` 可见。

## 4. 调度器

### 4.1 分层结构：`sched_class`

```c
struct sched_class {
    void (*enqueue_task)(struct rq *, struct task_struct *, int);
    void (*dequeue_task)(struct rq *, struct task_struct *, int);
    struct task_struct *(*pick_next_task)(struct rq *);
    void (*task_tick)(struct rq *, struct task_struct *, int);
    void (*task_fork)(struct task_struct *);
    void (*prio_changed)(...);
    void (*switched_to)(...);
    /* ... */
};
```

每个 CPU 一个 `struct rq`（运行队列），里面按**优先级从高到低**挂着不同的调度类实例：

```
rq->dl        deadline 类（SCHED_DEADLINE）  最高
   ->rt       实时类（SCHED_FIFO / SCHED_RR）
   ->fair     普通类（SCHED_NORMAL / SCHED_BATCH），默认
   ->ext      sched_ext（可加载 BPF 调度器，6.12 起）
   ->idle     空闲类（SCHED_IDLE）
```

`pick_next_task()` 由高到低询问，找到就停。这就是"优先级"的实现方式：**不同调度类之间没有复杂的公平算法，就是严格分级**。

### 4.2 优先级数值

| 概念 | 范围 | 说明 |
|---|---|---|
| nice | -20 ~ +19 | 用户态可见，越小越优先 |
| `static_prio` | 100 ~ 139 | `120 + nice` |
| `rt_priority` | 1 ~ 99 | 实时任务的相对优先级（99 最高） |
| `prio` | 0 ~ 139 | 有效优先级（含 PI 继承调整） |
| `SCHED_DEADLINE` | 有 `runtime`/`deadline`/`period` | 用参数而非优先级排序 |

用户态接口：`nice()`、`setpriority()`、`sched_setscheduler()`、`sched_setattr()`、`sched_setaffinity()`。

### 4.3 CFS 与 EEVDF

**CFS（完全公平调度器，2.6.23 ~ 6.5）** 的核心是**虚拟运行时间 `vruntime`**：

- 每个 `sched_entity` 维护 `vruntime`，每次运行按 `实际运行时间 × 权重比` 累加。
- 红黑树（`cfs_rq->tasks_timeline`）以 `vruntime` 为键，**总是选最左边的任务**（`vruntime` 最小）。
- 权重由 nice 值映射（`sched_prio_to_weight[]`），典型值：nice 0 = 1024；每降 1 个 nice 约提升 1.25 倍 CPU 份额。
- `min_vruntime` 用于保证新唤醒任务不会被饿死太久（`place_entity` 做补偿）。

**EEVDF（6.6 起默认，来自实时调度理论 Earliest Eligible Virtual Deadline First）** 修正了 CFS 的两个结构性缺陷：

1. CFS 只保证"按权重比例分时间"，**不保证延迟**——一个刚被唤醒的交互任务（如按键响应）可能排在 `vruntime` 很靠后的位置等很久。
2. 时间片是"启发式"的：`sched_slice()` 按 `nr_running` 均分目标周期，任务数多时每个片都很短，切换开销占比高。

EEVDF 的做法：

- 每个任务有 **`slice`（请求的时间片）**，可由 `sched_setattr(sched_runtime)` 显式指定，默认按权重推算。
- 计算 **`deadline = 唤醒时 vruntime 基线 + slice / 权重`**——"lag" 决定它应得的 CPU 量。
- **只考虑 eligible（lag ≥ 0，即还没拿到应得 CPU 时间）的任务**；在 eligible 集合中选 **virtual deadline 最小**的。
- 结果：既按权重公平分享，又对短 `slice` 的交互任务给出显式延迟保证。用户可通过 `sched_setattr` 的 `sched_runtime` 调优单任务延迟。

调参：5.13 起调度器的调试参数从 `/proc/sys/kernel/sched_*` 移到了 debugfs（`/sys/kernel/debug/sched/`）；EEVDF 下主要是 `base_slice_ns`（替代旧的 `min_granularity_ns`），CFS 时代的 `latency_ns`、`wakeup_granularity_ns` 已移除。

### 4.4 实时调度

- **`SCHED_FIFO`**：同优先级 FIFO，只有更高优先级或主动让出/阻塞才会被抢；**无时间片**，一条死循环能锁死整个 CPU（并且会饿死所有普通任务）。
- **`SCHED_RR`**：同优先级轮转，时间片 `sched_rr_timeslice_ms`（默认 100ms）。
- **`SCHED_DEADLINE`**：EDF，参数 `(runtime, deadline, period)`，每 period 内最多跑 runtime，deadline 前必须完成。用 CBS（constant bandwidth server）限制带宽，超支会被推到下一个周期。
- 实时带宽控制：`/proc/sys/kernel/sched_rt_runtime_us`（默认 950000/1000000，即最多 95%）给普通任务留 5% 的活路。
- `SCHED_IDLE`：仅在系统空闲时运行，适合后台清理。
- `SCHED_BATCH`：非交互批处理，唤醒延迟容忍度高。

### 4.5 抢占模型

| 模型 | 配置 | 行为 |
|---|---|---|
| 无抢占 | `CONFIG_PREEMPT_NONE` | 内核代码跑到底（长时间计算会带来调度抖动） |
| Voluntary | `CONFIG_PREEMPT_VOLUNTARY` | 只在显式 `might_sleep()`/阻塞点调度 |
| 完整抢占 | `CONFIG_PREEMPT` | 除临界区外任意内核代码可被抢占 |
| 实时 | `CONFIG_PREEMPT_RT` | 自旋锁变可睡眠 mutex、中断线程化、`local_lock` 等，最坏延迟到微秒量级（6.12 起部分 RT 功能并入主线） |

抢占点检查 `preempt_count`：中断/软中断/自旋锁都会加计数，计数不为 0 时不可抢占。这就是"原子上下文"的机械含义。

### 4.6 上下文切换

`__schedule()` → `context_switch()`：

1. 切换到目标的 `mm`（`switch_mm_irqs_off`）：若 `mm` 不同，换 CR3（PCID 优化可少 flush TLB）。
2. `switch_to(prev, next)`：保存/恢复 callee-saved 寄存器、栈指针，以及 `thread_struct` 里的 FS/GS 基址、浮点/向量状态（AVX-512 的 `xstate_ptr` 用 `XSAVES`/`XRSTORS` 惰性保存）。
3. 执行 `finish_task_switch()`，返回新任务的保存点。

单次切换开销大致几百纳秒到一两微秒（估计值，随 CPU 与状态保存量变化）。`/proc/<pid>/status` 的 `voluntary_ctxt_switches`/`nonvoluntary_ctxt_switches` 以及 `vmstat` 的 `cs` 可观察频率。

## 5. 负载均衡与 CPU 亲和

- 每个 CPU 一个 `rq`，空闲 CPU 从忙 CPU"拉"任务（`newidle_balance`/`load_balance`），周期性负载均衡由 `sched_domain` 层次驱动（SMT → 同一 die → 同一 socket → NUMA 节点）。
- **NUMA balancing**：周期性把任务的页或任务本身迁移到更近的节点。
- `sched_setaffinity` 设置 `cpus_ptr`；cgroup `cpuset` 限制更强（含内存节点 `mems`）。
- **CPU 隔离**：`isolcpus=` 内核参数 + `nohz_full=` + `rcu_nocbs=` + `irqaffinity=`，把某些核完全留给特定实时/DPDK 类工作负载。

## 6. cgroup 的 CPU 控制器

| 控制器 | 效果 |
|---|---|
| `cpu.weight` | 按比例分配 CPU（对应 nice 的层级版本） |
| `cpu.max` | 硬带宽限速：`<quota> <period>`，超出就在下一个 period 前不让跑（CFS bandwidth） |
| `cpuset.cpus`/`cpuset.mems` | 绑定 CPU 与 NUMA 节点 |
| `cpu.stat` | `usage_usec`、`throttled_usec` 等 |

注意 `cpu.max` 的经典坑：quota 用尽的全组一起被 throttle，会出现"明明机器有空闲核，容器却卡住"的现象（`nr_throttled` 增高）。

## 7. 关键文件

| 路径 | 内容 |
|---|---|
| `include/linux/sched.h` | `task_struct`、调度实体定义 |
| `kernel/fork.c` | `copy_process`、`copy_mm`、`kernel_clone`（原 `do_fork`） |
| `fs/exec.c` | `execve` 全流程 |
| `kernel/exit.c` | `do_exit`、`wait4`、`reparent` |
| `kernel/sched/core.c` | 调度核心、`__schedule`、`context_switch` 调用点 |
| `kernel/sched/fair.c` | CFS / EEVDF（`pick_eevdf`、`sched_slice`） |
| `kernel/sched/rt.c`、`deadline.c` | 实时与 deadline 类 |
| `kernel/sched/sched.h` | `rq`、`sched_class` 声明 |

## 小结

进程管理的主线是"**共享尽量多、复制尽量少**"：`clone` 用标志位决定共享粒度，`fork` 用 COW 拖延物理复制，`execve` 一次性重建地址空间。调度器则是"**分层类 + 每 CPU 运行队列 + 通过 `sched_entity` 做公平记账**"，EEVDF 在记账基础上引入了显式延迟保证。理解 `vruntime`/`deadline` 与 `preempt_count` 这两个概念，基本就能解释绝大多数调度相关的现象。
