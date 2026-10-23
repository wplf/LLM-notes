# MIT 6.S081 操作系统工程（Fall 2021）学习 TODO

> 来源：[6.S081 Fall 2021 Schedule](https://pdos.csail.mit.edu/6.828/2021/schedule.html)（课程主页：[6.S081](https://pdos.csail.mit.edu/6.828/2021/)）。
> 以下按原课表逐周整理，链接已转为绝对地址；课程材料为英文，保留原文。
> 每讲的 2020 年视频/笔记是 2021 年同主题讲座的往年录像。

## 课程资源

- [ ] 搭建实验环境：[Tools](https://pdos.csail.mit.edu/6.828/2021/tools.html)（RISC-V 工具链 + QEMU）
- [ ] 阅读实验指南：[Lab guidance](https://pdos.csail.mit.edu/6.828/2021/labs/guidance.html)
- 教材：[xv6: a simple, Unix-like teaching operating system（book-riscv-rev2）](https://pdos.csail.mit.edu/6.828/2021/xv6/book-riscv-rev2.pdf)
- 源码：[mit-pdos/xv6-riscv](https://github.com/mit-pdos/xv6-riscv)

## 实验总览

| # | 实验 | 布置 | 截止 |
|---|---|---|---|
| 1 | [util: Unix utilities](https://pdos.csail.mit.edu/6.828/2021/labs/util.html) | 09-08 | 09-16 |
| 2 | [syscall: System calls](https://pdos.csail.mit.edu/6.828/2021/labs/syscall.html) | 09-15 | 09-23 |
| 3 | [pgtbl: Page tables](https://pdos.csail.mit.edu/6.828/2021/labs/pgtbl.html) | 09-22 | 09-30 |
| 4 | [traps: Traps](https://pdos.csail.mit.edu/6.828/2021/labs/traps.html) | 09-29 | 10-07 |
| 5 | [cow: Copy-on-write fork](https://pdos.csail.mit.edu/6.828/2021/labs/cow.html) | 10-06 | 10-21 |
| 6 | [thread: Multithreading](https://pdos.csail.mit.edu/6.828/2021/labs/thread.html) | 10-20 | 10-28 |
| 7 | [net: Network driver](https://pdos.csail.mit.edu/6.828/2021/labs/net.html) | 10-27 | 11-09 |
| 8 | [lock: Parallelism/locking](https://pdos.csail.mit.edu/6.828/2021/labs/lock.html) | 11-10 | 11-18 |
| 9 | [fs: File system](https://pdos.csail.mit.edu/6.828/2021/labs/fs.html) | 11-17 | 11-24 |
| 10 | [mmap: Mmap](https://pdos.csail.mit.edu/6.828/2021/labs/mmap.html) | 11-24 | 12-07 |

## 逐周课表

### 09-06 当周

- 09-06 Mon — Labor Day
- 09-07 Tue — Reg Day
- [ ] 09-08 Wed — **LEC 1 (ab):** [Introduction](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-intro.pdf) and [examples](https://pdos.csail.mit.edu/6.828/2021/lec/l-overview/) (handouts: [xv6 book](https://pdos.csail.mit.edu/6.828/2021/xv6/book-riscv-rev2.pdf); 2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-overview.txt), [video](https://youtu.be/L6YqHxYHa7A))
    - [ ] **Preparation**: [Read chapter 1](https://pdos.csail.mit.edu/6.828/2021/xv6/book-riscv-rev2.pdf) (for your amusement: [Unix](https://www.youtube.com/watch?v=tc4ROCJYbm0))
    - [ ] **Homework 1 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
    - [ ] **Assignment**: [Lab util: Unix utilities](https://pdos.csail.mit.edu/6.828/2021/labs/util.html)

### 09-13 当周

- [ ] 09-13 Mon — **LEC 2 (TAs):** [C](https://pdos.csail.mit.edu/6.828/2021/lec/6S081-Intro-to-C-Fa21.pdf) and [gdb](https://pdos.csail.mit.edu/6.828/2021/lec/gdb_slides.pdf)
    - [ ] **Preparation**: 2.9 (Bitwise operators) and 5.1 (Pointers and addresses) through 5.6 (Pointer arrays) and 6.4 (pointers to structures) by Kernighan and Ritchie (K&R)
- [ ] 09-15 Wed — **LEC 3 (ab):** [OS organization and system calls](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-osorg.pdf) (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-os.txt) <!-- 原页面链接 lec-los.txt 已失效，改为 2020 课表中的 lec/l-os.txt -->, [boards](https://pdos.csail.mit.edu/6.828/2021/lec/l-os-boards.pdf), [video](https://youtu.be/o44d---Dk4o))
    - [ ] **Preparation**: [Read chapter 2](https://pdos.csail.mit.edu/6.828/2021/xv6/book-riscv-rev2.pdf) and xv6 code: [kernel/proc.h](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/proc.h), [kernel/defs.h](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/defs.h), [kernel/entry.S](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/entry.S), [kernel/main.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/main.c), [user/initcode.S](https://github.com/mit-pdos/xv6-riscv/blob/riscv/user/initcode.S), [user/init.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/user/init.c), and skim [kernel/proc.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/proc.c) and [kernel/exec.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/exec.c)
    - [ ] **Homework 2 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
    - [ ] **Assignment**: [Lab syscall: System calls](https://pdos.csail.mit.edu/6.828/2021/labs/syscall.html)
- [ ] 09-16 Thu — **DUE**: Lab util

### 09-20 当周

- [ ] 09-20 Mon — **LEC 4 (ab):** [Page tables](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-vm.pdf) (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-vm.txt), [boards](https://pdos.csail.mit.edu/6.828/2021/lec/l-vm-boards.pdf), [video](https://youtu.be/f1Hpjty3TT8))
    - [ ] **Preparation**: Read [Chapter 3](https://pdos.csail.mit.edu/6.828/2021/xv6/book-riscv-rev2.pdf) and [kernel/memlayout.h](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/memlayout.h), [kernel/vm.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/vm.c), [kernel/kalloc.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/kalloc.c), [kernel/riscv.h](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/riscv.h), and [kernel/exec.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/exec.c)
    - [ ] **Homework 3 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
- [ ] 09-22 Wed — **LEC 5 (TAs):** [GDB, calling conventions and stack frames RISC-V](https://pdos.csail.mit.edu/6.828/2021/lec/gdb_slides.pdf) (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-riscv.txt), [boards](https://pdos.csail.mit.edu/6.828/2021/lec/l-riscv-slides.pdf), [video](https://youtu.be/s-Z5t_yTyTM))
    - [ ] **Preparation**: Read [Calling Convention](https://pdos.csail.mit.edu/6.828/2021/readings/riscv-calling.pdf)
    - [ ] **Assignment**: [Lab pgtbl: Page tables](https://pdos.csail.mit.edu/6.828/2021/labs/pgtbl.html)
- [ ] 09-23 Thu — **DUE**: Lab syscall

### 09-27 当周

- [ ] 09-27 Mon — **LEC 6 (ab):** [Isolation & system call entry/exit](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-syscall.pdf) (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-internal.txt), [video](https://youtu.be/T26UuauaxWA))
    - [ ] **Preparation**: Read [Chapter 4, except 4.6](https://pdos.csail.mit.edu/6.828/2021/xv6/book-riscv-rev2.pdf) and [kernel/riscv.h](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/riscv.h), [kernel/trampoline.S](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/trampoline.S), and [kernel/trap.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/trap.c)
    - [ ] **Homework 4 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
- [ ] 09-29 Wed — **LEC 7 (ab):** [Page faults](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-usingvm.pdf) (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-pgfaults.txt), [boards](https://pdos.csail.mit.edu/6.828/2021/lec/l-pgfaults.pdf), [video](https://youtu.be/KSYO-gTZo0A))
    - [ ] **Preparation**: Read [Section 4.6](https://pdos.csail.mit.edu/6.828/2021/xv6/book-riscv-rev2.pdf)
    - [ ] **Homework 5 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
    - [ ] **Assignment**: [Lab traps: Traps](https://pdos.csail.mit.edu/6.828/2021/labs/traps.html)
- [ ] 09-30 Thu — **DUE**: Lab pgtbl

### 10-04 当周

- [ ] 10-04 Mon — **LEC 8 (ab):** [Q&A labs](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-qa1.pdf)
    - [ ] **Homework 6 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/QA.html)
- [ ] 10-06 Wed — **LEC 9 (ab):** [Interrupts](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-interrupts.pdf) (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-interrupt.txt), [boards](https://pdos.csail.mit.edu/6.828/2021/lec/l-interrupt.pdf), [video](https://youtu.be/zRnGNndcVEA))
    - [ ] **Preparation**: Read [Chapter 5](https://pdos.csail.mit.edu/6.828/2021/xv6/book-riscv-rev2.pdf) and [kernel/kernelvec.S](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/kernelvec.S), [kernel/plic.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/plic.c), [kernel/console.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/console.c), [kernel/uart.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/uart.c), [kernel/printf.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/printf.c)
    - [ ] **Homework 7 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
    - [ ] **Assignment**: [Lab cow: Copy-on-write fork](https://pdos.csail.mit.edu/6.828/2021/labs/cow.html)
- [ ] 10-07 Thu — **DUE**: Lab traps
- 10-08 Fri — ADD DATE

### 10-11 当周

- 10-11 Mon — Indigenous Peoples Day
- [ ] 10-13 Wed — **LEC 10 (ab):** [Multiprocessors and locking](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-locks.pdf) (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-lockv2.txt), [boards](https://pdos.csail.mit.edu/6.828/2021/lec/l-lock.pdf), [video](https://youtu.be/NGXu3vN7yAk))
    - [ ] **Preparation**: Read ["Locking"](https://pdos.csail.mit.edu/6.828/2021/xv6/book-riscv-rev2.pdf) with [kernel/spinlock.h](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/spinlock.h) and [kernel/spinlock.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/spinlock.c)
    - [ ] **Homework 8 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)

### 10-18 当周

- [ ] 10-18 Mon — **LEC 11 (ab):** [Scheduling 1](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-threads.pdf) (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-threads.txt), [video](https://youtu.be/vsgrTHY5tkg))
    - [ ] **Preparation**: Read ["Scheduling"](https://pdos.csail.mit.edu/6.828/2021/xv6/book-riscv-rev2.pdf) through Section 7.4, and [kernel/proc.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/proc.c), [kernel/swtch.S](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/swtch.S)
    - [ ] **Homework 9 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
- [ ] 10-20 Wed — **LEC 12 (ab):** [Scheduling 2](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-threads2.pdf) (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-coordination.txt), [code](https://pdos.csail.mit.edu/6.828/2021/lec/l-coordination.c), [video](https://youtu.be/gP67sJ4PTnc))
    - [ ] **Preparation**: Read remainder of ["Scheduling"](https://pdos.csail.mit.edu/6.828/2021/xv6/book-riscv-rev2.pdf), and corresponding parts of [kernel/proc.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/proc.c), [kernel/sleeplock.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/sleeplock.c)
    - [ ] **Homework 10 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
    - [ ] **Assignment**: [Lab thread: Multithreading](https://pdos.csail.mit.edu/6.828/2021/labs/thread.html)
- [ ] 10-21 Thu — **DUE**: Lab cow

### 10-25 当周

- [ ] 10-25 Mon — **LEC 13 (ab):** [Q&A labs](https://pdos.csail.mit.edu/6.828/2021/slides/6s081-lec-qa2.pdf)
    - [ ] **Homework 11 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/QA.html)
- [ ] 10-27 Wed — **LEC 14 (ab):** File systems (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-fs.txt), [boards](https://pdos.csail.mit.edu/6.828/2021/lec/l-fs.pdf), [video](https://youtu.be/ADzLv1nRtR8))
    - [ ] **Preparation**: Read [kernel/bio.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/bio.c), [kernel/fs.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/fs.c), [kernel/sysfile.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/sysfile.c), [kernel/file.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/file.c) and ["File system" (except for the logging sections)](https://pdos.csail.mit.edu/6.828/2021/xv6/book-riscv-rev2.pdf) <!-- 原页面链接 xv6-book-riscv-rev2.pdf 已失效 -->
    - [ ] **Homework 12 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
    - [ ] **Assignment**: [Lab net: Network driver](https://pdos.csail.mit.edu/6.828/2021/labs/net.html)
- [ ] 10-28 Thu — **DUE**: Lab thread

### 11-01 当周

- [ ] 11-01 Mon — **LEC 15 (ab):** Crash recovery (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-crash.txt), [boards](https://pdos.csail.mit.edu/6.828/2021/lec/l-crash.pdf), [video](https://youtu.be/7Hk2dIorDkk))
    - [ ] **Preparation**: Read [kernel/log.c](https://github.com/mit-pdos/xv6-riscv/blob/riscv/kernel/log.c) and the logging sections of "File system"
    - [ ] **Homework 13 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
- [ ] 11-03 Wed — **LEC 16 (ab):** File system performance and fast crash recovery (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-journal.txt), [video](https://youtu.be/CmDcf6rjFb4))
    - [ ] **Preparation**: Read [Journaling the Linux ext2fs Filesystem (1998)](https://pdos.csail.mit.edu/6.828/2021/readings/journal-ext2fs.html)
    - [ ] **Homework 14 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)

### 11-08 当周

- [ ] 11-08 Mon — **LEC 17 (ab):** Virtual memory for applications (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-uservm.txt), [boards](https://pdos.csail.mit.edu/6.828/2021/lec/l-uservm.pdf), [video](https://youtu.be/YNQghIvk0jc)) ([baker example](https://pdos.csail.mit.edu/6.828/2021/lec/baker.c))
    - [ ] **Preparation**: Read [Virtual Memory Primitives for User Programs (1991)](https://pdos.csail.mit.edu/6.828/2021/readings/appel-li.pdf)
    - [ ] **Homework 15 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
- [ ] 11-09 Tue — **DUE**: Lab net
- [ ] 11-10 Wed — **LEC 18 (ab):** OS Organization (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-organization.txt), [video](https://youtu.be/dM9PLdaTpnA))
    - [ ] **Preparation**: Read [The Performance of micro-Kernel-Based Systems (1997)](https://pdos.csail.mit.edu/6.828/2021/readings/microkernel.pdf)
    - [ ] **Homework 16 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
    - [ ] **Assignment**: [Lab lock: Parallelism/locking](https://pdos.csail.mit.edu/6.828/2021/labs/lock.html)
- 11-11 Thu — Veteran's Day

### 11-15 当周

- [ ] 11-15 Mon — **LEC 19 (ab):** Virtual Machines (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-vmm.txt), [video](https://youtu.be/R8obXHAIPY0))
    - [ ] **Preparation**: Read [Dune: Safe User-level Access to Privileged CPU Features (2012)](https://pdos.csail.mit.edu/6.828/2021/readings/belay-dune.pdf)
    - [ ] **Homework 17 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
- [ ] 11-17 Wed — **LEC 20 (ab):** Kernels and HLL (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-biscuit.txt), [slides](https://pdos.csail.mit.edu/6.828/2021/lec/l-biscuit-slides.pdf), [video](https://youtu.be/AAtXWGwxI9k))
    - [ ] **Preparation**: Read [the Biscuit paper (2018)](https://pdos.csail.mit.edu/6.828/2021/readings/biscuit.pdf), [FAQ](https://pdos.csail.mit.edu/6.828/2021/lec/faq-biscuit.txt)
    - [ ] **Homework 18 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
    - [ ] **Assignment**: [Lab fs: File system](https://pdos.csail.mit.edu/6.828/2021/labs/fs.html)
- 11-18 Thu — **DROP DATE**
- [ ] 11-18 Thu — **DUE**: Lab lock

### 11-22 当周

- [ ] 11-22 Mon — **LEC 21 (ab):** Networking (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-net.txt), [video](https://youtu.be/Fcjychg4Tvk))
    - [ ] **Preparation**: Read [Receive Livelock (1996)](https://pdos.csail.mit.edu/6.828/2021/readings/mogul96usenix.pdf)
    - [ ] **Homework 19 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
- 11-24 Wed — Hacking day: no class meeting; work on the lab
- [ ] 11-24 Wed — **DUE**: Lab fs
- [ ] 11-24 Wed — **Assignment**: [Lab mmap: Mmap](https://pdos.csail.mit.edu/6.828/2021/labs/mmap.html)

### 11-29 当周

- [ ] 11-29 Mon — **LEC 22 (ab):** Meltdown (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-meltdown.txt), [video](https://youtu.be/WpKVr3p5rjE))
    - [ ] **Preparation**: Read [Meltdown (2018)](https://pdos.csail.mit.edu/6.828/2021/readings/meltdown.pdf)
    - [ ] **Homework 20 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
- [ ] 12-01 Wed — **LEC 23 (ab):** Multi-Core scalability and RCU (2020: [notes](https://pdos.csail.mit.edu/6.828/2021/lec/l-rcu.txt), [video](https://youtu.be/KUwyCGMTeq8))
    - [ ] **Preparation**: Read [RCU paper (2013)](https://pdos.csail.mit.edu/6.828/2021/readings/rcu-decade-later.pdf), [FAQ](https://pdos.csail.mit.edu/6.828/2021/lec/rcu-faq.txt)
    - [ ] **Homework 21 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)

### 12-06 当周

- [ ] 12-06 Mon — **LEC 24 (TAs):** Current Research: [Radiation Tolerance](https://pdos.csail.mit.edu/6.828/2021/lec/CelSkeggsRadiationTolerance.pdf)
    - [ ] **Preparation**: Read [NASA CALIPSO paper (2006)](https://pdos.csail.mit.edu/6.828/2021/readings/nasa-calipso-radiation.pdf) for background
    - [ ] **Homework 22 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/q.html)
- [ ] 12-07 Tue — **DUE**: Lab mmap
- [ ] 12-08 Wed — **LEC 25 (ab):** Q&A
    - [ ] **Homework 23 due:** [Question](https://pdos.csail.mit.edu/6.828/2021/homework/QA.html)
- 12-09 Thu — LAST DAY OF CLASSES
