# 第 13 讲 LNA 设计实例与新技术

> [原讲义 PDF](https://ocw.mit.edu/courses/6-776-high-speed-communication-circuits-spring-2005/resources/lec13/) · 公式按标准形式补写

本讲把第 12 讲的设计例子做完，然后介绍近期的 LNA 技术。讲义前几页（设计实例、偏置点、重新设计、负载与增益设定）的内容已并入 [第 12 讲](lec12-lna.md)，这里是新增部分。

## 13.1 重新设计的结论

- 从 $V_{gs}$ = 1 V 的偏置点出发（该点器件已进入速度饱和），分两步改：
    1. 降低电流密度 $I_{den}$（例如到 100 μA/μm），重新计算 $g_m/g_{do}$ 和 $f_t$，重画噪声因子缩放系数-Q 曲线；
    2. 把 Q 从 1.4 提高到 6。
- 仅提高 Q 这一项就把功耗降到原来的 **1/4 以下**；与降低电流密度合起来接近 **1/8**。
- 更新元件值（$R_s$ = 50 Ω、Q = 6、$f_o$ = 1.8 GHz、$f_t$ = 42.8 GHz）。

## 13.2 近期 CMOS LNA 技术

### 电流复用（current reuse）提高 $g_m$

- 考虑用电流复用来在给定电流下提高 $g_m$：同一个电流既流过 NMOS 又流过 PMOS，两者的跨导都贡献给输入（Karanicolas，"A 2.7 V 900-MHz CMOS LNA and Mixer"）。
- **偏置**：PMOS 用电流镜偏置；调整 NMOS 的电流与 PMOS 电流匹配。

### 从输出到晶体管的反馈

- 另一种近期做法：从输出反馈到晶体管的（源极/基极），多一个自由度；负反馈用来同时调节输入匹配和增益（Rossi 等，"A 2.5 dB NF Direct-Conversion Receiver Front-End for HiperLAN2/IEEE802.11a"，ISSCC）。

### 宽带 LNA 的新做法

- 用多阶 LC 滤波器（梯形网络）作输入匹配，在很宽的频带内实现匹配：
    - Bevilacqua 等，"An Ultra-Wideband CMOS LNA for 3.1 to 10.6 GHz Wireless Receivers"，ISSCC 2004；
    - Ismail 等，"A 3 to 10 GHz LNA Using a Wideband LC-ladder Matching Network"，ISSCC 2004。

### $g_m$ 提升以改善噪声系数

- 问题：放大器会引入噪声和功耗。怎样在**不增加噪声**的前提下提升 $g_m$？
- **用变压器做 $g_m$ 提升**：升压变压器给栅极和源极提供相差 180° 的电压，于是等效跨导提升 n 倍（Xiaoyong Li 等，"Low-Power gm-boosted LNA and VCO Circuits in 0.18 μm CMOS"，ISSCC 2005）。

## 13.3 重新审视中和

- 中和的问题：输出摆幅（尾电流上多一个压降）。
- **能不能用电感把 $C_{gd}$ 调谐掉？** 概念上可以用串联电感 L 把 $C_{gd}$ 调掉；需要在输入输出之间串一个大电容 $C_{BIG}$ 阻断直流——但 $C_{BIG}$ 的下极板寄生电容又会带来问题（Cassan 等，"A 1-V Transformer-Feedback Low-Noise Amplifier for 5-GHz Wireless LAN in 0.18 μm CMOS"，JSSC 2003）。

### 用变压器反馈做中和

- **没有直流压降**：可以在低电源电压下工作；
- 用电感退化实现功率匹配；
- $C_{gd}$ 与 $C_{gs}$ 的匹配比 $C_{gd}$ 与 $C_N$ 的匹配更好做。
- 讲义给出差分实现（同一篇 Cassan 论文）。

## 13.4 其他近期 LNA 结构

- **差分输出 LNA**：为平衡混频器提供差分输出（例如带 5 dBm 带外 IIP3、2.0 dB NF 的设计，ISSCC 2005）。
- **可调增益 LNA**：通过在共源共栅级分流输出电流来调节增益（H. Darabi 等，"A Fully Integrated SoC for 802.11b in 0.18 μm CMOS"，ISSCC 2005）。
