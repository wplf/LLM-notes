# 第 9 篇 网络协议栈

> 目标：跟踪一个数据包的完整收发路径，理解 `sk_buff`、NAPI、socket 层、TCP 状态与拥塞控制、netfilter 以及 XDP/eBPF 这些"捷径"处在哪一层。

## 1. 分层与对应代码

```
应用：socket()/bind()/connect()/send()/recv()/epoll
──────────────── 系统调用 ────────────────
socket 层（net/socket.c）：struct socket + struct sock，协议无关接口 proto_ops
传输层（net/ipv4/tcp*.c、udp.c）：TCP 状态机、重传、拥塞控制；UDP
网络层（net/ipv4/ip_*.c、route.c、ipv6/）：路由查找、分片、转发、netfilter 钩子
邻居子系统（net/core/neighbour.c、ipv4/arp.c）：IP → MAC
设备无关层（net/core/dev.c）：NAPI、GRO/GSO、qdisc 流量控制、RPS/RFS
网卡驱动（drivers/net/ethernet/...）：环形缓冲区、DMA、中断
──────────────── 硬件 ────────────────
```

## 2. `sk_buff`：数据包的载体

`struct sk_buff`（`include/linux/skbuff.h`）描述一个数据包，**包头与数据分离**：

```
         head          data                  tail          end
          │             │                     │             │
          ▼             ▼                     ▼             ▼
  [ headroom ][ 以太网头|IP头|TCP头|payload ][ tailroom ][ skb_shared_info ]
                                                              └─ frags[]：额外的页片段（零拷贝/大包）
                                                              └─ frag_list：skb 链
```

- 各层处理时**移动指针而不是拷贝数据**：收包时 `skb_pull` 剥掉头部往上交，发包时 `skb_push` 往前加头部。因此分配时会预留 headroom。
- `skb->network_header`、`transport_header`、`mac_header` 记录各层头部偏移。
- 克隆（`skb_clone`）共享数据只复制描述符（抓包、多播）；`skb_copy` 才复制数据。
- 其它重要字段：`dev`、`sk`（所属 socket）、`len`/`data_len`、`protocol`、`mark`、`priority`、`hash`、`tstamp`、`cb[48]`（各层私有暂存区）。

## 3. 收包路径（RX）

```
① 网卡 DMA 把帧写入驱动预先放好的 RX 环形缓冲区（描述符指向的页）
② 网卡发 MSI-X 中断（每个 RX 队列一个向量，绑定到某个 CPU）
③ 硬中断处理：关掉该队列的中断，napi_schedule() → 挂到本 CPU 的 poll 列表，触发 NET_RX_SOFTIRQ
④ softirq：net_rx_action() → 驱动的 napi->poll()
     · 一次最多处理 budget（默认 64）个包，全局 netdev_budget（300）/ netdev_budget_usecs（2ms）
     · 构造 skb（或 build_skb 直接包装已有页），补充 RX 环
     · XDP 程序（若有）在这里最先执行，可直接 DROP / TX / REDIRECT
     · GRO：把同一流的多个小包合并成一个大 skb，减少上层处理次数
     · 处理完且包少于 budget → napi_complete_done() 重新开中断
⑤ __netif_receive_skb：
     · 抓包点：AF_PACKET（tcpdump）在这里拿到副本
     · tc ingress（clsact / eBPF）
     · 按 skb->protocol 分发到 ip_rcv / ipv6_rcv / arp_rcv
⑥ ip_rcv：校验 → netfilter PREROUTING → 路由查找（ip_route_input）
     · 本机 → ip_local_deliver（重组分片）→ netfilter INPUT → tcp_v4_rcv / udp_rcv
     · 转发 → ip_forward → FORWARD → ip_output
⑦ tcp_v4_rcv：按四元组查找 socket（哈希表：established / listen）
     · socket 被用户持有（正在 recv 中）→ 放入 backlog，稍后处理
     · 否则 tcp_rcv_established：快速路径（预测下一个序号）、发 ACK、放入接收队列
⑧ 唤醒在 sk->sk_wq 上等待的进程（recv 阻塞者或 epoll）
⑨ 应用 recv() → tcp_recvmsg：从接收队列 copy 到用户缓冲区，释放 skb，可能更新接收窗口
```

### NAPI 的意义

纯中断驱动在高包率下会产生**中断活锁**（CPU 全部用来响应中断，没时间处理包）。NAPI 是"中断 + 轮询"混合：第一个包用中断唤醒，之后关中断批量轮询，直到队列清空再开中断。低负载延迟低，高负载吞吐高。

### 多核扩展

| 技术 | 层次 | 作用 |
|---|---|---|
| **RSS**（Receive Side Scaling） | 硬件 | 网卡按流哈希把包分到多个 RX 队列，各队列中断绑不同 CPU |
| **RPS**（Receive Packet Steering） | 软件 | 网卡单队列时，在软件中按哈希把包分发到其它 CPU 的 backlog |
| **RFS**（Receive Flow Steering） | 软件 | 把包送到**消费该 socket 的应用线程所在的 CPU**，缓存更热 |
| **aRFS** | 硬件 | 让网卡硬件实现 RFS |
| **XPS** | 发送侧 | 选择与当前 CPU 对应的 TX 队列 |
| `SO_REUSEPORT` | socket | 多个 socket 监听同一端口，内核按哈希分配连接，多线程服务器免争用 accept |

## 4. 发包路径（TX）

```
send() → sock_sendmsg → tcp_sendmsg
   · 用户数据拷贝进 skb（或 MSG_ZEROCOPY 引用用户页），追加到写队列
   · 是否立即发送由拥塞窗口、接收窗口、Nagle 算法、TSQ（TCP Small Queues）决定
tcp_write_xmit → tcp_transmit_skb：构建 TCP 头、计算校验和（通常交给网卡 offload）
ip_queue_xmit：路由（缓存在 socket 上）、构建 IP 头 → netfilter OUTPUT → POSTROUTING
ip_finish_output → 邻居层：查 ARP 表，填以太网头（未解析时排队等待 ARP 回复）
dev_queue_xmit：
   · 选择 TX 队列（XPS）
   · 进入 qdisc（排队规则）：fq_codel / fq / mq / htb / tbf ...
   · GSO：大包延迟到这里（或交给网卡 TSO）才切分成 MTU 大小
driver ndo_start_xmit：把 skb 映射成 DMA 描述符放进 TX 环，敲门铃
网卡发送完成 → 中断 / NAPI 中回收 TX 描述符，释放 skb
```

**TSO/GSO/GRO/校验和卸载**：让协议栈处理 64KB 的"超级包"，由网卡或最后一刻的软件切分/合并，单包处理成本被摊薄。`ethtool -k eth0` 查看各项 offload。

**qdisc**：默认是 `fq_codel`（各发行版可能为 `fq`），按流公平排队并控制排队延迟（对抗 bufferbloat）。`tc qdisc show` 查看；`tc` 还能做限速（`tbf`、`htb`）、延迟/丢包模拟（`netem`）。BBR 拥塞控制推荐配合 `fq` 使用，以获得按流的 pacing。

## 5. Socket 层

- `struct socket`：面向 VFS 的一面（有 inode，所以 socket 是 fd），`ops` 指向 `proto_ops`（`inet_stream_ops` 等）。
- `struct sock`（及其扩展 `inet_sock` → `inet_connection_sock` → `tcp_sock`，"继承"链靠嵌套结构）：协议状态、收发队列、缓冲区限额（`sk_rcvbuf`/`sk_sndbuf`）、等待队列。
- 地址族：`AF_INET`、`AF_INET6`、`AF_UNIX`（本机 IPC，可传递 fd：`SCM_RIGHTS`）、`AF_NETLINK`（内核与用户态通信）、`AF_PACKET`（原始帧）、`AF_XDP`、`AF_VSOCK`（虚拟机与宿主）。

### 等待与多路复用

| 机制 | 复杂度 | 特点 |
|---|---|---|
| `select` | O(n)，fd 上限 1024 | 每次调用拷贝整个集合 |
| `poll` | O(n) | 无上限，但仍每次全扫 |
| **`epoll`** | O(就绪数) | 兴趣列表（红黑树）+ 就绪列表；`f_op->poll` 注册回调，事件发生时把 epitem 加入就绪列表 |

`epoll` 的边沿触发（`EPOLLET`）与水平触发、`EPOLLEXCLUSIVE`（避免惊群）、`EPOLLONESHOT` 是高性能服务器常用选项。

## 6. TCP 的内核实现要点

### 连接建立与队列

```
client                 server（listen）
 SYN ──────────────→   创建 request_sock（轻量），放入 SYN 队列（半连接）
     ←────────── SYN+ACK
 ACK ──────────────→   创建完整 sock，移入 accept 队列（全连接）
                        accept() 从 accept 队列取走
```

- 全连接队列长度 = `min(listen 的 backlog, net.core.somaxconn)`；满了会丢弃 ACK 或回 RST（`netstat -s | grep -i listen` 看溢出计数）。
- **SYN cookies**（`net.ipv4.tcp_syncookies`）：半连接队列满时，把连接状态编码在 SYN+ACK 的序号里，不占内存，抵御 SYN flood。
- **TFO**（TCP Fast Open）：用 cookie 在 SYN 里携带数据，节省 1 RTT。

### 可靠传输与定时器

| 定时器 | 作用 |
|---|---|
| 重传定时器（RTO） | 按 RTT 估计（SRTT + 4×RTTVAR）计算，最小 200ms，指数退避 |
| 延迟 ACK | 等待一小段时间（最长约 40ms）合并 ACK，或捎带在数据中 |
| 零窗口探测 | 对端窗口为 0 时周期探测 |
| keepalive | 空闲连接探活（默认 2 小时，`tcp_keepalive_time`） |
| TIME_WAIT | 主动关闭方保持 2MSL（Linux 固定 60 秒），防止旧报文干扰新连接 |

快速重传（3 个重复 ACK）、SACK（选择性确认）、RACK-TLP（基于时间的丢包检测与尾部丢包探测）都已默认开启。

### 拥塞控制

可插拔框架（`tcp_congestion_ops`），`sysctl net.ipv4.tcp_congestion_control` 或 `setsockopt(TCP_CONGESTION)` 按连接选择：

| 算法 | 依据 | 特点 |
|---|---|---|
| Reno / NewReno | 丢包 | 经典 AIMD |
| **CUBIC**（默认） | 丢包 | 窗口按时间的三次函数增长，适合高带宽长延迟网络 |
| **BBR** | 带宽与 RTT 测量 | 主动估计瓶颈带宽和最小 RTT，不以丢包为拥塞信号；在有随机丢包的链路上吞吐远高于 CUBIC |
| DCTCP | ECN 标记比例 | 数据中心内部低延迟 |

可以用 eBPF（`struct_ops`）编写自定义拥塞控制算法。

### 缓冲区与自动调优

`net.ipv4.tcp_rmem`/`tcp_wmem`（min/default/max 三元组）控制每 socket 缓冲；接收侧自动调优（`tcp_moderate_rcvbuf`）按 BDP（带宽 × 时延）动态扩大窗口。全局内存压力由 `tcp_mem` 控制。

## 7. netfilter 与防火墙

netfilter 在 IP 层设置 5 个钩子：

```
            PREROUTING ──→ 路由 ──→ FORWARD ──→ POSTROUTING ──→ 出网卡
 入网卡 ──→       │                                ↑
                  ▼                                │
               INPUT ──→ 本机进程 ──→ OUTPUT ──→ 路由
```

- **iptables**（旧）：按表（filter/nat/mangle/raw）和链组织规则，线性匹配，规则多时性能下降。
- **nftables**（新）：统一框架，类似字节码虚拟机，支持集合（set）与映射（map），O(1) 查找大量地址。现代发行版的 iptables 命令多为 `iptables-nft` 兼容层。
- **conntrack**：连接跟踪，记录每条流的状态，是有状态防火墙和 NAT 的基础（`conntrack -L`；`nf_conntrack_max` 满了会丢包）。
- Kubernetes 的 kube-proxy（iptables/IPVS 模式）、Docker 的端口映射都是 netfilter NAT 规则。

## 8. 可编程数据路径：XDP、tc-BPF 与 AF_XDP

| 技术 | 位置 | 能力 |
|---|---|---|
| **XDP** | 驱动收包最早点，`skb` 尚未分配 | `XDP_DROP`/`PASS`/`TX`/`REDIRECT`；DDoS 防护、负载均衡（Katran、Cilium），单核可达千万级 pps（估计值） |
| **tc eBPF**（clsact） | ingress/egress，已有 skb | 可修改包、重定向，Cilium 用其实现容器网络与策略 |
| **AF_XDP** | XDP 重定向到用户态共享内存环（UMEM） | 用户态高速收发，类似 DPDK 但仍保留内核驱动 |
| socket 层 BPF | `SO_ATTACH_FILTER`、`sk_msg`、`sockmap`、cgroup socket 钩子 | 过滤、socket 间直接转发、按 cgroup 策略 |

内核旁路方案对比：DPDK 完全绕过内核（用户态驱动 + 轮询），性能最高但失去内核协议栈与工具；XDP/AF_XDP 是在内核内的折中。

## 9. 虚拟网络设备

| 设备 | 用途 |
|---|---|
| `lo` | 回环 |
| `veth` 对 | 两端互通的"网线"，连接容器网络命名空间与宿主 |
| `bridge` | 软件二层交换机（`docker0`） |
| `bond` / `team` | 链路聚合 |
| `vlan`、`macvlan`、`ipvlan` | VLAN 与在一个物理网卡上虚拟多个 MAC/IP |
| `tun` / `tap` | 用户态程序收发三层/二层帧（VPN、虚拟机） |
| `vxlan` / `geneve` / `wireguard` | 隧道与加密 overlay |

网络命名空间（`ip netns`）给每个容器独立的设备、路由表、iptables 规则、socket 端口空间。

## 10. 观测与调优

```bash
ss -tanpi                         # socket 状态、cwnd、rtt、重传（-i 显示 tcp_info）
nstat -az | grep -iE 'retrans|overflow|drop'
ip -s link                        # 设备收发统计与丢包
ethtool -S eth0                   # 驱动/硬件级统计（rx_missed、队列计数）
ethtool -l / -g / -k eth0         # 队列数、环大小、offload
cat /proc/net/softnet_stat        # 每 CPU 的 softirq 处理数、dropped、time_squeeze（budget 用完）
tcpdump -i eth0 -nn port 443
perf trace -e 'net:*' / bpftrace 'tracepoint:skb:kfree_skb { @[kstack] = count(); }'  # 找丢包点
```

`dropwatch`、`pwru`（基于 eBPF 跟踪 skb 经过的每个函数）对定位"包在哪丢的"很有效。6.x 的 `kfree_skb_reason` tracepoint 直接给出丢包原因枚举。

## 11. 关键文件

| 路径 | 内容 |
|---|---|
| `include/linux/skbuff.h`、`net/core/skbuff.c` | `sk_buff` |
| `net/core/dev.c` | `netif_receive_skb`、`dev_queue_xmit`、NAPI、RPS |
| `net/core/gro.c` | GRO |
| `net/socket.c` | socket 系统调用 |
| `net/ipv4/ip_input.c`、`ip_output.c`、`route.c` | IP 收发与路由 |
| `net/ipv4/tcp_input.c`、`tcp_output.c`、`tcp_ipv4.c`、`tcp_cubic.c`、`tcp_bbr.c` | TCP |
| `net/netfilter/` | netfilter、conntrack、nftables |
| `net/sched/` | qdisc 与 tc |
| `fs/eventpoll.c` | epoll |
| `drivers/net/ethernet/intel/ice/` 等 | 典型网卡驱动 |

## 小结

网络栈的设计主线是**减少每包开销**：`sk_buff` 移动指针不拷贝，NAPI 批量轮询，GRO/GSO/TSO 把多包当一包处理，RSS/RPS/RFS 把流分到多核且保持缓存局部性。在协议层面，TCP 实现集中体现了可插拔思想（拥塞控制、qdisc）；在可编程性方面，netfilter 提供传统钩子，XDP/tc-BPF 提供更早、更快的处理点。
