# 第 7 篇 VFS 与文件系统

> 目标：理解 VFS 的四大对象、路径查找、一次 `read()`/`write()` 怎么经过 page cache，以及 ext4 这类磁盘文件系统和 procfs 这类伪文件系统是如何挂到 VFS 上的。

## 1. VFS 的定位

VFS（Virtual File System）是一层**通用文件模型**：系统调用只和 VFS 打交道，VFS 再通过操作表调用具体文件系统。

```
open/read/write/stat/mmap/...
          │
          ▼
        VFS：路径解析、权限检查、fd 管理、page cache、锁
          │  inode->i_op / file->f_op / sb->s_op / mapping->a_ops
  ┌───────┼─────────┬───────────┬──────────┬────────┐
 ext4    xfs      btrfs       tmpfs      procfs    nfs / fuse
  │       │         │        (纯内存)   (内核数据)   (网络/用户态)
  ▼       ▼         ▼
       块设备层（第 8 篇）
```

## 2. 四大对象

| 对象 | 生命周期 | 表示 | 操作表 |
|---|---|---|---|
| `super_block` | 每次挂载 | 一个已挂载的文件系统实例 | `super_operations`（`alloc_inode`、`write_inode`、`sync_fs`、`statfs`） |
| `inode` | 文件存在期间（缓存） | 一个文件本身：元数据（大小、权限、时间、块映射） | `inode_operations`（`lookup`、`create`、`mkdir`、`rename`、`permission`、`setattr`） |
| `dentry` | 缓存 | 路径中的一个**名字**到 inode 的绑定 | `dentry_operations`（`d_revalidate`、`d_hash`、`d_compare`） |
| `file` | `open` 到最后一个 `close` | 一次**打开**：偏移量、打开标志、引用 | `file_operations`（`read_iter`、`write_iter`、`mmap`、`fsync`、`ioctl`、`poll`） |

关系：

```
进程 task_struct
 └─ files_struct
     └─ fdtable: fd[0], fd[1], ... ──→ struct file（f_pos、f_flags、f_op）
                                        └─ f_path: { vfsmount, dentry }
                                                              └─ d_inode ──→ struct inode
                                                                               ├─ i_sb ──→ super_block
                                                                               └─ i_mapping ──→ address_space（page cache）
```

几个容易混淆的点：

- **一个 inode 可以有多个 dentry**（硬链接）；**一个 inode 可以有多个 file**（多次打开）；**一个 file 可以被多个 fd 引用**（`dup`、`fork` 后共享偏移量）。
- `inode` 号在单个文件系统内唯一，`(st_dev, st_ino)` 才全局唯一。
- 文件名不在 inode 里，而在**目录项**里（磁盘上是目录文件的内容，内存里是 dentry）。
- 删除文件（`unlink`）只是删除名字；inode 的 `i_nlink` 为 0 且没有打开的 file 时，才真正释放数据。这就是"删除了正在写的日志文件，磁盘空间却没释放"的原因（`lsof | grep deleted`）。

## 3. 路径查找（path walk）

`open("/home/a/b.txt")` → `do_filp_open()` → `path_openat()` → `link_path_walk()`：

1. 从根（或 `cwd`、`dirfd`）开始，对每个路径分量：
   - 在 **dcache**（以父 dentry + 名字哈希为键的全局哈希表）中查找。
   - 未命中 → 调用父目录 inode 的 `i_op->lookup()`，由具体文件系统读磁盘目录块并构造新 dentry。
   - 检查执行（搜索）权限 `MAY_EXEC`。
   - 处理符号链接（最多 40 层，防止循环）、`..`、挂载点穿越（`follow_managed`）。
2. 最后一个分量按 `O_CREAT`/`O_EXCL` 等标志决定是查找还是创建。

**RCU-walk**：路径查找首先尝试完全不拿锁、不增加引用计数的 RCU 模式（用 seqcount 检测并发修改）；遇到冲突或需要睡眠的操作时退回 **ref-walk**（逐个拿引用和锁）。这让热点路径（`stat` 大量文件）在多核上几乎线性扩展。

**负 dentry**：查找失败的名字也会缓存（`d_inode == NULL`），避免反复去磁盘确认"不存在"（例如 `$PATH` 搜索可执行文件）。

`openat2()` 的 `RESOLVE_BENEATH`、`RESOLVE_NO_SYMLINKS`、`RESOLVE_IN_ROOT` 可以安全地限制路径解析范围，防止 `../` 和符号链接逃逸。

## 4. 读写路径

### 4.1 缓冲 I/O（默认）

```
read(fd, buf, n)
 → ksys_read → vfs_read → file->f_op->read_iter
   → 通用实现 generic_file_read_iter → filemap_read
      → 在 i_mapping 的 xarray 中按页索引查 folio
         命中 → copy_folio_to_iter（拷贝给用户）
         未命中 → page_cache_sync_ra（同步预读）
                  → a_ops->read_folio / readahead → 提交 bio → 等待 I/O 完成
      → 顺序访问时触发异步预读（page_cache_async_ra），窗口动态增长
```

```
write(fd, buf, n)
 → vfs_write → f_op->write_iter → generic_perform_write
   → a_ops->write_begin（找到/分配 folio，必要时先读入旧数据）
   → copy_from_iter 把用户数据拷进 page cache
   → a_ops->write_end → 标记脏页，更新 i_size
   → 返回（此时数据还没上盘！）
 → 之后由回写线程或 fsync 落盘
```

**预读（readahead）**：内核检测顺序访问模式，从最初几个页逐步扩大到 `read_ahead_kb`（默认 128KB）。`posix_fadvise(POSIX_FADV_SEQUENTIAL/RANDOM)`、`readahead()` 可以调整。

### 4.2 落盘保证

| 操作 | 保证 |
|---|---|
| `write()` 返回 | 数据进入 page cache，**断电会丢** |
| `fsync(fd)` | 文件数据 + 元数据落盘，并发出设备缓存刷新（FLUSH/FUA） |
| `fdatasync(fd)` | 只保证数据和读取数据必需的元数据（大小），不一定更新 mtime |
| `sync_file_range` | 只发起回写，**不保证**元数据与持久性 |
| `O_SYNC` / `O_DSYNC` | 每次 write 等同于之后跟一次 fsync/fdatasync |
| `syncfs` / `sync` | 整个文件系统 / 全部文件系统 |

**新建文件的持久性陷阱**：`fsync(file)` 不保证目录项落盘。经典的"写临时文件 + `rename` 原子替换"需要：`write` → `fsync(tmpfile)` → `rename` → `fsync(dir_fd)`。

### 4.3 直接 I/O 与 mmap

- **`O_DIRECT`**：绕过 page cache，DMA 直接在用户缓冲区和设备之间进行。要求偏移、长度和缓冲区地址按逻辑块大小（通常 512B 或 4KB）对齐。数据库用它自管理缓存。实现走 `iomap_dio_rw`。
- **`mmap`（文件映射）**：把 page cache 页直接映射进进程页表，读写不经系统调用，缺页时从文件读入；`MAP_SHARED` 的修改通过脏页回写落盘（`msync` 强制）。
- **零拷贝**：`sendfile`、`splice`、`copy_file_range`（同文件系统内可能变成服务端复制/reflink）、`FICLONE`（btrfs/xfs 的 reflink，只复制元数据）。

## 5. 文件锁与通知

| 机制 | 语义 |
|---|---|
| `flock` | 整文件、绑定到 open file description，`fork` 后共享 |
| `fcntl(F_SETLK)` POSIX 锁 | 字节范围，绑定到进程，**进程关闭该文件的任何一个 fd 都会释放所有锁**（著名坑） |
| `fcntl(F_OFD_SETLK)` | 字节范围、绑定到 open file description，修正上述问题，推荐使用 |
| lease / delegation | 别人打开时通知持有者（Samba、NFS） |
| inotify / fanotify | 文件变化事件通知；fanotify 可做全文件系统监控与访问拦截（杀毒软件） |

默认都是**建议性锁**（advisory），不遵守协议的进程照样能读写。

## 6. 挂载与命名空间

- `mount` 把一个 `super_block` 的根 dentry 接到某个目录 dentry 上，形成 `vfsmount` 树。
- 同一个文件系统可以多次挂载（bind mount：`mount --bind`），共享同一 `super_block`。
- **mount namespace**：每个命名空间一棵独立的挂载树，容器的根文件系统隔离就靠它（加 `pivot_root`）。
- **挂载传播**（shared/slave/private/unbindable）决定一个命名空间里的挂载事件是否传到别处（systemd 默认把 `/` 设为 shared）。
- 新挂载 API（5.2 起）：`fsopen` → `fsconfig` → `fsmount` → `move_mount`，替代参数格式混乱的 `mount(2)`。
- **overlayfs**：把只读的下层（镜像层）与可写的上层叠成一个视图，写时把文件"copy-up"到上层；是 Docker/containerd 镜像的基础。

## 7. 具体文件系统

### 7.1 ext4（磁盘文件系统的代表）

| 设计 | 说明 |
|---|---|
| 块组（block group） | 磁盘按组划分，每组有块位图、inode 位图、inode 表，减少寻道并局部化元数据 |
| **extent** | 用"起始块 + 长度"描述连续区域，替代 ext2/3 的间接块指针，大文件元数据大幅缩小；extent 树存在 inode 中 |
| **日志（jbd2）** | 先把元数据（或数据）变更写进日志，提交后再写回原位置，崩溃恢复只需重放日志。模式：`data=ordered`（默认：数据先落盘，再提交元数据日志）、`data=writeback`、`data=journal` |
| 延迟分配（delalloc） | 写入时只预留空间，回写时才真正分配块，可合并为大的连续 extent，减少碎片 |
| 多块分配器（mballoc） | 一次分配多块，有预分配机制 |
| HTree 目录索引 | 目录项用哈希 B 树索引，大目录查找为 O(log n) |
| 元数据校验 | `metadata_csum`，检测静默损坏 |

### 7.2 其它文件系统的特点

| 文件系统 | 特点 |
|---|---|
| **XFS** | 按分配组（AG）并行、B+ 树管理空间、擅长大文件和高并发；支持 reflink；不能缩小 |
| **Btrfs** | 写时复制（CoW）B 树，快照、子卷、数据校验、透明压缩、多设备 RAID；碎片化与写放大是代价 |
| **tmpfs** | 数据就在 page cache / swap 里，无后备磁盘；`/dev/shm`、`/run` |
| **procfs / sysfs** | 读写时内核**动态生成内容**，没有存储；`/proc/<pid>` 下的文件由 `fs/proc/base.c` 生成 |
| **FUSE** | 文件系统逻辑在用户态进程里，内核把请求通过 `/dev/fuse` 转发；sshfs、rclone 等 |
| **NFS / CIFS** | 网络文件系统，VFS 层的 `d_revalidate` 用于确认缓存未过期 |
| **erofs / squashfs** | 只读压缩文件系统，常用于镜像、Android 系统分区 |

### 7.3 iomap：现代文件系统的共同底座

`fs/iomap/` 提供"文件偏移 → 磁盘块映射"的通用框架，文件系统只需实现 `iomap_begin`/`iomap_end` 回调，缓冲 I/O、直接 I/O、`fiemap`、DAX、`SEEK_HOLE` 等都由通用代码完成。XFS 最早采用，ext4/btrfs/gfs2 等逐步迁移。这是 VFS "把通用逻辑上移"思路的延续（从 buffer_head 到 iomap）。

## 8. 实现一个最简文件系统要做什么

1. `register_filesystem(&my_fs_type)`，提供 `init_fs_context`（新 API）或 `mount` 回调。
2. 填充 `super_block`：`s_op`、`s_magic`、根 inode 与根 dentry（`d_make_root`）。
3. 为 inode 设置 `i_op`（目录：`lookup`/`create`/`mkdir`；普通文件：`setattr`）和 `i_fop`（`read_iter`/`write_iter` 可直接用 `generic_file_*`）。
4. 提供 `address_space_operations`（`read_folio`、`writepages`、`write_begin`/`write_end`），把页与存储对应起来。
5. 参考实现：`fs/ramfs/`（最简单，几百行）、`fs/libfs.c`（通用辅助函数，`simple_*`）。

## 9. 观测与调试

```bash
cat /proc/self/mountinfo             # 挂载树（含传播属性和 mount ID）
findmnt                              # 树状显示挂载
cat /proc/sys/fs/dentry-state        # dentry 缓存数量
slabtop | grep -E 'dentry|inode'     # 缓存占用
echo 2 > /proc/sys/vm/drop_caches    # 释放 dentry/inode 缓存（测试用，勿在生产随意执行）
strace -e trace=%file ls             # 看进程访问了哪些路径
bpftrace -e 'kprobe:vfs_read { @[comm] = count(); }'
```

bcc 工具：`opensnoop`（谁打开了什么）、`filetop`、`ext4slower`/`xfsslower`（慢操作）、`vfsstat`、`cachestat`。

## 10. 关键文件

| 路径 | 内容 |
|---|---|
| `include/linux/fs.h` | `super_block`、`inode`、`file`、各操作表 |
| `include/linux/dcache.h`、`fs/dcache.c` | dentry 与 dcache |
| `fs/namei.c` | 路径查找、`open`/`mkdir`/`rename` 等的 VFS 实现 |
| `fs/open.c`、`fs/read_write.c` | `open`、`read`、`write` 系统调用 |
| `fs/file.c`、`fs/file_table.c` | fd 表与 `struct file` 管理 |
| `fs/namespace.c` | 挂载、mount namespace |
| `mm/filemap.c` | page cache 读写核心 |
| `fs/iomap/` | 通用块映射框架 |
| `fs/ext4/`、`fs/jbd2/` | ext4 与其日志层 |

## 小结

VFS 的核心是**四个对象 + 四张操作表**：`super_block` 表示文件系统实例，`inode` 表示文件，`dentry` 表示名字，`file` 表示一次打开。性能靠三层缓存（dcache、inode cache、page cache）和 RCU-walk；持久性则必须由应用显式用 `fsync` 争取。具体文件系统只需实现操作表，大量通用逻辑（页缓存、预读、iomap）由 VFS 与 mm 提供。
