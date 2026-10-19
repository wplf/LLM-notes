# 第 12 篇 安全、命名空间与 cgroup

> 目标：说清内核的访问控制模型（UID/GID、capabilities、LSM、seccomp），以及容器依赖的隔离原语（namespace 与 cgroup）分别解决什么问题。

## 1. 访问控制的基本模型

### 1.1 凭证（credentials）

每个任务持有 `const struct cred *`（不可变，改动要新建并 `commit_creds`，因此可以无锁共享与 RCU 读取）：

| 字段 | 含义 |
|---|---|
| `uid` / `gid` | 真实 ID |
| `euid` / `egid` | 有效 ID（多数权限检查用它） |
| `suid` / `sgid` | saved ID（`setuid` 程序切换权限用，可"记住"原身份） |
| `fsuid` / `fsgid` | 文件访问专用 ID（NFS 服务器需要模拟他人访问） |
| `cap_effective` / `cap_permitted` / `cap_inheritable` / `cap_ambient` | 能力集（见下） |
| `security` | LSM 私有数据（SELinux 的 label、AppArmor 的 profile） |
| `user_ns` | 用户命名空间 |

进程有真实/有效/保存三重 UID 的原因：`su`、`sudo`、setuid 程序需要临时提权再降权而不丢失"能再提权"的能力。

### 1.2 文件权限

- 传统 12 位：`rwx` × (owner, group, other) + setuid/setgid/sticky。
- **setuid 位**：执行时 euid 变成文件所有者（`/usr/bin/passwd` 为 root 所有且有 setuid）。这是本地提权漏洞最集中的地方——历史上大量 CVE 源于 setuid 程序。
- **sticky 位**（`/tmp`）：目录里只有文件所有者或目录所有者能删除。
- **ACL**（`setfacl`）：更细粒度的按用户/组授权，`getxattr` 存储。
- **扩展属性**：`security.selinux`（label）、`security.capability`（文件能力）、`user.*`。
- `O_NOFOLLOW`、`O_PATH`、`openat2` 的 `RESOLVE_*` 就是为安全地处理路径（防符号链接攻击）设计的。

### 1.3 能力（capabilities）：把 root 拆开

root 的权限被拆成约 40 项（`include/uapi/linux/capability.h`）：

| 能力 | 允许 |
|---|---|
| `CAP_NET_ADMIN` | 配置网络接口、路由、防火墙 |
| `CAP_NET_BIND_SERVICE` | 绑定 <1024 端口 |
| `CAP_NET_RAW` | 原始 socket、`ping` |
| `CAP_SYS_ADMIN` | 万能（mount、namespace 管理等），"新的 root"，应尽量避免 |
| `CAP_SYS_PTRACE` | ptrace 别的进程 |
| `CAP_SYS_MODULE` | 加载内核模块 |
| `CAP_DAC_OVERRIDE` | 绕过文件读写权限 |
| `CAP_CHOWN` / `CAP_FOWNER` | 改文件所有者 / 忽略所有者检查 |
| `CAP_BPF`、`CAP_PERFMON` | 5.8 起从 `CAP_SYS_ADMIN` 拆出 |

**文件能力**（`setcap 'cap_net_bind_service=+ep' /usr/bin/mydaemon`）：让非 root 程序获得单项权限，替代 setuid root，风险小得多。

四个能力集的关系：

```
permitted ⊇ effective（真正生效的）
permitted ⊇ inheritable（exec 时可继承给子程序）
ambient ⊆ permitted ∩ inheritable（非特权二进制执行后仍保留）
exec 后：new_permitted = (file_inheritable & old_inheritable) | (file_permitted & bounding) | ambient
```

此外还有 **bounding set**（进程能获得的能力上限，`capsh --drop`）和 **securebits**。

### 1.4 用户命名空间与 ID 映射

`unshare -Ur` 让非 root 用户在自己命名空间里成为"root"（uid 0 映射到宿主的一个普通 uid）。这大幅降低了测试和 rootless 容器（Podman、rootless Docker）的门槛，但也使得"在用户命名空间内拥有 `CAP_SYS_ADMIN`"成为一个需要谨慎对待的攻击面——内核历史上不少提权漏洞需要用户命名空间，因此有 `kernel.unprivileged_userns_clone`、`user.max_user_namespaces` 之类的开关。

## 2. LSM：可插拔的安全策略

**LSM（Linux Security Modules）** 在内核的关键操作点插入钩子（hook），由安全模块决定放行还是拒绝：

```
系统调用 → 传统权限检查（uid/gid、能力）
              ↓ 通过
          security_xxx() 钩子 —— 依次调用各 LSM —— 任一拒绝则失败
              ↓
          实际执行
```

可以**堆叠**（stacking，5.1 起正式支持）：例如同时启用 `capability` + `landlock` + `apparmor`。

| 模块 | 模型 | 特点 |
|---|---|---|
| `capability` | 传统能力检查（总在最底层） | 总是启用 |
| **SELinux** | 强制访问控制（MAC），类型强制（type enforcement） | 每个对象有 label，策略决定"哪些类型能对哪些类型做什么"；粒度最细，配置最复杂。RHEL/Fedora/Android 默认 |
| **AppArmor** | 基于**路径**的 profile | 用简单文本规则限制程序能访问的路径与能力；Ubuntu/SUSE 默认 |
| **Smack** | 简单标签 | 嵌入式/汽车 |
| **Landlock**（5.13 起） | **非特权进程自己**限制自己 | 用户态可用的沙箱原语，逐步支持文件系统、网络、IPC |
| **Yama** | 限制 ptrace 范围（`ptrace_scope`） | 阻止进程读取无关进程内存 |

常见钩子：`inode_permission`、`file_open`、`sb_mount`、`socket_create`、`task_kill`、`bprm_check_security`（执行前检查）、`mmap_file`。

查看：`getenforce`/`sestatus`、`aa-status`、`cat /sys/kernel/security/lsm`（已启用的 LSM 列表）。

## 3. seccomp：系统调用白名单

见第 2 篇的实现位置，这里补充使用层面：

```c
/* 只允许 read/write/exit，其余杀进程 */
struct sock_filter filter[] = {
    BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
    BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_read,  0, 1), BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
    /* ... */
    BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
};
```

- 返回值：`ALLOW`、`ERRNO(data)`、`TRAP`、`TRACE`、`LOG`、`USER_NOTIF`、`KILL_PROCESS`/`KILL_THREAD`。
- 过滤器一旦安装**不能放宽**（只能继续加严），且会**被 fork/exec 继承**。
- `SECCOMP_RET_USER_NOTIF` 让一个"监管进程"实时裁决：容器运行时（如 gVisor 风格的轻量方案、部分 runc 特性）用它实现本不该允许的调用。
- Docker 默认的 seccomp profile 屏蔽了约 40 个危险系统调用（`mount`、`reboot`、`kexec_load`、`add_key` 等）。

## 4. 命名空间（Namespace）

| 命名空间 | 隔离内容 | 标志 | 内核加入版本 |
|---|---|---|---|
| Mount | 挂载树 | `CLONE_NEWNS` | 2.4.19 |
| UTS | 主机名、域名 | `CLONE_NEWUTS` | 2.6.19 |
| IPC | SysV IPC、POSIX 消息队列 | `CLONE_NEWIPC` | 2.6.19 |
| PID | 进程号空间（PID 1 是空间内的 init） | `CLONE_NEWPID` | 2.6.24 |
| Network | 网卡、路由表、iptables、端口空间 | `CLONE_NEWNET` | 2.6.29 |
| User | UID/GID 映射、能力集 | `CLONE_NEWUSER` | 3.8 |
| Cgroup | cgroup 根视图 | `CLONE_NEWCGROUP` | 4.6 |
| Time | `CLOCK_MONOTONIC`/`BOOTTIME` 偏移 | `CLONE_NEWTIME` | 5.6 |

```bash
unshare --pid --net --mount --uts --ipc --fork --mount-proc /bin/bash
ls -l /proc/self/ns/            # 每个进程的命名空间 inode（相同 inode = 同一命名空间）
nsenter -t <pid> -n -m          # 进入某进程的命名空间（调试容器神器）
```

**容器的本质** = namespace（隔离视图）+ cgroup（限制资源）+ rootfs（overlayfs 等）+ capabilities/seccomp/LSM（限制权限）+ 一个 init 进程。容器不是虚拟化：共享同一个内核，因此**内核漏洞对容器是逃逸路径**，而虚拟机有独立的攻击边界。

PID 命名空间的几个后果：容器内看到的 PID 从 1 开始；容器内 PID 1 收不到内核直接发送的致命信号（需自己处理 `SIGTERM`）；宿主上可见进程的 NSpid 列（`/proc/<pid>/status`）。

## 5. cgroup：资源控制

cgroup v1（多层级，每个控制器一棵树）已被 v2（**单一层级，统一树**）取代；现代发行版默认 v2（挂在 `/sys/fs/cgroup`，可通过 `cgroup_no_v1=all` 强制）。

### v2 核心概念

```
/sys/fs/cgroup/
├─ cgroup.controllers      可用控制器
├─ cgroup.subtree_control  在子层级启用哪些控制器
├─ cgroup.procs            属于本组的进程
├─ cgroup.events           populated/frozen 状态
├─ cgroup.stat
├─ <my-group>/
│   ├─ cgroup.procs
│   ├─ memory.max / memory.high / memory.current
│   ├─ cpu.max / cpu.weight / cpu.stat
│   ├─ io.max / io.weight / io.latency
│   └─ pids.max / cgroup.freeze / rdma.max / hugetlb.*
```

| 控制器 | 关键文件 | 说明 |
|---|---|---|
| memory | `memory.max`（硬限）、`memory.high`（软限，先节流再回收）、`memory.swap.max`、`memory.oom.group` | 达到 `max` 且回收失败 → cgroup OOM |
| cpu | `cpu.weight`（比例）、`cpu.max`（`quota period` 硬限） | 见第 3 篇 |
| cpuset | `cpuset.cpus`、`cpuset.mems` | 绑核与 NUMA |
| io | `io.max`、`io.weight`、`io.latency`、`io.cost.*` | 见第 8 篇 |
| pids | `pids.max` | 防 fork bomb |
| freezer | `cgroup.freeze` | 原子地冻结整组进程（取代 SIGSTOP） |

### 关键实践要点

- **"no internal process" 规则**：v2 中一个 cgroup 只有在其内部没有进程时，才能把控制器下发给子 cgroup。所以结构通常是"中间层只做组织，进程都在叶子节点"。
- **memory.high 优先于 memory.max**：先用 `high` 做软限流，让应用自己回收，避免 `max` 触发 OOM。
- **PSI（Pressure Stall Information）**：`/proc/pressure/{cpu,memory,io}` 与每个 cgroup 的 `cpu.pressure`/`memory.pressure`/`io.pressure`，给出"因为资源不足而停顿的时间比例"，是比负载值更直接的饱和度指标。
- **systemd** 是实际的管理者：`systemd-cgtop`、`systemctl status` 里的 `Memory:`/`Tasks:` 就是 cgroup 数据；`systemd-run --scope -p MemoryMax=1G cmd` 快速起一个受限单元。
- **`cgroup.kill`**（5.14）：一次性杀掉整组所有进程。

## 6. 内核自身的安全加固

| 机制 | 作用 |
|---|---|
| KASLR | 内核与模块加载地址随机化（`nokaslr` 可关） |
| 栈保护（`-fstack-protector-strong`） | 栈 canary |
| `CONFIG_SLAB_FREELIST_RANDOM`/`HARDENED` | 内存分配器加固 |
| `CONFIG_RANDOMIZE_MEMORY` | 内核内存段随机化 |
| `CONFIG_STRICT_KERNEL_RWX` | 内核代码只读、数据不可执行 |
| `CONFIG_IO_STRICT_DEVMEM` | 限制 `/dev/mem` |
| `lockdown` | 完整性模式：限制 kexec、模块签名、`/dev/mem` |
| 模块签名（`CONFIG_MODULE_SIG`） | 只加载签名的模块（Secure Boot 需要） |
| `CONFIG_INIT_ON_ALLOC_DEFAULT_ON` | 分配内存清零（减少信息泄漏） |
| AMD SEV-SNP / Intel TDX | 机密计算：虚拟机内存加密，宿主机和 hypervisor 无法读取 |
| `spectre/meltdown` 缓解 | 微码 + KPTI + retpoline/IBRS，成本可测（`mitigations=` 控制） |

## 7. 容器安全的分层防线

```
能力（capabilities）：删掉 CAP_SYS_ADMIN 等
   ↓
seccomp：限制系统调用集合
   ↓
LSM（AppArmor/SELinux profile）：限定文件与网络访问
   ↓
namespace + user namespace：缩小可见范围，非 root 映射
   ↓
cgroup：限制资源（CPU/内存/IO/PID）
   ↓
只读 rootfs + no-new-privileges + 最小镜像
```

`docker run --cap-drop=ALL --read-only --security-opt no-new-privileges` 是常见的加固起点。

## 8. 关键文件

| 路径 | 内容 |
|---|---|
| `kernel/cred.c`、`include/linux/cred.h` | 凭证与能力 |
| `security/` | LSM 框架（`security.c`）与各模块（`selinux/`、`apparmor/`、`landlock/`、`yama/`） |
| `kernel/seccomp.c` | seccomp |
| `kernel/nsproxy.c`、`kernel/pid_namespace.c`、`net/core/net_namespace.c`、`fs/namespace.c`、`kernel/user_namespace.c` | 各命名空间 |
| `kernel/cgroup/` | cgroup v2 核心 |
| `mm/memcontrol.c`、`kernel/sched/core.c`（cpu 控制器）、`block/blk-cgroup.c` | 各控制器 |

## 小结

内核的安全是**多层叠加**而非单点：传统 DAC（uid/gid/权限位）之上有能力拆分，能力之上有 MAC（LSM），系统调用层面有 seccomp，进程自身可用 Landlock 自限。容器的隔离完全由 namespace（视图）+ cgroup（资源）+ 上述权限机制组成，共享内核这一事实决定了容器安全必须"纵深防御"，且内核漏洞的严重性对容器尤高。
