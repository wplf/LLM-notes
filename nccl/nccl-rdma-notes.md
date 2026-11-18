# NCCL 与 RDMA 学习记录

> 记录日期：2026-11-18
> 基于 [NVIDIA/nccl](https://github.com/NVIDIA/nccl/tree/v2.32.6-1) 仓库代码（NCCL v2.32.6）的问答整理，原对话为中英混合，已统一翻译为中文。

## 目录

1. [NCCL 能做什么？](#1-nccl-能做什么)
2. [各种 RDMA 技术介绍](#2-各种-rdma-技术介绍)
3. ["verbs API" 中的 verb 是什么意思？](#3-verbs-api-中的-verb-是什么意思)
4. [Fabric 是什么意思？](#4-fabric-是什么意思)
5. [GDR、GDRCopy、GDAKI、Data Direct 之间的关系](#5-gdrgdrcopygdakidata-direct-之间的关系)
6. [GDRCopy 和 GDAKI 哪个更快？](#6-gdrcopy-和-gdaki-哪个更快)
7. [NCCL 通信一般都是 GDRCopy + CPU proxy thread 吗？](#7-nccl-通信一般都是-gdrcopy--cpu-proxy-thread-吗)

---

## 1. NCCL 能做什么？

**问：** 帮我理解一下 NCCL 能做什么？

**答：**

**NCCL**（NVIDIA Collective Communications Library，读作 "nickel"）是 GPU 之间交换数据所用的库。在多 GPU 上运行的程序，例如 PyTorch 分布式训练、vLLM 和 SGLang 推理，都通过调用 NCCL 在 GPU 之间搬运张量。这些 GPU 可以在同一台服务器内，也可以分布在多台服务器上。

### 核心概念

每个进程管理一块 GPU，并加入一个 **communicator（通信器）**，即一组 GPU，每块 GPU 有一个 "rank" 编号。NCCL 提供在 CUDA stream 上运行的通信操作，并自动选择最快的路径：节点内走 NVLink/NVSwitch 或 PCIe，节点间走 InfiniBand/RoCE/以太网。它还会根据检测到的硬件拓扑选择 ring 或 tree 等算法。

### 主要能力（来自公开 API [src/nccl.h.in](https://github.com/NVIDIA/nccl/blob/v2.32.6-1/src/nccl.h.in)）

**1. 集合通信（组内所有 GPU 共同参与）**

| 操作 | 作用 | 典型用途 |
|---|---|---|
| `ncclAllReduce` | 对所有 GPU 上的缓冲区求和（或 max、min 等），每个 GPU 都得到结果 | 数据并行训练中平均梯度 |
| `ncclAllGather` | 每个 GPU 贡献一部分，所有 GPU 都得到完整拼接结果 | FSDP/ZeRO：收集分片权重 |
| `ncclReduceScatter` | 先归约，再让每个 GPU 只保留自己的分片 | FSDP 梯度分片 |
| `ncclBroadcast` | 一个 GPU 发给所有 GPU | 同步初始权重 |
| `ncclReduce` | 归约到单个 root GPU | |
| `ncclAlltoAll`、`ncclGather`、`ncclScatter` | 重新分发数据 | MoE 专家路由、张量重排 |

**2. 点对点通信：** `ncclSend` / `ncclRecv`，用于流水线并行和自定义通信模式。可以用 `ncclGroupStart` / `ncclGroupEnd` 把多次调用包在一起同时执行，也可以借此自己实现 all-to-all 之类的模式。

**3. 单边通信 / RMA：** `ncclPutSignal`、`ncclSignal`、`ncclWaitSignal`，以及内存窗口（`ncclCommWindowRegister`）。一块 GPU 直接写入另一块 GPU 的显存，不需要配对的 send/recv。

**4. 设备端 API**（[src/include/nccl_device/](https://github.com/NVIDIA/nccl/tree/v2.32.6-1/src/include/nccl_device)）：让你自己的 CUDA kernel 在 kernel 内部发起通信，包括 barrier、通过 NVLink 的 load/store（LSA）以及 GPU 发起的网络通信（GIN）。通信与计算 kernel 的融合（例如 MoE dispatch）就是靠它实现的。

**5. 通信器管理与容错：**
- `ncclCommSplit`：划分子组，用于张量并行、流水线并行、数据并行等。
- `ncclCommShrink` / `ncclCommGrow`：移除故障 rank 或加入新 rank。
- `ncclCommAbort`、`ncclCommRevoke`、`ncclCommGetAsyncError`：错误处理。
- `ncclCommSuspend` / `ncclCommResume`，以及内存统计。

**6. 内存辅助：** `ncclMemAlloc` 和 `ncclCommRegister` 用于注册缓冲区，使 NCCL 能够使用零拷贝和 NVLS（NVLink SHARP，即在交换机内部完成归约）。

### 仓库中的其他部分

- [plugins/](https://github.com/NVIDIA/nccl/tree/v2.32.6-1/plugins)：网络、tuner 和 profiler 插件，厂商可以接入自己的传输层或调优策略。
- [bindings/](https://github.com/NVIDIA/nccl/tree/v2.32.6-1/bindings)：语言绑定（最近的提交重新生成了 `nccl4py`）。
- [contrib/](https://github.com/NVIDIA/nccl/tree/v2.32.6-1/contrib)：扩展组件，例如 `tide`（感知布局的 FSDP2 集合通信，最新加入）、`nccl_ep`（MoE 专家并行）、`nccl4rust`、`nccl_checkpoint`、`custom_algos` 等。
- [docs/](https://github.com/NVIDIA/nccl/tree/v2.32.6-1/docs) 和 [README.md](https://github.com/NVIDIA/nccl/blob/v2.32.6-1/README.md)：构建说明。验证正确性和测性能时，通常配合独立的 **nccl-tests** 仓库（如 `all_reduce_perf`）。

### 实际中在哪里接触到它

一般很少直接调用 NCCL。PyTorch 用 `nccl` 后端执行 `dist.all_reduce(t)` 时，最终会调用 `ncclAllReduce`。了解 NCCL 主要帮助你做性能调优（各种 `NCCL_*` 环境变量、`NCCL_DEBUG=INFO`）以及排查通信卡死（hang）问题。

---

## 2. 各种 RDMA 技术介绍

**问：** 帮我理解一下不同的 RDMA。

**答：**

### RDMA 是什么

**RDMA（Remote Direct Memory Access，远程直接内存访问）** 指网卡（NIC）直接读写另一台机器的内存，CPU 和操作系统内核不参与数据通路。普通 TCP socket 的数据要从应用拷贝到内核再到网卡，对端再反向走一遍，每一步都消耗 CPU。而 RDMA：

- **零拷贝：** 网卡直接通过 DMA（无需 CPU 参与的拷贝）把你的缓冲区数据写入远端缓冲区。
- **内核旁路（kernel bypass）：** 应用通过 **verbs** API（`libibverbs`）直接向网卡提交任务。
- **效果：** 延迟约 1–2 µs（而非几十 µs），带宽可达线速（每块网卡 200–800 Gb/s），CPU 几乎不占用。

### Verbs 基本术语

| 术语 | 含义 |
|---|---|
| **MR（Memory Region，内存区域）** | 需要先"注册"的缓冲区，网卡才能访问。注册会锁定内存并返回密钥（lkey/rkey）。 |
| **QP（Queue Pair，队列对）** | 一个发送队列加一个接收队列，相当于两个端点之间的"连接"。NCCL 通常使用 **RC**（Reliable Connected，可靠连接）类型的 QP。 |
| **WQE / work request（工作请求）** | 提交到 QP 的一个操作（例如"把这 1 MB 写到那里"）。 |
| **CQ（Completion Queue，完成队列）** | 网卡在这里报告操作已完成。 |
| **双边操作**（`SEND`/`RECV`） | 接收方必须预先提交一个对应的接收请求。 |
| **单边操作**（`RDMA_WRITE`/`READ`） | 只有发起方参与，远端 CPU 完全感知不到。NCCL 的大块数据传输主要使用 RDMA_WRITE。 |

### Fabric 类型（线路上的 RDMA）

| 类型 | 运行在什么之上 | 主要特点 | 常见场景 |
|---|---|---|---|
| **InfiniBand（IB）** | 独立网络：IB 交换机、线缆和 Subnet Manager | 天生无损（基于信用的流控），延迟最低，支持自适应路由、SHARP 交换机内归约 | NVIDIA DGX/SuperPOD、大多数 HPC 和 AI 训练集群 |
| **RoCE v1** | 仅以太网二层 | 无法跨子网路由，基本已淘汰 | 旧系统 |
| **RoCE v2** | 以太网，封装在 UDP/IP 中（端口 4791） | 与 IB 使用相同的 verbs，因此 NCCL 用同一套代码。可路由，但以太网必须调成近似无损（PFC 和 ECN/DCQCN 拥塞控制），否则性能会严重下降 | 云和超大规模集群（Azure、Oracle、Meta、NVIDIA Spectrum-X） |
| **iWARP** | TCP/IP | 依靠 TCP 保证可靠，不需要无损网络，但开销更大 | AI 领域少见（部分 Intel/Chelsio 环境） |
| **AWS EFA** | AWS 自研的 **SRD** 协议 | 不是标准 verbs。乱序、多路径传输，通过 `libfabric` 使用 | AWS p4d/p5 实例 |
| **其他** | — | HPE Slingshot（Cray）、Cornelis Omni-Path、Windows **Network Direct** | HPC 站点、Windows |

**要点：** IB 和 RoCE 共用同一套 verbs API 和同一类网卡（NVIDIA ConnectX/BlueField），区别只在底层链路层。因此 NCCL 用一个传输模块同时支持两者。

### GPU 侧的 RDMA 技术

这些技术解决的是另一个问题：网卡如何访问 **GPU** 显存？

| 技术 | 作用 |
|---|---|
| **无 GDR（回退方案）** | GPU → 拷贝到主机内存 → 网卡从主机内存发送。多一次拷贝，PCIe 流量更大。 |
| **GPUDirect RDMA（GDR）** | 网卡通过 PCIe 直接 DMA 读写 GPU 显存。需要 `nvidia-peermem` 内核模块，或者较新的 **DMA-BUF** 方式（Linux 5.12+，无需额外模块）。 |
| **GDRCopy** | 让 CPU（NCCL 的 proxy 线程）以低延迟读写少量 GPU 显存中的值，例如标志位和 FIFO 指针。 |
| **GPUDirect Async / GDAKI** | 由 **GPU kernel 自己**向网卡提交任务，不需要 CPU proxy 线程。设备端 "GIN" API 基于它构建，MoE 专家并行库也用它。 |
| **Data Direct** | ConnectX/BlueField 的较新特性：即使拓扑上原本要绕经 CPU，网卡也能获得一条直达 GPU 的 PCIe 路径。 |

GDR 是否真正带来收益取决于 PCIe 拓扑：网卡和 GPU 在同一个 PCIe 交换芯片下时效果最好；如果流量要跨 CPU socket，反而可能更差。NCCL 通过 `NCCL_NET_GDR_LEVEL` 来判断。

### 与 NCCL 代码的对应关系

来自 [src/transport/](https://github.com/NVIDIA/nccl/tree/v2.32.6-1/src/transport)：

| 目录/文件 | 负责内容 |
|---|---|
| [net_ib/](https://github.com/NVIDIA/nccl/tree/v2.32.6-1/src/transport/net_ib) | **InfiniBand 和 RoCE**（verbs）。包含 [gdr.cc](https://github.com/NVIDIA/nccl/blob/v2.32.6-1/src/transport/net_ib/gdr.cc)、`gdaki/`（GPU 发起）、[gin.cc](https://github.com/NVIDIA/nccl/blob/v2.32.6-1/src/transport/net_ib/gin.cc) 以及端口故障切换的 "resiliency" 逻辑。 |
| [net_efa_gda/](https://github.com/NVIDIA/nccl/tree/v2.32.6-1/src/transport/net_efa_gda) | AWS EFA + GPU-direct async |
| [net_nd/](https://github.com/NVIDIA/nccl/tree/v2.32.6-1/src/transport/net_nd) | Windows Network Direct |
| [net_socket.cc](https://github.com/NVIDIA/nccl/blob/v2.32.6-1/src/transport/net_socket.cc) | 纯 TCP 回退方案，无 RDMA（慢） |
| [coll_net.cc](https://github.com/NVIDIA/nccl/blob/v2.32.6-1/src/transport/coll_net.cc)、[nvls.cc](https://github.com/NVIDIA/nccl/blob/v2.32.6-1/src/transport/nvls.cc) | 网络内归约：IB SHARP 和 NVLink SHARP |
| [plugins/net/](https://github.com/NVIDIA/nccl/tree/v2.32.6-1/plugins/net) | 外部网络插件，例如用于 libfabric 的 AWS `aws-ofi-nccl`，或 Google 的 fastsocket |

### 常用环境变量

- `NCCL_IB_HCA=mlx5_0,mlx5_1`：指定使用哪些网卡。
- `NCCL_IB_GID_INDEX=3`：**仅 RoCE**。选择 RoCE v2 / IPv4 的 GID 条目，是 RoCE 最常见的配置错误点。
- `NCCL_IB_TC`、`NCCL_IB_SL`：流量类别和服务等级，用于 RoCE 和 IB 的 QoS。
- `NCCL_NET_GDR_LEVEL`、`NCCL_DMABUF_ENABLE`、`NCCL_GDRCOPY_ENABLE`：控制 GPUDirect 行为。
- `NCCL_IB_DISABLE=1`：强制使用 TCP socket 传输，便于调试。
- `NCCL_IB_ADAPTIVE_ROUTING`、`NCCL_IB_SPLIT_DATA_ON_QPS`、`NCCL_IB_QPS_PER_CONNECTION`：性能调优。

### 检查本机实际情况

查看每个 RDMA 设备及其链路层（InfiniBand 或 Ethernet，即 RoCE）：
```bash
ibv_devinfo | grep -E "hca_id|link_layer|state"
```

查看 GPU ↔ 网卡的 PCIe 拓扑（PIX/PXB 对 GDR 有利，SYS 表示跨 CPU socket）：
```bash
nvidia-smi topo -m
```

检查 GPUDirect RDMA 支持是否已加载：
```bash
lsmod | grep -E "nvidia_peermem|nv_peer_mem"
```

然后用 `NCCL_DEBUG=INFO` 运行任意 NCCL 任务，查找类似的日志行：
- `NET/IB : Using [0]mlx5_0:1/IB`（原生 InfiniBand）或 `.../RoCE`（以太网上的 RDMA）
- `GPU Direct RDMA Enabled for HCA ...`
- `via NET/IB/0/GDRDMA`：数据路径确实是网卡 ↔ GPU 直通。如果只显示 `NET/IB/0`，说明数据经过主机内存中转。

---

## 3. "verbs API" 中的 verb 是什么意思？

**问：** "The app posts work directly to the NIC through the verbs API" 这句话中的 verb 是什么？

**答：**

这句话语法上的动词是 **"posts"**。这里的 "verbs" 是一个名字的一部分：**"verbs API"** 就是 RDMA 编程接口的名称。

### 为什么叫 "verbs"

InfiniBand 规范把 RDMA 网卡必须具备的能力描述为一组抽象的**动作**，并把这些动作称为 *verbs（动词）*，因为每一个都是你要"做"的事：创建、注册、提交、轮询。实现它们的软件库也沿用了这个名字。在 Linux 上它叫 **`libibverbs`**，所有函数都以 `ibv_` 开头（"InfiniBand verb"）。

每个函数就是你对网卡执行的一个"动词"：

| Verb（函数） | 动作 |
|---|---|
| `ibv_open_device` | 打开网卡 |
| `ibv_reg_mr` | **注册**内存区域 |
| `ibv_create_cq` | **创建**完成队列 |
| `ibv_create_qp` | **创建**队列对（即连接） |
| `ibv_modify_qp` | 让 QP 依次**切换**状态（INIT → RTR → RTS）以建立连接 |
| `ibv_post_send` | **提交**发送或 RDMA 写请求 |
| `ibv_post_recv` | **提交**接收缓冲区 |
| `ibv_poll_cq` | **轮询**已完成的任务 |

### 用通俗的话重写这句话

> "The app posts work directly to the NIC through the verbs API"

意思是：

> 程序调用 `ibv_post_send()`。这个函数把一个小的工作请求直接写入网卡内存中的队列，不经过系统调用，也不经过操作系统内核。随后网卡自己完成传输。

这里的 "post" 借用自"投递邮件"：你把请求投进网卡的信箱（队列），网卡取走并执行。

由于 InfiniBand 和 RoCE 使用同一套 API，即使在以太网上，人们也习惯用 "verbs" 泛指 RDMA 接口。NCCL 在 [src/transport/net_ib/](https://github.com/NVIDIA/nccl/tree/v2.32.6-1/src/transport/net_ib) 中调用这些函数。例如在 [p2p.cc](https://github.com/NVIDIA/nccl/blob/v2.32.6-1/src/transport/net_ib/p2p.cc) 中搜索 `ibv_post_send`，就能找到 NCCL 实际发出 RDMA 写操作的位置。

---

## 4. Fabric 是什么意思？

**问：** Fabric 是什么意思？

**答：**

在网络领域，**fabric** 指把计算机（或 GPU）连接在一起的整个互联网络，包括所有交换机、线缆、网卡以及它们通信所遵循的规则，并把这些当作**一个整体系统**来看待。

### 词源

这个词借自"布料"。布由许多纱线交织而成，纵横交错。集群网络也类似：许多链路在许多交换机之间交织，因此任意两台机器之间存在**多条路径**，而不是只有一条线。

```
   Server A ─┐          ┌─ Server C
             ├─ Switch ─┼─ Switch ─┐
   Server B ─┘    │     └──────────┼─ Server D
                  └─── Switch ─────┘
        （许多交叉的路径 = 一张"编织"出来的 fabric）
```

### "fabric" 与 "network" 的区别

两者含义有很大重叠，但 "fabric" 通常暗示：
- **高性能：** 低延迟、高带宽，为集群而建，而不是承载普通互联网流量。
- **作为一个整体设计：** 交换机、网卡和协议是配套的、统一管理的系统，例如由 Subnet Manager 管理的 InfiniBand fabric。
- **任意到任意：** 每个节点都能以接近满速访问其他任意节点（"无阻塞"或 "fat-tree" 设计）。

普通办公室或家庭以太网通常只叫 "network"，而 GPU 集群里的专用网络通常叫 "fabric"。

### 在前面的表格中

我说 **"Fabric 类型"** 时，指的是这类集群网络的不同*种类*，各自有自己的硬件和线路协议：
- **InfiniBand fabric：** IB 交换机、IB 线缆、IB 协议。
- **RoCE fabric：** 调成近似无损的以太网交换机，上面跑 RDMA。
- **EFA fabric：** AWS 自己的数据中心网络，使用 SRD 协议。

### GPU 领域中的 fabric

一个 AI 集群里通常会提到**两种** fabric：

| Fabric | 连接对象 | 技术 |
|---|---|---|
| **Scale-up fabric（纵向扩展）** | 服务器或机柜*内部*的 GPU | NVLink / NVSwitch（例如 NVL72 连接 72 块 GPU） |
| **Scale-out fabric（横向扩展）** | 数据中心内*跨服务器* | InfiniBand 或 RoCE（RDMA） |

NCCL 两者都会用。在 [src/transport/](https://github.com/NVIDIA/nccl/tree/v2.32.6-1/src/transport) 中，`p2p.cc` 和 `nvls.cc` 负责 NVLink fabric，`net_ib/` 负责 InfiniBand/RoCE fabric。

另一个相关名词是 **libfabric**（也叫 OFI，OpenFabrics Interfaces）。它是一个软件库，为多种 fabric 提供统一的 API。AWS EFA 使用它，因此 NCCL 通过 `aws-ofi-nccl` 插件访问 EFA。

---

## 5. GDR、GDRCopy、GDAKI、Data Direct 之间的关系

**问：** （引用第 2 节的"GPU 侧 RDMA 技术"表格）这些技术之间是什么关系？

**答：**

这五项不是互相竞争的选项。每一项解决不同的瓶颈，它们是层层叠加的。可以把每次网络传输拆成两个独立的问题来理解：

1. **数据路径：** 真正的字节走哪条路？
2. **控制路径：** 谁告诉网卡"现在发送这个"？又是谁、如何得知数据已就绪、传输已完成？

### 五者关系图

```
                    数据路径（字节怎么走）
                    ─────────────────────────────
   无 GDR  ──被改进为──►  GPUDirect RDMA  ──被改进为──►  Data Direct
   （经主机内存）         （网卡 ↔ GPU 直通）            （为同一条路径提供
                                │                        更好的 PCIe 路由）
                                │ 是其前提
                                ▼
                    控制路径（谁驱动网卡）
                    ─────────────────────────────────
   CPU proxy 线程  ──被加速──►  GDRCopy
          │                    （CPU 快速读写 GPU 上的标志位）
          │ 被替代为
          ▼
   GPUDirect Async / GDAKI
   （GPU kernel 自己驱动网卡）
```

### 示例：把 1 MB 从服务器 A 的 GPU 0 发到服务器 B 的 GPU 0

**阶段 1：无 GDR（基线）**
1. GPU kernel 把 1 MB 数据**从显存拷贝到主机内存缓冲区**。
2. 一个 CPU 线程（NCCL 的 *proxy 线程*）发现数据就绪，调用 `ibv_post_send`。
3. 网卡**从主机内存**读取数据并发送。
4. 服务器 B 反向执行：网卡 → 主机内存 → 拷贝到显存。

问题：每个字节都要两次穿过 PCIe 并经过主机内存，浪费带宽、增加延迟。

**阶段 2：+ GPUDirect RDMA。解决数据路径问题。**
- 网卡**直接从显存读取**，并直接写入远端 GPU 显存。第 1 步和第 4 步消失。
- 为此，GPU 显存必须先注册，让网卡能够寻址。**nvidia-peermem** 和 **DMA-BUF** 是完成这种注册的两种驱动机制。它们不是独立的技术，只是开启 GDR 的两种方式。
- 调用 `ibv_post_send` 的仍然是 CPU proxy 线程。

**阶段 3：+ Data Direct。改进 GDR 路径。**
- 在某些服务器上，GPU 和网卡挂在不同的 PCIe 交换芯片下，GDR 流量只能绕经 CPU 的 root complex，速度很慢。这种情况下 NCCL 甚至可能关闭 GDR。
- Data Direct 为网卡提供一条直达 GPU 的 PCIe 路径，让 GDR 在这类服务器上也能满速运行。
- 它改变的是 GDR 路径**好不好**，而不是**有没有**。没有 GDR 时它不起作用。

**阶段 4：+ GDRCopy。加速由 CPU 驱动的控制路径。**
- 在阶段 1–3 中，CPU proxy 线程和 GPU kernel 需要不断互相通知："第 3 个槽的数据已就绪"、"第 3 个槽已发送，可以复用"。这些信号都是很小的计数器（FIFO 头尾指针、标志位）。
- GDRCopy 把一小块 GPU 显存映射到 CPU 地址空间，CPU 就能用普通的内存访问读写这些标志位，比 `cudaMemcpy` 快得多。
- 它**不搬运大块数据**，只是让 CPU ↔ GPU 之间的"对话"更快。这对小消息、延迟敏感的场景最有意义。

**阶段 5：GPUDirect Async / GDAKI。把 CPU 从控制路径中移除。**
- CPU 只负责一次性建立 QP。之后由 **GPU kernel 自己**把工作请求写入网卡队列，并敲响网卡的 doorbell（门铃，即通知网卡"有新任务"的寄存器）。
- 没有 proxy 线程，也就没有 CPU ↔ GPU 握手，因此这种模式下**不需要 GDRCopy**。
- 它**仍然依赖 GDR**：网卡必须能直接读取显存，因为 GPU 告诉它的是"从这个显存地址发送"。
- NCCL 的设备端 **GIN** API（[src/transport/net_ib/gdaki/](https://github.com/NVIDIA/nccl/tree/v2.32.6-1/src/transport/net_ib/gdaki)、[gin.cc](https://github.com/NVIDIA/nccl/blob/v2.32.6-1/src/transport/net_ib/gin.cc)）使用的就是它。CUDA kernel 可以在计算过程中把 token 发给其他 GPU，这正是 MoE 专家并行的 dispatch/combine 所需要的。

### 汇总表

| | 是否改变数据路径？ | 是否改变控制路径？ | 依赖 |
|---|---|---|---|
| 无 GDR | 基线：经主机内存 | CPU 驱动 | — |
| GPUDirect RDMA | **是**：网卡 ↔ GPU 直通 | 否，仍由 CPU 驱动 | nvidia-peermem 或 DMA-BUF |
| Data Direct | **让 GDR 更快**（针对不理想的 PCIe 布局） | 否 | GDR |
| GDRCopy | 否 | **CPU ↔ GPU 信号更快** | CPU 驱动模式（有无 GDR 均可） |
| GDAKI / GPUDirect Async | 否（使用 GDR 的路径） | **GPU 驱动，无需 CPU** | GDR（配合 Data Direct 效果更好） |

在典型的现代 H100/B200 集群上运行普通 NCCL 集合通信时，GDR 通常是开启的；如果硬件支持，还会用上 Data Direct。使用设备端通信的 MoE 负载会在此之上再加 GDAKI。

> **更正（见第 7 节）：** 原回答曾说"典型集群使用 GDR + GDRCopy"，这不准确。查阅源码后确认 NCCL **默认关闭 GDRCopy**（`NCCL_GDRCOPY_ENABLE` 默认为 0），需要手动开启。

在 `NCCL_DEBUG=INFO` 输出中可以查找：连接日志中的 `GDRDMA`（GDR 已生效）、`GDRCOPY enabled`（GDRCopy 已启用），以及 GIN/GDAKI 的初始化信息（GPU 发起的网络通信）。

---

## 6. GDRCopy 和 GDAKI 哪个更快？

**问：** GDRCopy 和 GPUDirect Async / GDAKI，哪个更快？

**答：**

直接比较 GDRCopy 和 GDAKI 并不公平，因为它们做的不是同一件事。GDRCopy 是 CPU proxy 设计*内部*的加速手段，而 GDAKI 是*去掉* CPU proxy。所以真正的问题是：

> **CPU proxy 线程 + GDRCopy** 对比 **GDAKI（GPU 直接驱动网卡）**：哪个更快？

**简短回答：** 小消息时 GDAKI 延迟更低。大消息时两者带宽基本相同，因为字节都走同一条 GPUDirect RDMA 路径，瓶颈在网络链路本身。

### GDAKI 延迟更低的原因：步骤更少

**CPU proxy + GDRCopy**，发送一条小消息：
```
GPU kernel 写入"就绪"标志
  → CPU proxy 发现它（通过 GDRCopy 映射轮询标志位，一次 PCIe 读）
  → CPU 构造工作请求，敲网卡 doorbell（一次 PCIe 写）
  → 网卡从显存读取数据（GDR）→ 网络
  → 远端网卡写入远端显存
  → 远端 CPU proxy 轮询其完成队列
  → 远端 CPU 把"已到达"标志写入显存（GDRCopy）
  → 远端 GPU kernel 看到标志
```

**GDAKI**，同一条消息：
```
GPU kernel 自己构造工作请求 + 敲网卡 doorbell
  → 网卡从显存读取数据 → 网络
  → 远端网卡把数据和信号直接写入远端显存
  → 远端 GPU kernel 看到信号
```

GDAKI 省掉了：
- **两次 CPU 中转**，两端各一次。每次都包括一个轮询循环和一次 PCIe 往返；如果 proxy 线程繁忙或被调度出去，还会带来抖动。
- **kernel 边界**。使用 CPU proxy 时，通信通常发生在 kernel 之间或与 kernel 并行。使用 GDAKI 时，kernel 可以在计算中途发送数据并继续计算，实现细粒度的重叠。

这就是 MoE 专家并行库在低延迟 dispatch/combine 模式中使用 GPU 发起网络通信（IBGDA/GDAKI）的原因：这些负载会发送大量小的、对延迟敏感的消息。

### GDAKI 并不总是更好

| 场景 | 通常谁更好 | 原因 |
|---|---|---|
| 小消息、延迟受限（MoE token dispatch、推理 decode） | **GDAKI** | 步骤更少，CPU 不在环路中 |
| 通信融合在计算 kernel 内部 | **GDAKI** | CPU proxy 根本做不到 |
| 大消息（梯度 all-reduce，数百 MB） | **基本相同** | 都受限于 GDR 下的网络带宽 |
| 每个 GPU 线程发出大量极小的操作 | **视情况而定** | 在 GPU 上构造工作请求意味着通过 PCIe 进行慢速的非缓存写入，还会占用本可用于计算的 GPU 线程/SM。一个专用 CPU 核心做这件事相当高效。 |
| 普通 NCCL 集合通信（`ncclAllReduce` 等） | **CPU proxy + GDRCopy** 是标准的、经过充分调优的路径 | GDAKI 主要在使用设备端 GIN API 时才有意义 |

**经验法则：** 看延迟 → GDAKI；看带宽 → 没区别；看易用性和默认行为 → CPU proxy + GDRCopy。

这里没有给出具体数字，因为结果会随 GPU、网卡、PCIe 布局和消息大小大幅变化。如果有多节点环境，最可靠的办法是在自己的硬件上分别用两种方式跑小消息延迟测试。

---

## 7. NCCL 通信一般都是 GDRCopy + CPU proxy thread 吗？

**问：** NCCL 通信一般都是 GDRCopy + CPU proxy thread 的是吗？

**答：**

不完全对。CPU proxy thread 那一半大体是对的，GDRCopy 那一半不对。而且要先分清**节点内**和**跨节点**两种情况。

### 7.1 跨节点（走网卡 IB/RoCE）

**通常是 CPU proxy thread 驱动网卡，但默认不开 GDRCopy。**

源码证据：

```c
// src/init.cc:153
NCCL_PARAM(GdrCopyEnable, "GDRCOPY_ENABLE", 0);   // 默认 0 = 关闭
```

所以默认路径是：
- **数据**：走 GPUDirect RDMA（拓扑合适时），网卡直接读写 GPU 显存。
- **控制**：CPU proxy thread 调 `ibv_post_send`，轮询 CQ。
- **GPU ↔ CPU 之间的信号**（FIFO 头尾指针、ready 标志等）：默认放在 **pinned host memory（锁页主机内存）** 里。GPU kernel 通过 PCIe 写主机内存，CPU 直接读本地内存，不需要 GDRCopy。

GDRCopy 是可选优化：设置 `NCCL_GDRCOPY_ENABLE=1`，并且装好 gdrcopy 驱动后才启用。

⚠️ 更正：前面第 5 节曾说"典型 H100/B200 集群用 GDR + GDRCopy"，这不准确。正确的是：**GDR 通常开启，GDRCopy 默认关闭。**

### 7.2 节点内（NVLink / PCIe P2P / NVLS）

**数据面基本不用 CPU proxy thread。**

| 传输方式 | 怎么搬数据 | 需要 CPU proxy 吗？ |
|---|---|---|
| P2P over NVLink（`p2p.cc`） | GPU kernel 直接 load/store 对端 GPU 的显存 | 不需要 |
| NVLS（`nvls.cc`） | GPU 通过 NVSwitch multicast，在交换机里做归约 | 不需要 |
| SHM（`shm.cc`，没有 P2P 时） | 经过主机共享内存中转 | 一般不需要；只有少数模式（如用 cudaMemcpy 搬数据时）才用 |

节点内是 GPU kernel 自己把活干完，CPU 只负责初始化和启动 kernel。

### 7.3 设备端通信（GIN / GDAKI）

如果用的是 device API（在 kernel 里发起网络通信，例如 MoE 的 EP 通信），跨节点也不需要 CPU proxy：GPU 直接驱动网卡。

### 总结

| 场景 | 数据路径 | 谁驱动 | GDRCopy |
|---|---|---|---|
| 节点内 NVLink | GPU 直接读写对端显存 | GPU kernel | 不涉及 |
| 跨节点，普通集合通信（默认） | GPUDirect RDMA | **CPU proxy thread** | **默认关闭**，信号走 pinned host memory |
| 跨节点 + `NCCL_GDRCOPY_ENABLE=1` | GPUDirect RDMA | CPU proxy thread | 开启，信号放显存，CPU 通过 GDRCopy 访问 |
| 跨节点 device API（GIN/GDAKI） | GPUDirect RDMA | GPU kernel | 不需要 |

所以更准确的说法是：**NCCL 的普通跨节点通信一般是 CPU proxy thread + GPUDirect RDMA，GDRCopy 是可选项；节点内通信则由 GPU kernel 直接完成，不依赖 CPU proxy。**
