# MIT 6.776 高速通信电路（High Speed Communication Circuits）课程笔记

- **课程**：MIT 6.776 High Speed Communication Circuits，研究生课，2005 年春季
- **主讲**：Hae-Seung Lee、Michael H. Perrott
- **教材**：Thomas H. Lee，*The Design of CMOS Radio-Frequency Integrated Circuits*（必读）；参考 Behzad Razavi，*RF Microelectronics*
- **讲义来源**：[MIT OpenCourseWare 课程页](https://ocw.mit.edu/courses/6-776-high-speed-communication-circuits-spring-2005/)（[讲义列表](https://ocw.mit.edu/courses/6-776-high-speed-communication-circuits-spring-2005/pages/lecture-notes/)），以 CC BY-NC-SA 协议公开

!!! note "关于这份笔记"
    - 按**原讲义的讲次和幻灯片标题**整理，是中文概括，不是逐字翻译。
    - 这份讲义的公式大多是用公式编辑器嵌在幻灯片里的，PDF 抽取文字时几乎全部乱码，**能看清的只有每页标题和文字要点**。笔记里的公式是按 Lee 教材中的标准形式补写的，凡是这样补写的都尽量写明；数值例子能从文字里读出来的才照录。
    - OCW 只公开了 21 讲讲义：第 19 讲（其他类别功放、功放调制）、第 20 讲（功放线性化、自适应偏置）、第 24 讲（高级 RF 专题）、第 25 讲（客座报告：RF 收发器设计实例）**没有讲义**，这里只在目录中列出。
    - 第 5 讲在 OCW 上的资源名叫 `lec5-1`。

## 课程定位

这是一门**无线 RF 电路**课，和前面几门高速链路课互补：

- 与 [EE273](../ee273-digital-systems-engineering/index.md)、[ECEN 720](../ecen720-high-speed-links/index.md) 共享传输线、宽带放大器、PLL 这些基础；
- 但侧重点是窄带无线收发机：调制方式、收发机架构、S 参数与 Smith 圆图、LNA、混频器、VCO 相位噪声、功率放大器、小数分频频率合成器。

## 讲次目录

| 讲 | 主题 | 作业/考核节点 |
|---|---|---|
| [1](lec01-communication-systems.md) | 通信系统概览：调制与多址 | |
| [2](lec02-transceiver-architectures.md) | 收发机架构 | 作业 1 发布 |
| [3](lec03-transmission-lines.md) | 波导与传输线 | |
| [4](lec04-sparameters-impedance-transformers.md) | S 参数与阻抗变换器 | |
| [5](lec05-smith-chart.md) | 广义反射系数与 Smith 圆图 | 作业 1 截止、作业 2 发布 |
| [6](lec06-mos-passives-gbw.md) | MOS 管、无源器件、宽带放大器的增益带宽问题 | |
| [7](lec07-broadband-amplifiers.md) | 高频宽带放大器 | 作业 2 截止、作业 3 发布 |
| [8](lec08-broadband-amplifiers-cont.md) | 宽带放大器（续） | |
| [9](lec09-enhancement-narrowband.md) | 宽带放大器的增强技术、窄带放大器 | 作业 3 截止 |
| [10](lec10-noise-modeling.md) | 放大器中的噪声建模 | |
| [11](lec11-noise-figure-nonlinearity.md) | 噪声系数与放大器非线性 | 作业 4 发布 |
| [12](lec12-lna.md) | 低噪声放大器（LNA） | 实验发布 |
| [13](lec13-lna-examples.md) | LNA 设计实例与新技术 | 作业 4 截止 |
| [14](lec14-vco.md) | 压控振荡器（VCO） | 作业 5 发布 |
| [15](lec15-vco-examples-mixers.md) | VCO 实例与混频器 | |
| [16](lec16-mixers.md) | 混频器（续） | 作业 5 截止、小测验 |
| [17](lec17-vco-noise.md) | VCO 中的噪声 | |
| [18](lec18-power-amplifiers.md) | 功率放大器基础 | 项目发布、实验报告截止 |
| 19 | 其他类别功放、功放调制（**无讲义**） | |
| 20 | 功放线性化、自适应偏置（**无讲义**） | |
| [21](lec21-pll-integer-n.md) | 锁相环与整数分频频率合成器概览 | 作业 6 发布 |
| [22](lec22-synthesizer-noise.md) | 整数/小数分频合成器的噪声 | |
| [23](lec23-fractional-n-design.md) | 小数分频合成器设计与带宽扩展 | 作业 6 截止 |
| 24 | 高级 RF 专题（**无讲义**） | |
| 25 | RF 收发器设计实例（客座报告，**无讲义**） | 项目截止 |

## 课程形式与考核

- 每周两次 1.5 小时的课；7 次作业（两人一组交一份）；
- 一个**实验**，内容是 RF 放大器，第 18 讲时交；
- 期末**项目**：设计并仿真一个无线应用的 CMOS 功率放大器，第 25 讲时交；
- 第 16 讲之后有一次小测验，没有期末考试。

| 项目 | 占比 |
|---|---|
| 小测验 | 35% |
| 实验 | 25% |
| 期末项目 | 25% |
| 作业 | 15% |

先修课：MIT 6.301 固态电路（或同等）。

## 和本站其他笔记的关系

- 传输线、反射：对照 [EE273 第 2 讲](../ee273-digital-systems-engineering/lec02-wires.md)、[ECEN 720 第 2 讲](../ecen720-high-speed-links/lec02-channels.md)。
- 宽带放大器的峰化与多级级联：对照 [ECEN 689 第 6 讲](../ecen689-optical-interconnects/lec06-limiting-amplifiers.md)。
- PLL 与相位噪声：对照 [ECEN 720 第 11 讲](../ecen720-high-speed-links/lec11-clocking-plls.md)。
