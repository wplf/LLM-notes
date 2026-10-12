# LLM-notes
For recording useful knowledge about LLMs and computers.

## Index

### 硬件 / Hardware
- [芯片间互联技术概览](chip-interconnect/chip-interconnect-overview.md) — 3D 堆叠、2.5D/Chiplet、铜 SerDes、无线耦合、晶圆级集成与光互连的优缺点对比
- [Hot Chips 2026 报告汇总](hot-chips-2026/hot-chips-2026-summary.md) — 48 个报告（26 正会 + 1 keynote + 10 tutorial + 11 poster）的中文摘要，按 session 整理，含贯穿全会的主线归纳
- EE273 数字系统工程（Stanford 课程笔记）
    - [课程总览与讲次目录](ee273-digital-systems-engineering/index.md) — Dally 2001 年冬季学期 16 讲讲义的中文笔记：导线、噪声、信号传输、时序与同步、电源分配
    - [第 1 讲 数字系统工程导论](ee273-digital-systems-engineering/lec01-introduction.md)
    - [第 2 讲 导线](ee273-digital-systems-engineering/lec02-wires.md)
    - [第 3 讲 导线（续）：多点总线、平衡线与测量](ee273-digital-systems-engineering/lec03-wires-concluded.md)
    - [第 4 讲 数字系统中的噪声](ee273-digital-systems-engineering/lec04-noise.md)
    - [第 5 讲 回流串扰、码间干扰与噪声管理](ee273-digital-systems-engineering/lec05-return-crosstalk-isi-noise-budget.md)
    - [第 6 讲 信号传输入门](ee273-digital-systems-engineering/lec06-signaling-intro.md)
    - [第 7 讲 信号传输（二）](ee273-digital-systems-engineering/lec07-signaling-part-two.md)
    - [第 8 讲 高级信号传输](ee273-digital-systems-engineering/lec08-advanced-signaling.md)
    - [第 9 讲 时序基础](ee273-digital-systems-engineering/lec09-timing.md)
    - [第 10 讲 闭环时序](ee273-digital-systems-engineering/lec10-closed-loop-timing.md)
    - [第 11 讲 时钟分配](ee273-digital-systems-engineering/lec11-clock-distribution.md)
    - [第 12 讲 同步](ee273-digital-systems-engineering/lec12-synchronization.md)
    - [第 13 讲 同步器设计](ee273-digital-systems-engineering/lec13-synchronizer-design.md)
    - [第 14 讲 片外电源分配](ee273-digital-systems-engineering/lec14-off-chip-power.md)
    - [第 15 讲 片上电源分配](ee273-digital-systems-engineering/lec15-on-chip-power.md)
    - [第 16 讲 总结与课程项目讲评](ee273-digital-systems-engineering/lec16-wrap-up.md)
- ECEN 720 高速链路电路与系统（Texas A&M 课程笔记）
- [课程总览与讲次目录](ecen720-high-speed-links/index.md) — Palermo 2025 年春季学期 16 讲讲义的中文笔记：信道、调制、均衡、收发电路、时钟、Chiplet 互联与光收发器
    - [第 1 讲 课程介绍](ecen720-high-speed-links/lec01-introduction.md)
    - [第 2 讲 信道元件、导线与传输线](ecen720-high-speed-links/lec02-channels.md)
    - [第 3 讲 时域反射与 S 参数信道模型](ecen720-high-speed-links/lec03-tdr-sparameters.md)
    - [第 4 讲 信道脉冲模型与调制方式](ecen720-high-speed-links/lec04-pulse-model-modulation.md)
    - [第 5 讲 端接、发送驱动器与复用器电路](ecen720-high-speed-links/lec05-termination-tx-driver.md)
    - [第 6 讲 接收电路](ecen720-high-speed-links/lec06-rx-circuits.md)
    - [第 7 讲 均衡概述与发送端 FIR 均衡](ecen720-high-speed-links/lec07-equalization-tx-fir.md)
    - [第 8 讲 接收端 FIR、CTLE、DFE 与自适应均衡](ecen720-high-speed-links/lec08-rx-equalization.md)
    - [第 9 讲 噪声源](ecen720-high-speed-links/lec09-noise-sources.md)
    - [第 10 讲 抖动](ecen720-high-speed-links/lec10-jitter.md)
    - [第 11 讲 时钟架构与 PLL](ecen720-high-speed-links/lec11-clocking-plls.md)
    - [第 12 讲 时钟数据恢复（CDR）](ecen720-high-speed-links/lec12-cdrs.md)
    - [第 13 讲 前向时钟去偏斜电路](ecen720-high-speed-links/lec13-forwarded-clock-deskew.md)
    - [第 14 讲 时钟分配技术](ecen720-high-speed-links/lec14-clock-distribution.md)
    - [第 15 讲 裸片间（Die-to-Die）收发器](ecen720-high-speed-links/lec15-die-to-die.md)
    - [第 16 讲 光收发器](ecen720-high-speed-links/lec16-optical-transceivers.md)

### 操作系统 / Operating System
- [Linux 内核的构成（入门版）](linux-kernel/linux-kernel-architecture.md) — 用户态与内核态、系统调用、五大子系统（调度/内存/VFS/网络/驱动）、宏内核与模块、源码目录与学习路线

### 金融 / Finance
- [量化交易核心概念入门教程](quant-trading/quant-trading-basics.md) — 量化流程、数据偏差、Alpha/Beta、因子与 IC、常见策略、回测陷阱、绩效指标、组合风控与执行，附双均线示例代码
- 《打开量化投资的黑箱》读书笔记
    - [《打开量化投资的黑箱》导读](inside-the-black-box/index.md) — Rishi Narang 著（第 2 版），全书框架与章节目录
    - [第 1 章 关注量化交易的原因](inside-the-black-box/ch01-why-quant-matters.md)
    - [第 2 章 量化交易简介](inside-the-black-box/ch02-intro-to-quant-trading.md)
    - [第 3 章 阿尔法模型：宽客如何盈利](inside-the-black-box/ch03-alpha-models.md)
    - [第 4 章 风险模型](inside-the-black-box/ch04-risk-models.md)
    - [第 5 章 交易成本模型](inside-the-black-box/ch05-transaction-cost-models.md)
    - [第 6 章 投资组合构建模型](inside-the-black-box/ch06-portfolio-construction.md)
    - [第 7 章 执行模型](inside-the-black-box/ch07-execution.md)
    - [第 8 章 数据](inside-the-black-box/ch08-data.md)
    - [第 9 章 研究](inside-the-black-box/ch09-research.md)
    - [第 10 章 量化策略的风险内生性](inside-the-black-box/ch10-inherent-risks.md)
    - [第 11 章 对量化交易的批评](inside-the-black-box/ch11-criticisms.md)
    - [第 12 章 评估宽客和量化交易策略](inside-the-black-box/ch12-evaluating-quants.md)
    - [第 13 章 高速及高频交易概要](inside-the-black-box/ch13-intro-to-hft.md)
    - [第 14 章 高速交易](inside-the-black-box/ch14-high-speed-trading.md)
    - [第 15 章 高频交易](inside-the-black-box/ch15-high-frequency-trading.md)
    - [第 16 章 关于高频交易的争论](inside-the-black-box/ch16-hft-controversy.md)
    - [第 17 章 量化交易的展望](inside-the-black-box/ch17-future.md)

### 分布式训练 / Distributed Training
- [分层分片数据并行（HSDP）的设计原理](hsdp/hsdp-design-principles.md) — 相对 FSDP2 省掉哪些拷贝、三级 ZeRO 分片、两段梯度归约、对称内存通信、梯度直写，以及显存统计、空分组脏数据、FP64 热路径等坑
