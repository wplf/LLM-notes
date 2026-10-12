# Texas A&M ECEN 720 高速链路电路与系统（High-Speed Links Circuits & Systems）课程笔记

- **课程**：ECEN 720 High-Speed Links Circuits and Systems，Texas A&M University
- **讲义版本**：2025 年春季学期，Sam Palermo 主讲，共 16 讲
- **教材**：无指定教材，以讲义和论文为主。参考书：
    1. Dally & Poulton，*Digital Systems Engineering*（1998），即本站 [EE273 笔记](../ee273-digital-systems-engineering/index.md) 的教材
    2. Hall & Heck，*Advanced Signal Integrity for High-Speed Digital Designs*（2009）
    3. Razavi，*Design of Integrated Circuits for Optical Communications*（2003）
    4. Johnson & Graham，*High-Speed Digital Design: A Handbook of Black Magic*（1993）
- **讲义来源**：[课程主页](https://people.engr.tamu.edu/spalermo/ecen720.html)（讲义、实验、历年考试、参考论文都公开）

!!! note "关于这份笔记"
    - 按**原讲义的讲次和幻灯片小节**整理，是中文概括，不是逐字翻译；讲义版权归 Sam Palermo 所有，原件见每讲页首链接。
    - 讲义大量引用 ISSCC / JSSC 论文，笔记里保留了"[作者 会议 年份]"形式的出处，方便回查原文。
    - 公式抽取时多有乱码，按标准形式重写，记号可能和原幻灯片略有出入。
    - 我补的计算或解释标了"（笔者）"。图、眼图、版图照片没有复现。
    - 第 11 讲后半部分（PLL 电路细节）讲义注明"不在考试范围"，属于前置课 ECEN 620 的内容，这里也整理了。

## 课程定位

讲高速**电**（以及光）信号传输的系统与设计问题。和 EE273 相比，这门课更贴近今天的 SerDes：PAM4、均衡器、CDR、ADC 接收机、Chiplet 互联和光模块都讲到了。

课程目标（大纲原文概括）：

1. 理解高速电/光信道的特性、建模、测量和通信技术；
2. 理解驱动器、接收器、均衡器、同步系统等链路电路的设计指标与实现；
3. 会用统计误码率（BER）分析和建模工具做链路系统设计；
4. 了解实现电/光串行链路标准的挑战和几种架构。

大纲的九个模块与讲次的对应：

| 模块 | 讲次 |
|---|---|
| I. 信道 | 1–3 |
| II. 通信技术（调制） | 4 |
| III. 均衡器 | 7–8 |
| IV. 发送 / 接收电路 | 5–6 |
| V. 均衡器电路 | 7–8 |
| VI. 时钟电路 | 11–12 |
| VII. 时钟系统 | 13–14 |
| VIII. 链路建模（噪声、抖动、BER） | 9–10 |
| IX. 链路实例 | 1、15、16 |

## 讲次目录

| 讲 | 主题 |
|---|---|
| [1](lec01-introduction.md) | 课程介绍、高速串行 I/O 应用、IBM 10 Gb/s 背板链路实例 |
| [2](lec02-channels.md) | 信道元件、导线模型、传输线、端接、差分线 |
| [3](lec03-tdr-sparameters.md) | TDR 与 S 参数信道模型、冲激响应、眼图 |
| [4](lec04-pulse-model-modulation.md) | 信道脉冲响应模型、峰值失真分析、NRZ 与 PAM4 |
| [5](lec05-termination-tx-driver.md) | 端接电路、发送驱动器、复用器 |
| [6](lec06-rx-circuits.md) | 接收电路：前端、时钟比较器、灵敏度与失调校正 |
| [7](lec07-equalization-tx-fir.md) | 均衡概述与发送端 FIR 均衡 |
| [8](lec08-rx-equalization.md) | 接收端 FIR、CTLE、DFE 与自适应均衡 |
| [9](lec09-noise-sources.md) | 噪声源与统计 BER 分析 |
| [10](lec10-jitter.md) | 抖动：定义、分类、双狄拉克模型、抖动预算 |
| [11](lec11-clocking-plls.md) | 时钟架构与 PLL |
| [12](lec12-cdrs.md) | 时钟数据恢复（CDR） |
| [13](lec13-forwarded-clock-deskew.md) | 前向时钟去偏斜电路 |
| [14](lec14-clock-distribution.md) | 时钟分配技术 |
| [15](lec15-die-to-die.md) | 裸片间（Die-to-Die）收发器 |
| [16](lec16-optical-transceivers.md) | 光收发器 |

第一次考试覆盖第 1–6 讲，第二次考试覆盖第 7–15 讲。

## 考核方式（2025 年）

| 项目 | 占比 | 说明 |
|---|---|---|
| 两次期中考试 | 50% | 各 25% |
| 实验与作业 | 25% | 6 次实验（预习 + 报告），用 Cadence 90 nm 模型和 MATLAB |
| 课程项目 | 25% | 1–3 人一组，给定真实背板信道的 S 参数，设计完整链路 |

实验、项目用的信道 S 参数文件（IEEE 802.3 背板信道）、MATLAB 脚本和历年考试解答都在课程主页上。

## 和本站其他笔记的关系

- 前置：[EE273 数字系统工程](../ee273-digital-systems-engineering/index.md)。本课第 2、9 讲的很多内容（传输线、串扰、噪声预算）直接引用 Dally 的教材。
- 第 15 讲（Chiplet 互联）和第 16 讲（光收发器）对应[芯片间互联技术概览](../chip-interconnect/chip-interconnect-overview.md)里的 2.5D/3D 封装和光互连两节。
