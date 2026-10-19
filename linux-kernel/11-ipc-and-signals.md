# 第 11 篇 进程间通信与信号

> 目标：理解内核提供的各种 IPC 机制的实现方式与适用场景，重点是信号的投递流程和 futex（用户态锁的内核基础）。

## 1. IPC 机制总览

| 机制 | 数据流 | 内核实现要点 | 适用 |
|---|---|---|---|
| 管道 `pipe` | 单向字节流 | `pipe_inode_info` 环形缓冲（默认 16 页 = 64KB），`fs/pipe.c` | shell 管道、父子进程 |
| FIFO（命名管道） | 单向字节流 | 同管道，但有文件系统路径 | 无亲缘关系的进程 |
| Unix 域 socket | 双向，流/数据报/有序包 | `net/unix/`，**可传递 fd**（`SCM_RIGHTS`）与凭证（`SCM_CREDENTIALS`） | 本机服务（dbus、docker.sock、Wayland） |
| 共享内存 | 内存映射 | 同一物理页映射进多个进程页表 | 大数据量、低延迟 |
| 信号 | 异步通知（携带极少数据） | `task_struct->pending`，返回用户态时投递 | 事件通知、作业控制 |
| futex | 同步原语的内核等待部分 | 按地址哈希的等待队列 | pthread mutex/condvar |
| eventfd | 64 位计数器 | 一个 fd，可放进 epoll | 线程/进程间轻量唤醒，KVM 中断注入 |
| System V IPC | 消息队列、信号量、共享内存 | `ipc/`，独立的 key 命名空间，需要显式删除 | 遗留应用 |
| POSIX 消息队列 / 信号量 | 同上 | `mqueue` 文件系统；POSIX 命名信号量实际基于共享内存 + futex | 新代码中较 SysV 推荐 |
| netlink | 内核 ↔ 用户态消息 | 特殊 socket 族 | 路由、防火墙、设备事件 |
| `pidfd` | 进程句柄 | 指向 `struct pid` 的 fd | 安全地对进程发信号、等待退出（避免 PID 复用竞争） |

## 2. 管道

```c
int fd[2]; pipe2(fd, O_CLOEXEC);
```

- 内核里是一组 `pipe_buffer`（每个指向一页），读写指针循环使用。
- 写入不超过 `PIPE_BUF`（4096 字节）时保证**原子性**（不会和其他写者的数据交错）。
- 缓冲区满则写者阻塞，空则读者阻塞；所有写端关闭后读端得到 EOF；所有读端关闭后写端收到 `SIGPIPE`/`EPIPE`。
- `fcntl(F_SETPIPE_SZ)` 调整容量（上限 `/proc/sys/fs/pipe-max-size`）。
- **`splice` / `vmsplice` / `tee`**：管道是内核内部"移动页引用"的中转站，可在文件、socket、管道之间零拷贝转移数据。

## 3. 共享内存

| 方式 | 说明 |
|---|---|
| `mmap(MAP_SHARED | MAP_ANONYMOUS)` + `fork` | 父子进程共享匿名页（底层是 shmem/tmpfs） |
| `shm_open` + `mmap` | POSIX 共享内存，`/dev/shm` 下的 tmpfs 文件 |
| `memfd_create` + 传递 fd | 无路径的匿名内存文件，可用 `F_SEAL_*` 封印（禁止缩小/写入），适合安全地与不可信进程共享（Wayland、Android） |
| `shmget`/`shmat` | System V，需 `ipcrm` 清理，受 `kernel.shmmax` 等限制 |
| 文件 `mmap(MAP_SHARED)` | 共享 page cache 页 |

共享内存本身**没有同步**，需要配合 futex（进程共享的 pthread mutex：`PTHREAD_PROCESS_SHARED`）、原子操作或 eventfd 通知。

## 4. 信号

### 4.1 数据结构

```
task_struct
 ├─ pending        线程私有待处理信号（tkill/tgkill、同步异常如 SIGSEGV）
 ├─ blocked        信号掩码（sigprocmask / pthread_sigmask）
 ├─ signal ──→ signal_struct（线程组共享）
 │              └─ shared_pending   发给整个进程的信号（kill）
 └─ sighand ──→ sighand_struct（线程组共享）
                └─ action[64]      每个信号的处理方式（SIG_DFL / SIG_IGN / 用户函数）
```

- 标准信号 1–31：**不排队**，同一信号多次到达只记一次（位图）。
- 实时信号 `SIGRTMIN`–`SIGRTMAX`（内核编号 32–64；glibc 内部占用前两个，所以用户看到的 `SIGRTMIN` 通常是 34）：**排队**，按序投递，可携带 `sigval` 数据（`sigqueue`）。

### 4.2 发送

`kill()` → `kill_pid_info` → `group_send_sig_info` → 权限检查（同 UID 或 `CAP_KILL`） → `__send_signal_locked`：

1. 被忽略的信号直接丢弃（除了特殊处理）。
2. 加入相应 `pending` 队列（分配 `sigqueue`，受 `RLIMIT_SIGPENDING` 限制）。
3. **选择一个线程来处理**（`complete_signal`）：进程级信号优先选当前没有阻塞该信号的线程。
4. 设置该线程的 `TIF_SIGPENDING` 并唤醒它（`signal_wake_up`：若它在 `TASK_INTERRUPTIBLE` 睡眠中，会被唤醒，系统调用返回 `-EINTR` 或 `-ERESTARTSYS`）。
5. `SIGKILL` 与致命信号会唤醒 `TASK_KILLABLE` 的任务，并对整个线程组设置退出。

### 4.3 投递

信号**只在返回用户态时**处理（第 2 篇 `exit_to_user_mode_loop`）：

```
get_signal() 取出一个待处理且未阻塞的信号
  ├─ SIG_IGN → 丢弃
  ├─ SIG_DFL → 默认动作：终止 / 终止并 core dump / 停止（SIGSTOP 家族） / 继续 / 忽略
  └─ 用户处理函数：
       handle_signal() → setup_rt_frame()
         · 在用户栈（或 sigaltstack 指定的备用栈）上压入 rt_sigframe：
           保存的寄存器（ucontext）、siginfo、返回地址 = sa_restorer（glibc 的 __restore_rt）
         · 修改 pt_regs：rip = handler，rdi = signo，rsi = &siginfo，rdx = &ucontext
         · 返回用户态 → 执行 handler
       handler 返回 → __restore_rt 执行 rt_sigreturn 系统调用
         → 内核从栈帧恢复原寄存器 → 回到被打断的位置
```

### 4.4 系统调用被打断与重启

| 返回码 | 行为 |
|---|---|
| `-EINTR` | 直接返回给用户 |
| `-ERESTARTSYS` | 若 handler 设置了 `SA_RESTART`，内核调整 `rip` 回退到 `syscall` 指令自动重启；否则返回 `EINTR` |
| `-ERESTARTNOINTR` | 总是重启 |
| `-ERESTART_RESTARTBLOCK` | 通过 `restart_syscall` 带剩余时间重启（`nanosleep`） |

### 4.5 特殊信号与要点

- `SIGKILL`、`SIGSTOP` 不可捕获、不可阻塞、不可忽略。
- 同步信号（`SIGSEGV`、`SIGBUS`、`SIGFPE`、`SIGILL`、`SIGTRAP`）由异常处理代码直接发给出错线程。
- **信号处理函数中只能调用异步信号安全函数**（`write` 可以，`printf`/`malloc` 不行），因为它可能打断任意代码（包括正在持有 malloc 锁的代码）。
- 现代做法：用 `signalfd` 把信号变成可读事件，或 handler 只写一个字节到 self-pipe/eventfd，主循环统一处理。
- 多线程程序中推荐：所有线程阻塞信号，用一个专门线程 `sigwaitinfo`。
- `pidfd_send_signal` 避免"PID 被回收复用后误杀"的竞争。

## 5. futex：用户态锁的内核基础

**设计思想**：无竞争时完全在用户态用原子指令完成加解锁，只有**需要等待或唤醒时**才进入内核。

```
用户态锁变量：int *uaddr（0 = 空闲，1 = 被持有，2 = 被持有且有等待者）

加锁：
  if (cmpxchg(uaddr, 0, 1) == 0) return;          /* 快路径：无系统调用 */
  while (xchg(uaddr, 2) != 0)
      futex(uaddr, FUTEX_WAIT, 2);                 /* 慢路径：内核再次检查 *uaddr == 2 才睡眠 */

解锁：
  if (atomic_exchange(uaddr, 0) == 2)
      futex(uaddr, FUTEX_WAKE, 1);                 /* 有等待者才进内核唤醒 */
```

### 内核实现

- 全局哈希表 `futex_queues`，键是**地址**：私有 futex 用 `(mm, 虚拟地址)`，共享 futex 用 `(inode/page, 偏移)`，所以跨进程共享内存中的锁也能工作。
- `FUTEX_WAIT` 的关键：**在持有哈希桶锁的情况下重新读取 `*uaddr` 并与期望值比较**，不等则返回 `EAGAIN`。这个"比较并睡眠"的原子性消除了丢失唤醒的竞争。
- `FUTEX_PRIVATE_FLAG`：仅进程内使用，跳过共享映射查找，更快（glibc 默认）。
- **PI futex**（`FUTEX_LOCK_PI`）：优先级继承，防止实时系统中的优先级反转，内核用 `rt_mutex` 实现。
- **robust futex**：线程持锁死亡时，内核遍历其注册的 robust list，把锁标记为 `FUTEX_OWNER_DIED` 并唤醒等待者。
- `futex_waitv`（5.16）：一次等待多个 futex（为 Wine/Proton 的 `WaitForMultipleObjects` 而加）。
- 6.7 起的 `futex2` 系列系统调用（`futex_wake`/`futex_wait`/`futex_requeue`）支持不同大小与 NUMA 感知。

glibc 的 `pthread_mutex`、`pthread_cond`、`sem_t`、C++ `std::mutex`、Go/Rust 运行时的锁最终都基于 futex。`perf trace -e futex` / `strace -f -e futex` 可以观察锁争用。

## 6. eventfd、signalfd、timerfd、pidfd：一切皆 fd

这些接口把不同的事件源统一为文件描述符，可以放进同一个 `epoll` 循环：

| fd 类型 | 事件 |
|---|---|
| `eventfd` | 计数器非零 |
| `signalfd` | 有待处理信号 |
| `timerfd` | 定时器到期 |
| `pidfd` | 进程退出（`poll` 可读） |
| `inotify` / `fanotify` | 文件系统事件 |
| `userfaultfd` | 缺页事件交给用户态处理（虚拟机热迁移、CRIU） |
| io_uring | 完成事件 |

## 7. System V IPC 与 IPC 命名空间

- 以 key（`ftok` 生成）标识，对象在内核中持续存在直到显式删除或重启，泄漏常见。
- `ipcs` / `ipcrm` 查看与删除；限制在 `/proc/sys/kernel/{shmmax,shmall,msgmax,sem}`。
- **IPC 命名空间**（`CLONE_NEWIPC`）隔离 SysV 对象与 POSIX 消息队列，容器之间互不可见。

## 8. 选型建议

| 需求 | 推荐 |
|---|---|
| 父子进程简单流式传输 | 管道 |
| 本机客户端-服务器、需要传 fd 或认证对方 | Unix 域 socket（`SO_PEERCRED`） |
| 大块数据、低延迟 | `memfd` / `shm_open` 共享内存 + futex 或 eventfd 通知 |
| 线程/进程间唤醒且集成事件循环 | eventfd |
| 监控子进程 | `pidfd` + epoll |
| 处理信号 | `signalfd` 或专用 `sigwait` 线程 |
| 内核 ↔ 用户态配置与事件 | netlink / generic netlink |

## 9. 关键文件

| 路径 | 内容 |
|---|---|
| `fs/pipe.c`、`fs/splice.c` | 管道与 splice |
| `kernel/signal.c` | 信号发送、`get_signal`、`sigprocmask` |
| `arch/x86/kernel/signal.c` | 信号栈帧构造与 `rt_sigreturn` |
| `kernel/futex/` | futex 实现（`core.c`、`waitwake.c`、`pi.c`、`requeue.c`） |
| `ipc/` | System V IPC、POSIX 消息队列 |
| `mm/shmem.c` | 共享内存/tmpfs 后端 |
| `fs/eventfd.c`、`fs/signalfd.c`、`fs/timerfd.c`、`kernel/pid.c` | fd 化接口 |
| `net/unix/af_unix.c` | Unix 域 socket |

## 小结

IPC 的设计在内核中呈现两个趋势：一是**快路径留在用户态**（futex 无竞争不进内核，共享内存不经内核拷贝）；二是**事件源 fd 化**（eventfd、signalfd、pidfd），以便统一放进 epoll/io_uring。信号是最古老也最容易误用的机制，理解"发送时设置 pending 并唤醒、返回用户态时才投递、通过伪造栈帧调用 handler"这一流程，就能解释 `EINTR`、`SA_RESTART`、异步信号安全等所有相关规则。
