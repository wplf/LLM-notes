# 第 4 篇 内存管理

> 目标：把"虚拟内存 → 物理内存 → 分配器 → 回收"这条链完整走一遍，并理解 Linux 内存管理的几个独有设计（folio、反向映射、按需分页、回收优先于 swap）。

## 1. 三层地址空间

```
用户程序看到的虚拟地址
      │  MMU + 页表（多级，x86-64 四级/五级）
      ▼
物理内存（由 NUMA 节点、zone（DMA/DMA32/NORMAL/HIGHMEM）、page 帧组成）
      │
      ▼
磁盘（swap、文件系统后备存储）
```

| 层 | 单位 | 关键结构 |
|---|---|---|
| 虚拟地址空间 | `vm_area_struct`（VMA） | 一段连续虚拟范围及其属性 |
| 页表 | PTE / PMD / PUD / P4D / PGD | 每进程一棵树（`mm_struct`） |
| 物理页 | `struct page`（元数据）| 每 4KB（或 THP 2MB）一个 |
| 分配器 | 页（buddy）与对象（slab） | `free_area[]`、`kmem_cache` |

### 页表

- x86-64 默认 4 级页表：48 位虚拟地址 = 9+9+9+9+12。5 级（`CONFIG_X86_5LEVEL`）扩展到 57 位（128PB）。
- 大页：`PMD` 层 2MB（THP）、`PUD` 层 1GB（`hugetlbfs`）。
- **TLB** 是页表的缓存；换页表（进程切换）会污染 TLB。**PCID**（`INVPCID`）让切换时不必全刷；`ASID` 在 arm64 上类似。
- **反向映射（rmap）**：从物理页反查"哪些页表项映射了它"，是页面回收和迁移的前提。实现为 `struct address_space` 的 `i_mmap` 区间树（VMA 的 `anon_vma` 链 + 文件映射的红黑树）。

## 2. 进程地址空间布局：VMA

`cat /proc/self/maps` 看到的就是 VMA 列表（`mm_struct->mm_mt`，6.1 起用 maple tree 替代红黑树，查询/插入更快且更适合 RCU）。

| 区域 | 内容 | 典型标志 |
|---|---|---|
| 代码段 / 只读数据 | ELF `PT_LOAD` | `r-xp` / `r--p` |
| 数据段 `.data` `.bss` | 已初始化/未初始化全局变量 | `rw-p` |
| 堆 | `brk` 扩展区 | `rw-p` |
| 映射区 | `mmap` 匿名或文件映射、共享库 | `rw-s`（共享）/ `rw-p`（私有） |
| 栈 | 向下增长，`RLIMIT_STACK` 限制 | `rw-p`，可扩展 |
| `[vvar] [vdso] [vsyscall]` | 内核映射的特殊页 | `r-xp` |

`vm_area_struct` 关键字段：`vm_start/vm_end`、`vm_flags`（`VM_READ/WRITE/EXEC/SHARED/MAYWRITE/GROWSDOWN`）、`vm_ops`（`fault`/`open`/`close`/`split`/`mremap` 等操作表）、`vm_file`、`vm_pgoff`、`anon_vma`。VMA 是"惰性"的：`mmap` 只登记范围，物理页在首次访问时才分配。

### 缺页异常（page fault）

`handle_mm_fault()`：

1. 找到/创建对应的 VMA（找 VMA 期间用 RCU + 读锁）。
2. 没有 PTE 页表页 → `p4d_alloc` / `pud_alloc` / `pmd_alloc` / `pte_alloc` 逐级分配。
3. 按情况处理：
   - **匿名页首次访问**（`do_anonymous_page`）：分配一个零页或新页；读访问可先映射**全局共享的零页**（`ZERO_PAGE`），写时再 COW。
   - **文件页缺页**（`do_fault` → `do_read_fault`/`do_cow_fault`）：查 page cache，未命中就 `readpage` → 提交块 I/O（第 8 篇）→ 唤醒进程。
   - **写时复制**（`do_wp_page`）：PTE 是只读但 VMA 可写，复制一页并改本进程 PTE。
   - **swap 入页**（`do_swap_page`）：`swap_readpage` 把页读回来并重建映射。
   - **THP**：若 VMA 允许大页（THP 为 `always`，或 `madvise` 模式下带 `MADV_HUGEPAGE`）且对齐，`do_huge_pmd_anonymous_page` 直接从伙伴系统分配 2MB 页；分配不到就退回 4KB 小页，之后由 `khugepaged` 在后台合并。
4. 更新 PTE、`mm->rss_stat`、`tsk->min_flt`/`maj_flt`（`majflt` = 需要磁盘 I/O 的缺页）。

指标：`/proc/vmstat` 的 `pgfault`、`pgmajfault`；`getrusage`/`/proc/<pid>/stat` 的 `minflt`/`majflt`。

## 3. 物理页管理与分配器

### 3.1 三层分配器

| 层 | 接口 | 粒度 | 实现 |
|---|---|---|---|
| 页帧分配器 | `alloc_pages()` / `__free_pages()` | `2^order` 页（4KB ~ 4MB） | 伙伴系统，每 zone 一组 `free_area[MAX_ORDER]` 链表 + 位图 |
| Slab 分配器 | `kmem_cache_alloc()` / `kmalloc()` | 任意小对象 | **SLUB**（默认），每个 CPU 一个当前 slab，几乎无锁 |
| 大块虚拟内存 | `vmalloc()` / `vmap()` | 页级，虚拟连续物理不连续 | |

**伙伴系统**：按 order 分链表；申请 order-n 没有空闲块时，从 order-n+1 拆一半，释放时若"伙伴"也空闲则向上合并。每 zone 有水位（`WMARK_MIN/LOW/HIGH`），低于低水位时唤醒 `kswapd`（异步回收），低于最低水位时**直接回收**（同步，会让分配者自己卡住）。

**SLUB 的关键设计**：
- 每个 CPU 的 `kmem_cache_cpu` 指向当前 slab 的 `freelist`，分配 = 指针弹出，无锁。
- 换 slab 时才拿 `node` 锁。
- 空闲对象数低于 `cpu_partial` 阈值时才批量还给 node 的 partial 链表，避免频繁跨 CPU 争用。
- `SLAB_TYPESAFE_BY_RCU`：slab 页要等一个 RCU 宽限期后才还给页分配器，因此 RCU 读者拿到的指针始终指向**同类型**对象（但对象可能已被释放并复用，读者需要重新校验身份），如 `sighand_struct`、部分 socket。
- 调试选项：`CONFIG_SLUB_DEBUG`（`slub_debug=FZPU`：Sanity、Red zoning、Poisoning、User tracking），`/sys/kernel/slab/<name>/` 可实时查看。

**`kmalloc` 的尺寸类基本是 2 的幂**（8/16/32/64/96/128/192/256/…/8K，另有 96、192 两个非 2 的幂档位），超过上限（通常为 2 页）就直接走 `alloc_pages`，仍然是物理连续的。不要求物理连续的大对象用 `kvmalloc`（先试 `kmalloc`，失败退到 `vmalloc`）。

### 3.2 zone 与 NUMA

- **zone**：`ZONE_DMA`（老设备 <16MB）、`ZONE_DMA32`（<4GB）、`ZONE_NORMAL`、`ZONE_MOVABLE`（可迁移页，供热插拔和巨大页）、`ZONE_HIGHMEM`（32 位遗留）。
- **NUMA**：每个节点一个 `pg_data_t`，含本地 zone 与 `zonelist`（按距离排序的 fallback 顺序）。`numactl`、`mbind`、`set_mempolicy` 控制策略；`/proc/zoneinfo`、`/sys/devices/system/node/node*/meminfo` 可观测。
- **迁移类型**（migratetype）：`UNMOVABLE`、`RECLAIMABLE`、`MOVABLE`，伙伴系统按类型分桶以**减少碎片**（否则一个不可移动页会毁掉整个大页块）。

### 3.3 `page` / `folio` / memcg

- `struct page` 每个物理页一个（4KB 页的话，1TB 内存就是 256M 个 `struct page`，元数据开销可观）。字段用 union 复用：匿名页、文件页、slab 页、复合页各用不同子集，靠 `page->flags` 区分。
- **`folio`**（5.16 起逐步引入，6.x 深入）：表示"一个复合页或多个页组成的单位"，用于修掉 `struct page` 语义混乱（一个指针到底指一页还是连续多页）。新代码优先用 `folio`，`page` 更多作为内部实现。
- **memcg 记账**：页分配时把页挂到 `page->memcg_data`（`obj_cgroup`），`memcg->memory` 计入；超限触发**进程级回收**（`try_charge` → `mem_cgroup_oom`）。

### 3.4 特殊分配器

| 分配器 | 适用区域 | 特点 |
|---|---|---|
| `kmalloc`（SLUB） | 低端直接映射区 | 小对象，快速，物理连续 |
| `vmalloc` | `VMALLOC_START~VMALLOC_END` | 虚拟连续物理离散，每次分配要建页表，慢，不能用于 DMA |
| `kmem_cache` | 专用对象（`task_struct`、`sk_buff`…） | 可预构造、SLAB_ACCOUNT、对齐控制 |
| per-CPU 分配器 | 每个 CPU 独立 | `alloc_percpu`/`this_cpu_ptr`，无锁 |
| `gen_pool` / `dma_alloc_coherent` | 设备专用内存 | 物理连续，DMA 可直接访问 |
| `mempool` | 紧急保留池 | 内存紧张时仍能成功（I/O 路径必需） |

## 4. 缓存、写回与回收

### 4.1 Page cache

文件内容缓存在内存里，以 4KB 页（或 large folio）为单位，由 `address_space`（`inode->i_mapping`）的 **xarray** 索引（`mapping->i_pages`，key = 页索引）。读走 `filemap_read`/`filemap_get_pages`，写走 `filemap_write_and_wait_range`；脏页由 `writepages` 批量回写。

### 4.2 回写（writeback）

- 脏页在一段时间后（`dirty_expire_centisecs`，默认 30s）或被写满阈值（`dirty_ratio`/`dirty_background_ratio`，默认 20%/10%）时回写。
- 每个后备设备（bdi）对应 `bdi_writeback`，回写工作在 `kworker` 上执行（`wb_workfn`）；老内核里对应的是独立的 `flush-MAJOR:MINOR` 线程。写得太快的进程会在 `balance_dirty_pages()` 里被主动限速（throttle）。
- 阈值调参是延迟问题的常见源头：`vm.dirty_ratio` 太高 → 一次性大量回写导致长时间卡顿（"write stall"）。

### 4.3 页回收（`vmscan`）

1. 每 zone 维护 **LRU 链表**：`anon` 与 `file` 各一组 `active`/`inactive`（共 4 条，per-memcg 也各有一套）。
2. 回收扫描 inactive 尾部：
   - **文件页干净** → 直接丢弃（便宜）。
   - **文件页脏** → 先写回，再丢（贵）。
   - **匿名页且有 swap** → 写进 swap（`try_to_unmap`），再释放。
   - **匿名页无 swap** → 只能靠 OOM killer（除非 `zswap`/`zram` 把它压缩在内存里）。
3. **第二次机会**：扫描时检查 `PG_referenced`，若近期被访问则移到 active 链表。
4. **水位**：`kswapd`（每 NUMA 节点一个）在低水位启动，回到高水位睡眠；`direct reclaim` 在最低水位发生，由分配者同步执行（这也是"机器看起来很卡"的常见原因）。
5. **compaction**（内存规整）与回收是两件事：总空闲量够、但拼不出高 order 连续块时，把可迁移页挪到一起，腾出连续空间。高 order 分配失败时会交替尝试规整和回收，后台有 `kcompactd`。
6. **MGLRU**（6.1 起可选，很多发行版默认开启）：用多代（generation）替代 active/inactive 两条链表，并通过批量扫描页表的 accessed 位判断冷热，在内存压力下的 CPU 开销和误回收都更少（`/sys/kernel/mm/lru_gen/enabled`）。

> **Linux 与其他 Unix 的重要差别**：这里没有"缓冲区缓存"和"页缓存"之分，也没有独立的匿名内存换出器；一切都统一成"page cache + 匿名页 + swap"，回收策略统一在 LRU 上。

## 5. 系统级内存管理：OOM、swap、THP

### OOM killer

当回收失败且无法分配时，`out_of_memory()` 按 `oom_score`（`oom_score_adj` 可调，-1000 ~ 1000）选一个"最该杀"的进程。容器里通常是 cgroup 级别的 OOM（`memory.max`），会杀掉组内某个进程或触发 `memory.oom.group`。

```bash
cat /proc/<pid>/oom_score        # 分数越高越容易被杀
echo -1000 > /proc/<pid>/oom_score_adj   # 让关键进程免死
```

### swap 与 zram / zswap

- swap 文件/分区：`swapon`，页由 `swap_info_struct` 管理 slot。**SSD 上的 swap 完全可用**，主要代价是延迟。
- **zram**：把一块内存做成压缩块设备当 swap（移动设备、无 swap 分区场景）。
- **zswap**：在 swap 前面加一层压缩缓存（内存中的"swap cache"），减少真实磁盘 I/O。
- **swap 不一定等于性能灾难**：把长期不用的匿名页移出内存，可以让 page cache 占更多空间。

### 大页与 KSM

- **THP（透明大页）**：`madvise` / `always` / `never`（`/sys/kernel/mm/transparent_hugepage/enabled`），由 `khugepaged` 后台合并 + 缺页时直接分配 2MB。好处是减少 TLB miss 和缺页次数；坏处是内存放大（一个字节的分配占 2MB）和 `khugepaged` 的 CPU/延迟抖动。数据库类负载常推荐 `madvise`。
- **hugetlbfs**：预保留的显式大页，无 THP 的抖动问题，`vm.nr_hugepages` 配置。
- **KSM（Kernel Samepage Merging）**：扫描内容相同的匿名页并合并为一个 COW 页，对虚拟机/容器密度敏感场景有用（`/sys/kernel/mm/ksm/`），但扫描本身耗 CPU。

## 6. 内存相关的系统调用与接口

| 接口 | 作用 |
|---|---|
| `brk` / `mmap` / `mremap` / `munmap` | 建立、扩展、移动、拆除 VMA |
| `madvise` | 对 VMA 给建议：`MADV_DONTNEED`、`MADV_PAGEOUT`、`MADV_HUGEPAGE`、`MADV_FREE`、`MADV_COLLAPSE` |
| `mlock` / `mlockall` | 锁定页，禁止换出（实时系统必需） |
| `mlock2(MLOCK_ONFAULT)` | 第一次访问时锁 |
| `mbind` / `set_mempolicy` / `move_pages` | NUMA 策略与迁移 |
| `process_madvise` | 批量对别的进程应用 madvise（跨进程内存管理，如 Android/容器） |
| `io_uring` 的 `REGISTER_BUFFERS` | 注册长期使用的缓冲区（免重复映射/固定） |

## 7. 可观测性

```bash
cat /proc/meminfo               # MemTotal/MemFree/MemAvailable/Cached/Dirty/Slab/SReclaimable...
cat /proc/zoneinfo | head -40   # 每 zone 的水位、free_area 各 order 的空闲块数
cat /proc/buddyinfo             # 碎片情况（每个 order 有多少块，大页能不能分出来）
slabtop -s c                    # slab 占用排序
cat /proc/vmstat                # pgfault/pgmajfault/pgsteal_direct/compact_* 等
numastat -p <pid>               # 进程的 NUMA 分布
```

进阶追踪：`perf trace -e page-faults`、`bcc` 的 `cachestat`/`cachetop`/`oomkill`、`bpftrace` 挂 `handle_mm_fault` 统计各条分支的占比。

## 8. 关键文件

| 路径 | 内容 |
|---|---|
| `mm/mmap.c`、`mm/memory.c` | VMA 管理、`handle_mm_fault` 全流程 |
| `mm/page_alloc.c` | 伙伴系统、per-CPU 页列表、`__alloc_pages` |
| `mm/slub.c` | SLUB 分配器 |
| `mm/filemap.c` | page cache 读路径 |
| `mm/vmscan.c` | LRU、`shrink_folio_list`、kswapd |
| `mm/page-writeback.c` | 脏页阈值与回写节流 |
| `mm/rmap.c` | 反向映射 |
| `mm/khugepaged.c`、`mm/huge_memory.c` | THP |
| `mm/memcontrol.c` | memcg 记账与 cgroup 回收/OOM |

## 小结

内存管理的结构可以概括成：**VMA 描述"应该有什么"，页表记录"实际有什么"，缺页异常把前者变成后者，伙伴系统与 SLUB 保证页面来源，LRU 回收在"可用内存"不足时腾出空间**。三个最影响实际体验的旋钮是：脏页阈值（写延迟）、THP 策略（内存放大 vs TLB/缺页开销）、swap/zswap 配置（匿名页能否让位给 page cache）。
