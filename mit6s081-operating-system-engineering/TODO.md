# MIT 6.S081 操作系统工程（2021 秋）学习 TODO

> 来源：[6.S081 Fall 2021 课表](https://pdos.csail.mit.edu/6.828/2021/schedule.html)。教材为 [xv6 讲义](https://pdos.csail.mit.edu/6.828/2021/xv6/book-riscv-rev2.pdf)，源码为 [xv6-riscv](https://github.com/mit-pdos/xv6-riscv)；课程材料均为英文。

## 准备

- [ ] 搭建实验环境（RISC-V 工具链 + QEMU）：[工具说明](https://pdos.csail.mit.edu/6.828/2021/tools.html)
- [ ] 阅读[实验指南](https://pdos.csail.mit.edu/6.828/2021/labs/guidance.html)

## 课程

- [ ] 第 1 讲 课程介绍与示例 — 预习：xv6 第 1 章 — [讲义](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-intro.pdf) / [视频](https://youtu.be/L6YqHxYHa7A)
- [ ] 第 2 讲 C 语言与 GDB — 预习：K&R 2.9、5.1–5.6、6.4 — [C 讲义](https://pdos.csail.mit.edu/6.828/2021/lec/6S081-Intro-to-C-Fa21.pdf) / [GDB 讲义](https://pdos.csail.mit.edu/6.828/2021/lec/gdb_slides.pdf)
- [ ] 第 3 讲 操作系统组织结构与系统调用 — 预习：xv6 第 2 章 — [讲义](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-osorg.pdf) / [视频](https://youtu.be/o44d---Dk4o)
- [ ] 第 4 讲 页表 — 预习：xv6 第 3 章 — [讲义](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-vm.pdf) / [视频](https://youtu.be/f1Hpjty3TT8)
- [ ] 第 5 讲 GDB、RISC-V 调用约定与栈帧 — 预习：[调用约定](https://pdos.csail.mit.edu/6.828/2021/readings/riscv-calling.pdf) — [讲义](https://pdos.csail.mit.edu/6.828/2021/lec/gdb_slides.pdf) / [视频](https://youtu.be/s-Z5t_yTyTM)
- [ ] 第 6 讲 隔离与系统调用的进入/退出 — 预习：xv6 第 4 章（除 4.6）— [讲义](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-syscall.pdf) / [视频](https://youtu.be/T26UuauaxWA)
- [ ] 第 7 讲 缺页异常 — 预习：xv6 4.6 节 — [讲义](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-usingvm.pdf) / [视频](https://youtu.be/KSYO-gTZo0A)
- [ ] 第 8 讲 实验答疑（一）— [讲义](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-qa1.pdf)
- [ ] 第 9 讲 中断 — 预习：xv6 第 5 章 — [讲义](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-interrupts.pdf) / [视频](https://youtu.be/zRnGNndcVEA)
- [ ] 第 10 讲 多处理器与锁 — 预习：xv6"锁"一章 — [讲义](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-locks.pdf) / [视频](https://youtu.be/NGXu3vN7yAk)
- [ ] 第 11 讲 调度（一）— 预习：xv6"调度"一章至 7.4 节 — [讲义](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-threads.pdf) / [视频](https://youtu.be/vsgrTHY5tkg)
- [ ] 第 12 讲 调度（二）：睡眠与唤醒 — 预习："调度"一章其余部分 — [讲义](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-threads2.pdf) / [视频](https://youtu.be/gP67sJ4PTnc)
- [ ] 第 13 讲 实验答疑（二）— [讲义](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-qa2.pdf)
- [ ] 第 14 讲 文件系统 — 预习：xv6"文件系统"一章（日志部分除外）— [笔记](https://pdos.csail.mit.edu/6.828/2021/lec/l-fs.txt) / [视频](https://youtu.be/ADzLv1nRtR8)
- [ ] 第 15 讲 崩溃恢复 — 预习："文件系统"一章的日志部分 — [笔记](https://pdos.csail.mit.edu/6.828/2021/lec/l-crash.txt) / [视频](https://youtu.be/7Hk2dIorDkk)
- [ ] 第 16 讲 文件系统性能与快速崩溃恢复 — 论文：[Journaling the Linux ext2fs Filesystem](https://pdos.csail.mit.edu/6.828/2021/readings/journal-ext2fs.html) — [视频](https://youtu.be/CmDcf6rjFb4)
- [ ] 第 17 讲 面向应用程序的虚拟内存 — 论文：[Virtual Memory Primitives for User Programs](https://pdos.csail.mit.edu/6.828/2021/readings/appel-li.pdf) — [视频](https://youtu.be/YNQghIvk0jc)
- [ ] 第 18 讲 操作系统组织结构：微内核 — 论文：[The Performance of μ-Kernel-Based Systems](https://pdos.csail.mit.edu/6.828/2021/readings/microkernel.pdf) — [视频](https://youtu.be/dM9PLdaTpnA)
- [ ] 第 19 讲 虚拟机 — 论文：[Dune](https://pdos.csail.mit.edu/6.828/2021/readings/belay-dune.pdf) — [视频](https://youtu.be/R8obXHAIPY0)
- [ ] 第 20 讲 用高级语言写内核 — 论文：[Biscuit](https://pdos.csail.mit.edu/6.828/2021/readings/biscuit.pdf) — [视频](https://youtu.be/AAtXWGwxI9k)
- [ ] 第 21 讲 网络 — 论文：[Receive Livelock](https://pdos.csail.mit.edu/6.828/2021/readings/mogul96usenix.pdf) — [视频](https://youtu.be/Fcjychg4Tvk)
- [ ] 第 22 讲 Meltdown 漏洞 — 论文：[Meltdown](https://pdos.csail.mit.edu/6.828/2021/readings/meltdown.pdf) — [视频](https://youtu.be/WpKVr3p5rjE)
- [ ] 第 23 讲 多核可扩展性与 RCU — 论文：[RCU](https://pdos.csail.mit.edu/6.828/2021/readings/rcu-decade-later.pdf) — [视频](https://youtu.be/KUwyCGMTeq8)
- [ ] 第 24 讲 前沿研究：抗辐射计算 — 背景阅读：[NASA CALIPSO](https://pdos.csail.mit.edu/6.828/2021/readings/nasa-calipso-radiation.pdf) — [讲义](https://pdos.csail.mit.edu/6.828/2021/lec/CelSkeggsRadiationTolerance.pdf)
- [ ] 第 25 讲 总复习答疑

> 第 1–24 讲的视频均为 2020 年同主题讲座录像（2021 年未公开视频）。

## 实验

- [ ] 实验 1：Unix 实用程序 — [util](https://pdos.csail.mit.edu/6.828/2021/labs/util.html)
- [ ] 实验 2：系统调用 — [syscall](https://pdos.csail.mit.edu/6.828/2021/labs/syscall.html)
- [ ] 实验 3：页表 — [pgtbl](https://pdos.csail.mit.edu/6.828/2021/labs/pgtbl.html)
- [ ] 实验 4：陷阱 — [traps](https://pdos.csail.mit.edu/6.828/2021/labs/traps.html)
- [ ] 实验 5：写时复制 fork — [cow](https://pdos.csail.mit.edu/6.828/2021/labs/cow.html)
- [ ] 实验 6：多线程 — [thread](https://pdos.csail.mit.edu/6.828/2021/labs/thread.html)
- [ ] 实验 7：网卡驱动 — [net](https://pdos.csail.mit.edu/6.828/2021/labs/net.html)
- [ ] 实验 8：并行与锁 — [lock](https://pdos.csail.mit.edu/6.828/2021/labs/lock.html)
- [ ] 实验 9：文件系统 — [fs](https://pdos.csail.mit.edu/6.828/2021/labs/fs.html)
- [ ] 实验 10：mmap — [mmap](https://pdos.csail.mit.edu/6.828/2021/labs/mmap.html)
