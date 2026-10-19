# 第 8 篇 块设备层与 I/O

> 目标：理解文件系统发出的读写请求如何变成 `bio`、经过 blk-mq 多队列到达 NVMe/SATA 设备，以及 I/O 调度器、设备映射（dm/md）与 io_uring 在其中的位置。

## 1. 层次结构

```
文件系统 / page cache / O_DIRECT / 直接打开 /dev/nvme0n1
         │  submit_bio(bio)
         ▼
┌───────────────── 块层 block/ ─────────────────┐
│ bio：一次 I/O 的描述（扇区 + 若干内存段）       │
│   ↓ 可能被 dm / md（RAID、LVM、加密）重映射/拆分 │
│ blk-mq：                                        │
│   软件队列（每 CPU） → I/O 调度器（可选）         │
│   → 硬件分派队列（与设备硬件队列一一对应）        │
│ request：合并后的 I/O，带 tag                   │
└──────────────────────────────────────────────┘
         │  queue_rq()
         ▼
设备驱动：nvme / scsi(sd) + ata / virtio-blk / null_blk / loop
         │  DMA + 门铃寄存器
         ▼
硬件；完成后中断（或轮询）→ blk_mq_complete_request → bio_endio → 唤醒等待者
```

## 2. 核心数据结构

### `struct bio`

一次块 I/O 的最小描述：

| 字段 | 说明 |
|---|---|
| `bi_iter.bi_sector` | 起始扇区（单位总是 512 字节，与设备真实扇区大小无关） |
| `bi_iter.bi_size` | 剩余字节数 |
| `bi_io_vec[]` | `bio_vec` 数组：(page, offset, len)，物理上不必连续 |
| `bi_opf` | 操作与标志：`REQ_OP_READ/WRITE/FLUSH/DISCARD/WRITE_ZEROES/ZONE_*`，以及 `REQ_SYNC`、`REQ_FUA`、`REQ_PREFLUSH`、`REQ_META`、`REQ_NOWAIT` |
| `bi_bdev` | 目标块设备 |
| `bi_end_io` | 完成回调 |

bio 可以被拆分（`bio_split`，适应设备最大请求长度、条带边界）或链接（`bio_chain`）。

### `struct request` 与 tag

blk-mq 把一个或多个**物理相邻**的 bio 合并成一个 `request`；每个 request 绑定一个 **tag**（硬件队列中的槽位编号），驱动用 tag 直接对应 NVMe 的 command ID，完成时 O(1) 找回请求。tag 数（队列深度）由 `nr_requests` 控制。

### `gendisk` 与 `block_device`

- `gendisk`：一个磁盘（含分区表），`/sys/block/<dev>/`。
- `block_device`：磁盘或某个分区的统一句柄（`/dev/sda1`），文件系统挂载时引用它。
- 请求队列参数：`/sys/block/<dev>/queue/`（`logical_block_size`、`max_sectors_kb`、`rotational`、`scheduler`、`nr_requests`、`nomerges`、`rq_affinity`、`write_cache`）。

## 3. blk-mq：多队列架构

**为什么要多队列**：老的单队列块层（`request_fn`）有一把全局队列锁，在 NVMe（每秒百万级 IOPS、多硬件队列）面前成为瓶颈。3.13 引入 blk-mq，5.0 删除了旧单队列路径。

```
CPU0 CPU1 CPU2 CPU3            每 CPU 软件上下文（blk_mq_ctx）：提交时无跨核争用
  │    │    │    │
  └─┬──┘    └─┬──┘             映射（按 CPU/NUMA 拓扑）
    ▼         ▼
  hctx0     hctx1               硬件分派上下文（blk_mq_hw_ctx），每个对应设备一个提交队列
    │         │
  NVMe SQ0  NVMe SQ1  ──→ 完成队列 CQ0/CQ1 → 各自 MSI-X 中断 → 对应 CPU
```

- 提交在本 CPU 完成，**完成中断也落在提交它的 CPU 附近**（`rq_affinity`），缓存友好。
- **plug**（`blk_start_plug`/`blk_finish_plug`）：进程在短时间内提交的多个 bio 先缓存在任务私有列表，批量合并后一起下发，减少锁和门铃次数。
- **合并**：前向/后向合并相邻扇区的 bio，减少请求数（`nomerges` 可关闭）。
- **轮询（polling）**：`io_uring` 的 `IORING_SETUP_IOPOLL` 或 `RWF_HIPRI` 不等中断，直接轮询完成队列，在超低延迟 NVMe 上能省掉中断开销（以 CPU 占用为代价）。

## 4. I/O 调度器

blk-mq 下的调度器是可选的，`/sys/block/<dev>/queue/scheduler` 切换：

| 调度器 | 思路 | 适用 |
|---|---|---|
| `none` | 不调度，直接下发 | NVMe 等高速、内部自带并行调度的设备（通常默认） |
| `mq-deadline` | 读写分别按扇区排序 + 截止时间，防止饿死；读优先 | SATA SSD/HDD、通用服务器 |
| `bfq` | 按进程分配"预算"，公平分享带宽，交互延迟好 | 桌面、慢速设备、需要按 cgroup 公平 |
| `kyber` | 按读/写/其它分类控制队列深度，以达到目标延迟 | 高速设备上的延迟控制 |

机械硬盘时代调度器的核心任务是**减少寻道**；SSD/NVMe 时代主要任务变成**公平与延迟控制**。

## 5. 设备映射与软件 RAID

| 组件 | 位置 | 功能 |
|---|---|---|
| **device-mapper（dm）** | `drivers/md/dm*.c` | 通用"bio 重映射"框架：一个虚拟块设备 → 映射表 → 一个或多个底层设备 |
| dm-linear / dm-stripe | | LVM 的基础（逻辑卷 = 线性或条带映射） |
| dm-crypt | | 块级加密（LUKS） |
| dm-thin | | 精简配置与快照 |
| dm-verity | | 只读块的哈希树校验（Android、ChromeOS 启动校验） |
| dm-cache / dm-writecache | | SSD 缓存 HDD |
| **md** | `drivers/md/raid*.c` | 软件 RAID 0/1/4/5/6/10（`mdadm`） |
| **loop** | `drivers/block/loop.c` | 把一个文件当成块设备 |
| **zram** | `drivers/block/zram/` | 压缩内存块设备 |
| **nbd / rbd / NVMe-oF** | | 网络块设备 |

dm 设备都是"栈式"的：上层看到的是普通 `gendisk`，内部把 bio 改写目标后再次 `submit_bio` 给下层。`dmsetup table` 查看映射。

## 6. 设备驱动侧：NVMe 与 SCSI

### NVMe

- 内存里的**提交队列（SQ）/完成队列（CQ）环**，驱动写 64 字节命令到 SQ，敲门铃寄存器；设备 DMA 读命令、执行、写完成项到 CQ，再发 MSI-X 中断。
- 每个 CPU 可以有自己的队列对，无锁提交。
- PRP/SGL 描述数据缓冲区的物理页（DMA 映射见第 10 篇）。
- `nvme-cli`：`nvme list`、`nvme smart-log`、`nvme id-ctrl`。

### SCSI 栈

`sd`（磁盘）/`sr`（光驱）上层驱动 → SCSI 中间层 → 低层驱动（`ahci` 走 libata 把 SCSI 命令翻译为 ATA；`mpt3sas`、`megaraid_sas`、USB 存储、iSCSI 等）。SATA 盘虽然不是 SCSI，但 Linux 让它走 SCSI 栈，因此显示为 `/dev/sdX`。

## 7. 特殊语义

| 操作 | 说明 |
|---|---|
| **FLUSH** | 把设备易失性写缓存刷到介质（`fsync` 最终会触发） |
| **FUA**（Force Unit Access） | 该写本身直接写到持久介质，不留在缓存中 |
| **DISCARD / TRIM** | 告诉 SSD 哪些块不再使用（`fstrim`，或挂载选项 `discard`） |
| **WRITE_ZEROES** | 设备侧清零，不传数据 |
| **Zoned 设备**（SMR HDD、ZNS SSD） | 区域内只能顺序写，`REQ_OP_ZONE_APPEND`；btrfs、f2fs 支持；`blkzone` 工具 |
| **原子写**（6.11 起） | `RWF_ATOMIC`：在设备支持的大小范围内保证写不撕裂，数据库可借此免去双写 |

## 8. 用户态 I/O 接口的演进

| 接口 | 特点 | 问题 |
|---|---|---|
| `read`/`write`/`pread`/`pwrite` | 同步，一次一个 | 高并发需要大量线程 |
| `readv`/`writev`/`preadv2` | 分散/聚集，`preadv2` 支持 `RWF_NOWAIT`/`RWF_HIPRI` | 仍同步 |
| Linux AIO（`io_submit`） | 异步，但**只对 `O_DIRECT` 真正异步**，缓冲 I/O 会阻塞 | 接口笨重、能力有限 |
| `epoll` | 就绪通知，对普通文件无效（文件总是"就绪"） | 不适用磁盘 I/O |
| **io_uring**（5.1 起） | 共享内存环形队列：提交队列 SQ + 完成队列 CQ，批量提交、批量收割 | 安全面大，部分环境（如容器、Android）默认禁用 |

### io_uring 的设计

```
用户态                              内核
 SQ ring：填写 SQE（opcode、fd、buf、off、user_data）
   │  io_uring_enter(to_submit, min_complete)  ← 一次系统调用提交多条
   │  或 SQPOLL：内核线程主动轮询 SQ，提交完全不用 syscall
   ▼
内核执行：能非阻塞完成的直接完成；需要等待的走异步路径（poll 驱动 / io-wq 工作线程）
   ▼
 CQ ring：写 CQE（user_data、res）  ← 用户态直接读共享内存收割
```

- 支持几乎所有 I/O 类操作：文件读写、`send`/`recv`、`accept`、`connect`、`openat`、`statx`、`splice`、超时、链式依赖（`IOSQE_IO_LINK`）。
- **注册资源**：`IORING_REGISTER_FILES`（fd 预先登记，免每次 `fget`）、`IORING_REGISTER_BUFFERS`（缓冲区预先 pin 住，免每次映射）。
- 与 `IOPOLL` 结合，单核可达到百万级 IOPS（估计值，取决于设备）。
- liburing 是推荐的用户态库。

## 9. I/O 控制与可观测性

### cgroup v2 io 控制器

| 文件 | 作用 |
|---|---|
| `io.max` | 硬限速：`rbps`/`wbps`/`riops`/`wiops` |
| `io.weight` | 按比例分配（需 BFQ 或 `io.cost`） |
| `io.latency` | 为某组保证目标延迟，超出时节流其它组 |
| `io.cost.qos` / `io.cost.model` | 基于设备成本模型的比例控制（iocost，Meta 开发） |
| `io.pressure` | PSI：I/O 压力指标 |

**缓冲写的归属问题**：写入 page cache 的数据由回写线程异步下发，cgroup v2 通过 `inode` 与 `bdi_writeback` 的关联把回写 I/O 记到产生脏页的 cgroup 名下（cgroup v1 做不到）。

### 观测工具

```bash
iostat -x 1                      # 每设备 r/s、w/s、await、aqu-sz、%util（注意：%util 对并行设备意义有限）
cat /proc/diskstats              # 原始计数
cat /sys/block/nvme0n1/stat
blktrace -d /dev/nvme0n1 -o - | blkparse -i -   # 每个请求的生命周期（Q 入队、G 获得 request、D 下发、C 完成）
biolatency / biosnoop / biotop   # bcc：延迟直方图、逐请求、按进程排序
fio --name=t --filename=/dev/nvme0n1 --rw=randread --bs=4k --iodepth=64 --ioengine=io_uring --direct=1
```

## 10. 关键文件

| 路径 | 内容 |
|---|---|
| `include/linux/blk_types.h` | `bio`、`bio_vec`、`REQ_*` 标志 |
| `include/linux/blk-mq.h`、`block/blk-mq.c` | blk-mq 核心 |
| `block/blk-core.c` | `submit_bio` 入口、plug |
| `block/blk-merge.c` | 合并与拆分 |
| `block/mq-deadline.c`、`bfq-*.c`、`kyber-iosched.c` | I/O 调度器 |
| `block/blk-cgroup.c`、`blk-iocost.c`、`blk-throttle.c` | cgroup I/O 控制 |
| `drivers/nvme/host/` | NVMe 驱动（`pci.c`、`core.c`） |
| `drivers/md/` | device-mapper 与软件 RAID |
| `io_uring/` | io_uring 实现（6.0 起独立成顶层目录） |

## 小结

块层的演进主线是**去掉全局锁、贴合硬件并行**：从单队列 + 电梯调度，到 blk-mq 的"每 CPU 软件队列 + 每硬件队列分派 + tag"，再到 io_uring 用共享内存环减少系统调用和上下文切换。`bio` 是贯穿全层的通用单位，dm/md 通过"改写 bio 再提交"实现栈式组合；持久性语义（FLUSH/FUA）与 cgroup I/O 控制则是生产环境最需要关注的两个方面。
