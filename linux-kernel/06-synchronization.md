# 第 6 篇 并发与同步

> 目标：理解内核里各种同步原语的适用条件——为什么有这么多种锁，以及 RCU 和内存屏障到底解决什么问题。

## 1. 并发从哪里来

| 来源 | 说明 |
|---|---|
| 多核（SMP） | 多个 CPU 同时执行内核代码 |
| 内核抢占 | `CONFIG_PREEMPT` 下，进程上下文的内核代码可能在任意点被切走 |
| 中断 | 硬中断/软中断可能打断正在运行的代码，并访问同一数据 |
| 睡眠 | 代码主动阻塞（等 I/O），醒来时世界已变 |
| 编译器与 CPU 重排 | 即使单线程看起来正确，其他 CPU 观察到的顺序可能不同 |

同步原语的选择基本由两个问题决定：**临界区内会不会睡眠？会不会在中断上下文访问？**

## 2. 原语一览

| 原语 | 等待方式 | 能否睡眠 | 典型场景 |
|---|---|---|---|
| `atomic_t` / `atomic64_t` / `refcount_t` | 无锁 | — | 计数、引用计数 |
| `spinlock_t` | 忙等 | 持锁期间**不能** | 短临界区、中断上下文可用 |
| `rwlock_t` | 忙等 | 不能 | 读多写少的短临界区（已不推荐，多数被 RCU 替代） |
| `seqlock_t` / `seqcount_t` | 读者重试 | 读者不阻塞写者 | 小数据、写少读多（时间、`jiffies_64`） |
| `struct mutex` | 睡眠（有自旋优化） | 能 | 进程上下文的较长临界区 |
| `struct rw_semaphore` | 睡眠 | 能 | 读多写少，持有时间长（`mmap_lock`） |
| `struct semaphore` | 睡眠 | 能 | 计数信号量（新代码很少用） |
| `completion` | 睡眠 | 能 | "等某件事完成"（不是锁） |
| **RCU** | 读者无锁，写者等宽限期 | 读侧一般不能睡（SRCU 可以） | 读远多于写的链表、哈希表、配置指针 |
| per-CPU 变量 | 无共享 | — | 统计计数、每 CPU 缓存 |
| `local_lock_t` | 关抢占/（RT 下变 per-CPU 锁） | 不能 | 保护 per-CPU 数据 |

## 3. 原子操作与引用计数

```c
atomic_inc(&v);  atomic_dec_and_test(&v);   /* 返回是否减到 0 */
atomic_cmpxchg(&v, old, new);               /* CAS，无锁算法的基础 */
refcount_inc(&obj->ref);                    /* 溢出/从 0 加会告警，替代用 atomic_t 做引用计数 */
if (refcount_dec_and_test(&obj->ref)) kfree(obj);
```

- **`kref`** 封装了 `refcount_t` + 释放回调，是内核对象生命周期管理的标准做法。
- 引用计数从 0 加回 1 是经典 UAF 漏洞来源，`refcount_t` 会检测并拒绝。
- 内存序：按 LKMM，**有返回值的**原子操作（如 `atomic_inc_return`、`atomic_cmpxchg` 成功时）隐含完整屏障，**无返回值的**（如 `atomic_inc`）不保证任何顺序，需要时显式加 `smp_mb__after_atomic()`；另有 `_acquire`/`_release`/`_relaxed` 变体。x86 上碰巧都是带 `lock` 前缀的全屏障，arm64 则用 LSE 原子指令或 LL/SC，差别会体现出来。

## 4. 自旋锁

```c
spin_lock(&lock);             /* 关抢占 + 拿锁 */
spin_lock_irqsave(&lock, flags); /* 再关本地中断，保存原状态 */
spin_lock_bh(&lock);          /* 关软中断 */
```

选择规则：

| 数据被谁访问 | 进程上下文里用 |
|---|---|
| 只在进程上下文 | `spin_lock` |
| 进程上下文 + softirq | `spin_lock_bh` |
| 进程上下文 + hardirq | `spin_lock_irqsave` / `spin_lock_irq` |
| 只在 hardirq 处理函数内 | `spin_lock`（本中断此时已屏蔽） |

为什么要关中断：如果进程上下文持锁时被同一 CPU 上的中断打断，而中断处理函数也来拿这把锁，就会**自己等自己**，死锁。

实现：x86-64 上是 **qspinlock**（基于 MCS 队列，每个等待者在自己的 per-CPU 节点上自旋，避免缓存行乒乓），竞争激烈时扩展性远好于早期的 ticket lock。

`PREEMPT_RT` 下 `spinlock_t` 变成可睡眠的 rt_mutex（带优先级继承），真正必须忙等的地方改用 `raw_spinlock_t`。

## 5. 睡眠锁

### mutex

- 语义比信号量严格：只能由持有者解锁、不能递归、不能在中断上下文使用。
- **乐观自旋**：如果锁持有者正在另一个 CPU 上运行，等待者先自旋一会儿（持有者很可能马上释放），比直接睡眠再唤醒便宜。
- `mutex_lock_interruptible` / `mutex_lock_killable`：等待中能被信号打断，用于系统调用路径避免进程卡死成 D 态。

### rw_semaphore 与 `mmap_lock`

`mm_struct->mmap_lock` 是一个 rwsem，缺页（读）与 `mmap`/`munmap`（写）都要拿它。多线程程序频繁 `mmap` 时这把锁是著名的扩展性瓶颈。6.4 起引入的 **per-VMA lock** 让大多数缺页只锁定单个 VMA，不再拿全局 `mmap_lock`。

## 6. 顺序锁（seqlock）

写者递增序号（奇数表示正在写），读者在读前后各读一次序号，不一致就重试：

```c
do {
    seq = read_seqbegin(&lock);
    t = shared_time;              /* 拷贝数据 */
} while (read_seqretry(&lock, seq));
```

适用于：数据小、写不频繁、读者能容忍重试。读者完全不阻塞写者，写者也不会被大量读者饿死。时间子系统、vDSO 的时间数据都使用它。限制：数据里不能有指针（读者可能读到半更新的指针并解引用）。

## 7. RCU（Read-Copy-Update）

RCU 是 Linux 内核里最有代表性的同步机制，用于**读远多于写**的场景，让读者**零开销**。

### 基本思想

```
写者：
  1. 复制旧对象 → 修改副本
  2. rcu_assign_pointer(gp, new)   ← 原子地发布新指针
  3. synchronize_rcu()             ← 等待"宽限期"：所有已开始的读者都结束
     （或 call_rcu(&old->rcu, free_cb) 异步回调）
  4. kfree(old)                    ← 此时不可能再有人引用旧对象

读者：
  rcu_read_lock();                 ← 非抢占内核里几乎什么都不做
  p = rcu_dereference(gp);         ← 带依赖屏障的读取
  ... 使用 p，不能睡眠 ...
  rcu_read_unlock();
```

### 宽限期怎么判断

在非抢占 RCU 中，读者临界区内不能发生上下文切换。因此**每个 CPU 都经历过一次上下文切换（或进入 idle/用户态）**，就说明此前开始的读者都已结束——这叫"静止状态"（quiescent state）。RCU 用分层的 `rcu_node` 树汇总各 CPU 的静止状态，避免全局锁。

### 变体

| 变体 | 读侧 | 用途 |
|---|---|---|
| 普通 RCU | `rcu_read_lock` | 大多数场景 |
| SRCU | `srcu_read_lock`，**可睡眠** | 读侧可能阻塞的场景（如 notifier 链） |
| Tasks RCU | 以任务自愿切换为静止状态 | ftrace/BPF trampoline 的安全替换 |
| `kfree_rcu()` | — | 最常用的写侧简写：宽限期后释放 |

### 常见使用

- 路由表、`fdtable`（文件描述符表）、进程链表遍历、模块列表、网络设备列表、`cred`。
- 列表操作：`list_add_rcu`、`list_del_rcu`、`list_for_each_entry_rcu`。

**代价**：写者要么同步等待（毫秒级），要么异步回调（内存延迟释放，回调堆积可能吃内存）。因此 RCU 不适合写频繁的场景。

## 8. 内存模型与屏障

### 为什么需要屏障

编译器可以重排、合并、消除内存访问；CPU（尤其 arm64、POWER 等弱内存序架构）可以乱序执行和乱序提交 store。对单线程无影响，但其他 CPU 可能看到"违反程序顺序"的结果：

```c
/* CPU 0 */                 /* CPU 1 */
data = 42;                  while (!READ_ONCE(ready)) ;
WRITE_ONCE(ready, 1);       print(data);     /* 弱序架构上可能打印旧值！ */
```

### 内核提供的工具

| 工具 | 作用 |
|---|---|
| `READ_ONCE` / `WRITE_ONCE` | 阻止编译器合并/撕裂/省略访问（不提供 CPU 层面的顺序） |
| `smp_mb()` / `smp_rmb()` / `smp_wmb()` | 全屏障 / 读屏障 / 写屏障（SMP 才生效） |
| `smp_store_release()` / `smp_load_acquire()` | 释放/获取语义，修复上例的标准写法 |
| `barrier()` | 仅编译器屏障 |
| 锁的加解锁 | 隐含 acquire/release 语义，临界区内访问不会"漏出去" |

修正上例：

```c
/* CPU 0 */                          /* CPU 1 */
data = 42;                           while (!smp_load_acquire(&ready)) ;
smp_store_release(&ready, 1);        print(data);   /* 保证看到 42 */
```

内核有正式的 **LKMM（Linux Kernel Memory Model）**，在 `tools/memory-model/` 中可用 herd7 工具对小段代码做形式化验证。

## 9. per-CPU 数据：最好的锁是不加锁

```c
DEFINE_PER_CPU(unsigned long, my_counter);
this_cpu_inc(my_counter);     /* 单条指令（x86 用 gs: 前缀），对抢占安全 */

/* 汇总时 */
for_each_possible_cpu(cpu) sum += per_cpu(my_counter, cpu);
```

- 访问 per-CPU 数据期间若涉及多步操作，必须关抢占（`get_cpu()`/`put_cpu()` 或 `preempt_disable()`），否则任务可能中途迁移到另一个 CPU。
- `percpu_counter`：近似计数，局部累积到阈值才合并到全局（`/proc/meminfo` 里很多数值就是这样来的，所以不是精确值）。
- `percpu_ref`：读侧几乎零成本的引用计数，关闭时切换为原子模式（用于 cgroup、块设备队列）。

## 10. 死锁与调试工具

| 工具 | 作用 |
|---|---|
| **lockdep**（`CONFIG_PROVE_LOCKING`） | 运行时记录所有锁的获取顺序与上下文，发现**潜在**的 AB-BA 死锁和中断不安全的使用，不需要真的死锁 |
| `CONFIG_DEBUG_ATOMIC_SLEEP` | 在原子上下文中睡眠时告警 |
| KCSAN | 动态数据竞争检测（基于采样 watchpoint） |
| `CONFIG_LOCK_STAT` | `/proc/lock_stat` 统计锁争用和等待时间 |
| hung task detector | 任务处于 D 态超过 `hung_task_timeout_secs`（默认 120 秒）时打印栈 |
| soft/hard lockup detector | CPU 长时间不调度或不响应中断 |

锁顺序约定：**按固定层级加锁**（例如 inode 锁先于 page 锁），并用 `lockdep_assert_held()` 在函数中声明前置条件。

## 11. 选型速查

```
需要保护共享数据？
├─ 只是一个计数/标志 → atomic_t / refcount_t / READ_ONCE+WRITE_ONCE
├─ 可以按 CPU 拆分 → per-CPU 变量
├─ 读极多、写少、能接受旧值短暂存在 → RCU
├─ 数据很小、写少、读者可重试 → seqlock
├─ 临界区内可能睡眠 → mutex（读多写少用 rw_semaphore）
└─ 临界区短、不睡眠 → spinlock（按中断上下文选 _bh/_irqsave 变体）
```

## 12. 关键文件

| 路径 | 内容 |
|---|---|
| `kernel/locking/` | `mutex.c`、`rwsem.c`、`qspinlock.c`、`lockdep.c`、`rtmutex.c` |
| `kernel/rcu/` | `tree.c`（Tree RCU）、`srcutree.c`、`tasks.h` |
| `include/linux/rcupdate.h` | RCU API |
| `include/asm-generic/barrier.h` | 屏障定义 |
| `tools/memory-model/` | LKMM 形式化模型与文档 |
| `Documentation/memory-barriers.txt` | 内存屏障权威文档（长但必读） |

## 小结

内核的同步设计遵循一条清晰的偏好顺序：**能不共享就不共享（per-CPU）> 读侧无锁（RCU、seqlock）> 短时间忙等（spinlock）> 睡眠锁（mutex）**。理解每种原语的前提（能否睡眠、是否在中断上下文、读写比例）比记住 API 更重要；而 lockdep、KCSAN 这类工具能把很多并发错误从"偶发死机"提前到"开发期告警"。
