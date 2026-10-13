# Texas A&M ECEN 689/721 光互连电路与系统（Optical Interconnects Circuits & Systems）课程笔记

- **课程**：ECEN 689 Special Topics in Optical Interconnects Circuits and Systems（同一门课在新版大纲里编号为 ECEN 721），Texas A&M University
- **讲义版本**：2022 年春季学期，Sam Palermo 主讲，共 14 讲（大纲用的是 2024 年 ECEN 721 版）
- **教材**：无指定教材，以讲义和论文为主。参考书：
    1. Sackinger，*Broadband Circuits for Optical Fiber Communication*（Wiley，2005）——本课主要参考书
    2. Razavi，*Design of Integrated Circuits for Optical Communications*（2003）
    3. Hall & Heck，*Advanced Signal Integrity for High-Speed Digital Designs*（2009）
    4. Johnson & Graham，*High-Speed Digital Design: A Handbook of Black Magic*（1993）
- **讲义来源**：[课程主页](https://people.engr.tamu.edu/spalermo/ecen689_oi.html)

!!! note "关于这份笔记"
    - 按**原讲义的讲次和幻灯片小节**整理，是中文概括，不是逐字翻译；讲义版权归 Sam Palermo 所有，原件见每讲页首链接。
    - 大纲的模块划分：光信道特性（1–2 讲）→ 光器件（3 讲）→ 接收机分析（4 讲）→ 接收机电路（5–6 讲）→ 发送机分析（7 讲）→ 发送机电路（8–11 讲）→ 激光源（12 讲）→ RF 光子学与光子 NoC（13–14 讲）。
    - 第 13 讲的公式在 PDF 抽取时几乎全乱，凡是我没能可靠还原的都写明了，请对照原讲义。
    - 我补的计算或解释标了"（笔者）"。图、眼图、版图照片没有复现。
    - 和 [ECEN 720 高速链路](../ecen720-high-speed-links/index.md) 第 16 讲（光收发器）有重叠，但本课在**接收机电路**（TIA、限幅放大器）和**调制器驱动**上深得多。

## 课程定位

讲高速**光**互连的信道、器件、收发电路和控制回路。与 ECEN 720 的关系：720 是电链路为主、光只是最后一讲；本课是光链路为主，电路部分深入到 TIA 的噪声分析、限幅放大器的带宽扩展以及各种调制器的驱动电路。

课程目标（大纲原文概括）：

1. 理解高速光信道的特性、建模、测量和通信技术；
2. 理解驱动器、接收器、时钟和控制等光互连电路的设计指标与实现；
3. 会用建模工具做光链路系统设计；
4. 了解实现光串行链路标准的挑战和几种架构。

## 讲次目录

| 讲 | 主题 |
|---|---|
| [1](lec01-introduction.md) | 课程介绍、电链路与光链路对比、光器件概览与集成方式 |
| [2](lec02-optical-channels.md) | 光信道：光纤、损耗与色散、非线性、硅光波导、链路预算 |
| [3](lec03-photodetectors.md) | 光电探测器：p-i-n、APD、光前置放大 |
| [4](lec04-rx-analysis.md) | 接收机分析：BER、灵敏度、Personick 积分、功率代价、带宽、均衡、抖动、FEC |
| [5](lec05-tias.md) | 跨阻放大器（TIA） |
| [6](lec06-limiting-amplifiers.md) | 限幅放大器（LA） |
| [7](lec07-tx-analysis.md) | 发送机分析：调制方式、消光比、线宽与色散限制 |
| [8](lec08-vcsel-tx.md) | VCSEL 发送机 |
| [9](lec09-mzm-tx.md) | 马赫-曾德尔调制器（MZM）发送机 |
| [10](lec10-eam-tx.md) | 电吸收调制器（EAM）发送机 |
| [11](lec11-rrm-tx.md) | 环形谐振调制器（RRM）发送机 |
| [12](lec12-laser-sources.md) | 激光源：FP、DFB、混合硅激光器、光频梳、微环激光器发送机 |
| [13](lec13-microwave-photonics.md) | 基于监测的微波光子自动调谐系统 |
| [14](lec14-linear-mzm-driver.md) | 带线性化的模拟 MZM 驱动器 |

第一次考试覆盖到第 6 讲，第二次覆盖到第 12 讲。

## 考核方式（2024 年 ECEN 721 版）

| 项目 | 占比 | 说明 |
|---|---|---|
| 两次期中考试 | 50% | 各 25%，闭卷，可带一张双面 8.5×11 手写纸；无期末 |
| 作业 | 25% | 用 Cadence 90 nm 模型；可讨论但独立完成 |
| 期末项目 | 25% | 1–3 人一组，需要报告和 PPT 演示 |

## 和本站其他笔记的关系

- 前置：[EE273 数字系统工程](../ee273-digital-systems-engineering/index.md)（信号完整性基础）与 [ECEN 720](../ecen720-high-speed-links/index.md)（高速链路电路）。
- 器件与封装层面的全景见[芯片间互联技术概览](../chip-interconnect/chip-interconnect-overview.md)。
