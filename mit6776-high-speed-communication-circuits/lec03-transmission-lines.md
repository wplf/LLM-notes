# 第 3 讲 波导与传输线

> 2005-02-08 · [原讲义 PDF](https://ocw.mit.edu/courses/6-776-high-speed-communication-circuits-spring-2005/resources/lec3/)

本讲从麦克斯韦方程出发推出 TEM 传输线方程。讲义的推导公式全部是图片，下面按标准推导补写。

## 3.1 自由空间中的麦克斯韦方程

$$\nabla\times E = -\mu\frac{\partial H}{\partial t}\quad(1),\qquad \nabla\times H = \varepsilon\frac{\partial E}{\partial t}\quad(2),\qquad \nabla\cdot E = 0\quad(3)$$

对 (1) 取旋度，代入 (2)，再用矢量恒等式 $\nabla\times\nabla\times E = \nabla(\nabla\cdot E) - \nabla^2E$ 和 (3)：

$$\nabla^2E - \mu\varepsilon\frac{\partial^2E}{\partial t^2} = 0,\qquad \nabla^2H - \mu\varepsilon\frac{\partial^2H}{\partial t^2} = 0$$

## 3.2 一维解与传播速度

- 为简单起见只考虑 z 方向：$\dfrac{\partial^2E}{\partial z^2} - \mu\varepsilon\dfrac{\partial^2E}{\partial t^2} = 0$。
- 任何形如 $f(z \pm vt)$ 的函数都满足这个方程，其中 $v = 1/\sqrt{\mu\varepsilon}$。
- **传播速度**：函数 $f$ 同时是时间和位置的函数；"骑"在波的某一点上，即令 $z \pm vt$ = 常数，得 $dz/dt = \mp v$。解沿 +z 或 −z 方向以速度 $v$ 传播。

## 3.3 正弦稳态

解的形式为 $Ae^{j(\omega t \pm kz)}$，其中 $k = \omega/v = \omega\sqrt{\mu\varepsilon}$。

## 3.4 假设与求解

- **方向**：E 场在 x 方向，H 场在 y 方向，都沿 z 方向传播。
- 自由空间中如此；对传输线（**TEM 模式**），两块平行板之间的场也满足这个假设。
- 场只随时间和 z 变化。在这些假设下计算麦克斯韦方程中的旋度，得到：

$$\frac{\partial E_x}{\partial z} = -\mu\frac{\partial H_y}{\partial t},\qquad \frac{\partial H_y}{\partial z} = -\varepsilon\frac{\partial E_x}{\partial t}$$

由此得到波阻抗 $\eta = E_x/H_y = \sqrt{\mu/\varepsilon}$。

### 自由空间的数值

- $\mu_0 = 4\pi\times10^{-7}$ H/m，$\varepsilon_0 \approx 8.85\times10^{-12}$ F/m；
- 阻抗 $\eta_0 = \sqrt{\mu_0/\varepsilon_0} \approx 377\ \Omega$；
- 传播速度 $c \approx 3\times10^8$ m/s；
- 30 GHz 信号的波长为 1 cm。

## 3.5 电压、电流与平行板波导

- 平行板（宽 a、间距 b）之间的 E 场和 H 场受极板影响。
- **电流与 H 场**：交流电流沿波导流动，影响 H 场；一块板的磁通与另一块板的磁通相互作用；近似认为 H 场均匀、并且只局限在两板之间：$I = H_y\,a$。
- **电压与 E 场**：同样近似认为 E 场均匀、只局限在两板之间：$V = E_x\,b$。

## 3.6 传输线（TEM）的波动方程

代回麦克斯韦方程，得到用电压电流表示的形式：

$$\frac{\partial V}{\partial z} = -L\frac{\partial I}{\partial t},\qquad \frac{\partial I}{\partial z} = -C\frac{\partial V}{\partial t}$$

其中单位长度的电感和电容为 $L = \mu b/a$，$C = \varepsilon a/b$。合并得波动方程：

$$\frac{\partial^2V}{\partial z^2} = LC\frac{\partial^2V}{\partial t^2}$$

**特性阻抗**：$Z_0 = \sqrt{L/C} = \eta\,b/a$。

### 与现实世界联系

- 和用相量做正弦分析一样，解是复数；取实部得到实际解，例如 $V(z,t) = |A|\cos(\omega t - kz + \phi)$。
- 余弦波同时是时间和位置的函数；"骑"在波的某一点上可以算出传播速度 $v = \omega/k = 1/\sqrt{LC} = 1/\sqrt{\mu\varepsilon}$。

## 3.7 集成电路中的数值

- 阻抗取决于几何形状和材料；
- **传播速度与几何形状无关、只取决于材料**：$v = c/\sqrt{\varepsilon_r}$；
- SiO₂（$\varepsilon_r \approx 3.9$）中 30 GHz 信号的波长约 $1\,\text{cm}/\sqrt{3.9} \approx 5$ mm（笔者计算）。

## 3.8 LC 网络类比

- 传输线（TEM）可以类比为无限多节 LC 的梯形网络。
- 计算输入阻抗：对无限长梯形网络，$Z_{in} = sL + (1/sC \parallel Z_{in})$，在 L、C 无穷小的极限下得到 $Z_{in} = \sqrt{L/C}$。

**集总 LC 与传输线有什么不同**：

- 传输线里 L 和 C 是无穷小的，所以 $Z_{in} = \sqrt{L/C}$ **在所有频率都成立**；
- 集总 LC 的 L、C 是有限值，只在 $\omega \ll 1/\sqrt{LC}$ 的有限频率范围内近似成立。

## 3.9 有损传输线

- 实际传输线的导体和介质都有损耗，在 LC 模型中加入串联电阻 R 和并联电导 G 来建模。
- 损耗对沿线传播的信号有两个影响：**衰减**和**色散**（即带宽下降）。
- 分析见教材（以及本站 [EE273 第 2 讲](../ee273-digital-systems-engineering/lec02-wires.md)）。
