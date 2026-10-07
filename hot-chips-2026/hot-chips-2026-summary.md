# Hot Chips 2026 报告汇总

> 会议：Hot Chips 2026（2026-08-23 至 08-25，Stanford）。日程页：<https://hc2026.hotchips.org/>
>
> 整理日期：2026-10-05

## 说明

- Hot Chips 不公开官方摘要，幻灯片 PDF 需要参会账号（HTTP 401）。下面的摘要**不是官方摘要**，是根据公开的现场报道和论文整理的。
- 48 个报告中：37 个找到了针对该报告的报道，2 个 poster 找到了 arXiv 论文摘要，1 个 poster 只有背景新闻，8 个 poster 没找到公开资料。
- 主要来源是 ServeTheHome 的 34 篇现场报道（现场速记，原文自称可能有笔误），另有 The Next Platform、韩国每日经济（mk.co.kr）、BigGo Finance、ChosunBiz、TechSpot 和 arXiv。
- 数字都是厂商自述或记者转述，没有核对原始幻灯片。

## 数量

| 类别 | 数量 | 找到资料 |
|---|---|---|
| 正会技术报告（9 个 session） | 26 | 26（BOS Eagle-N 只有简讯） |
| Keynote | 1 | 1 |
| Tutorial | 10 | 10 |
| Poster | 11 | 2 篇论文摘要，1 篇背景新闻 |
| **合计** | **48** | |

另有 4 个非技术环节没有计入：两个开场致辞、TCMM 颁奖、闭幕致辞。

## 目录

- [几条贯穿全会的主线](#几条贯穿全会的主线)
- [CPU 1](#cpu-1)
- [CPU 2](#cpu-2)
- [Keynote](#keynote)
- [Automotive](#automotive)
- [GPU](#gpu)
- [FPGA](#fpga)
- [Memory](#memory)
- [Networking & Interconnect](#networking--interconnect)
- [AI 1](#ai-1)
- [AI 2](#ai-2)
- [Tutorial 1：Memory technology](#tutorial-1memory-technology)
- [Tutorial 2：RISC-V](#tutorial-2risc-v)
- [Poster](#poster)
- [来源](#来源)

## 几条贯穿全会的主线

这一节是我读完各篇报道后的归纳，不是任何一个报告的原话。

- **decode 受内存带宽限制**：SambaNova、d-Matrix、NVIDIA LPU、Cerebras、OpenAI 都从这一点出发，分歧在于用什么内存（SRAM、HBM4、3D DRAM、晶圆级 SRAM）。
- **prefill/decode 是否拆开**：NVIDIA（GPU + LPU）、SambaNova（H200 + SN50）、Cerebras（WSE + MI455X）选择异构拆分；OpenAI Jalapeño 明确反对，用一颗均衡芯片按阶段关断模块。
- **FP4 / MXFP4 成为标配**：Meta、Microsoft、OpenAI、AMD、Intel、IBM、Google 的新芯片都支持。
- **确定性、编译期调度的数据流架构**：Groq LPU、Microsoft MAIA 200、Waymo carTPU、SambaNova RDU 都把调度从硬件搬到编译器。
- **机架和"AI 工厂"取代单芯片成为设计单位**：NVIDIA Rubin、AMD Helios、Cerebras CS-4、Google TPU 8t superpod。
- **HBM base die 逻辑化与 3D 堆叠**：Samsung（cHBM、zHBM）、SK hynix（混合键合）、d-Matrix（逻辑叠 DRAM）、Cerebras CS-6（晶圆叠 DRAM）。
- **小芯片与 UCIe 下沉**：从服务器（Arm AGI、Diamond Rapids、Monaka、Vera）到低价笔记本（Wildcat Lake）和车载（Eagle-N）。

## CPU 1

### 1. IBM：未来 IBM Z / LinuxONE 处理器与 AI 推理加速芯片组

- 处理器：2nm，11 核，5.7 GHz 以上。同一个核原生执行 z/Architecture 和 Arm AArch64（v9.3，含 SVE/SVE2），是硬件实现而非翻译，线程在两种指令集间切换是纳秒级。
- 配套：每核 36 MB L2，片上有 DPU 以及 AI、压缩、加密、排序加速块，这些加速器对 Arm Linux 以平台设备形式暴露。可用性目标 99.999999%。
- AI 加速器（第二代）：16 个 AI 核加 1 个冗余核，支持 FP4/MXFP4，96 GB HBM3e，带宽约 4 TB/s（称为现款的约 20 倍），PCIe Gen6。

### 2. Intel：Core Series 3（Wildcat Lake）

- 定位：Panther Lake 的低价版本，沿用最新的 CPU 核和 Xe3 GPU，工艺从 Intel 7 直接跳到 18A。
- 主题是成本取舍：只用 2 颗 die，放弃 Foveros，改用有机基板多芯片封装，用 UCIe 做 die 间互连，这是 Intel 首次这样做。
- 裁剪：减少 P 核、NPU、GPU、缓存和 PCIe 通道，去掉光追和摄像头 PHY，I/O die 面积省约 15%。
- 工程细节：UCIe 链路限速 8 GT/s 以免去重传和 FEC；显示数据跨 die 做缓冲以便进低功耗态；约 29% 的计算 die 可通过降配 SKU 回收。已有 70 多个设计中标。

### 3. NVIDIA：Vera CPU

- 规格：88 个自研 Olympus Arm 核，强调单线程性能而非核数。10 宽解码，采用静态划分的"空间多线程"以减少线程互扰。
- 封装：6 颗 die，计算核是单片，内存和 I/O 拆成小芯片。8 个 LPDDR5X 控制器，96 条 PCIe/CXL 通道，用 NVLink-C2C 连 Rubin GPU 或另一颗 Vera。
- 论点：智能体工作流需要高单线程性能和确定性延迟。在 NVIDIA 挑选的 SPEC CPU 2026 子集上，智能体类约 1.8 倍、数据处理类约 1.5 倍（报道未写明对比基准）。支持全机架机密计算。

## CPU 2

### 4. Fujitsu：FUJITSU-MONAKA

- 规格：Armv9.3-A，144 核，256-bit SVE2，12 通道 DDR5，支持双路。
- 封装：3D 小芯片。核心 die 用 TSMC N2P，面积占比不到 30%；SRAM 和 I/O die 用 N5；核心 die 混合键合叠在 SRAM die 上。
- 卖点：超低电压运行，称比同类设计低约 30%。另有浮点寄存器缓存、窄向量屏蔽等省电技术，支持 Arm 机密计算架构。
- 产品：两个 SKU，500 W（2.9 GHz）和 350 W（2.1 GHz），2027 年上市。后续 Monaka-X 计划用 1.4nm 并支持 NVLink Fusion。

### 5. Arm：Arm AGI 服务器 SoC

- 意义：Arm 第一颗自己出售的商用服务器 CPU。
- 规格：两颗 N3P 小芯片，每颗 70 个 Neoverse V3 核，最多 136 核可用。最高 3.7 GHz，300 W。
- 内存和 I/O：12 通道 DDR5-8800，约 845 GB/s；96 条 PCIe Gen6 通道，支持 CXL 3.0。
- 互连：die 间用 UCIe，每方向约 1 TB/s，带宽高于内存带宽，目标是让双 die 表现得像单片。

### 6. Intel：Diamond Rapids（下一代 Xeon）

- 架构：以"Fabric Hub"集中内存和 I/O，计算模块挂在上面。每个计算模块由若干 16 核小芯片组成，用 Foveros 3D 混合键合叠在带共享 LLC 的 base tile 上。
- 旗舰配置：4 个计算模块，256 核，1.28 GB LLC。16 通道内存（DDR5-8000 或 MRDIMM-12800），带宽 1.6 TB/s；128 条 PCIe Gen6/CXL 3/UPI 通道。
- 其他：Intel 18A-P 工艺；新增 16 个通用寄存器（共 32 个）和三操作数指令；一致性目录从 DRAM 移到片上 snoop filter。报道称平台在 2027 年。

## Keynote

### 7. Waymo：Compute in Motion: Challenges of Autonomous Driving（Daniel Rosenband）

- 立场：目标是事故远少于人类的"超人司机"，所以需要激光雷达、雷达、摄像头多传感器加自研芯片。例子是凤凰城沙尘暴中激光雷达看到了摄像头看不到的行人。
- 车载和数据中心的差别：必须毫秒级响应，只能靠一两颗芯片；车载液冷的液温可达 60°C。
- 架构："快思考/慢思考"，快速的传感器融合编码器加较慢的驾驶视觉语言模型。
- 数据和愿景：累计全自动驾驶超过 2 亿英里。愿景是车内跑 1 万亿参数模型，并把"披萨盒"大小的车载计算机缩到笔记本大小。
- 两处报道不一致：事故率一家写约为人类的 1/3，另一家写 1/13；芯片算力媒体写"超过 1000 TOPS"，而技术报告的报道是 160 TOPS（见第 9 条）。

## Automotive

### 8. BOS Semiconductors：Eagle-N

只找到简讯，没有技术细节报道。Eagle-N 是面向 ADAS、自动驾驶和车内生成式 AI 的小芯片架构车载 AI 加速器，Samsung 5nm，基于 Tenstorrent 技术，250 TOPS。公司称小芯片可把制造成本降低约一半，正与德国和中国车企做评估。

### 9. Waymo：Sensor Fusion Processor

- 用途：自研车载芯片，专门跑基础模型栈里的传感器融合编码器，已装在第六代车辆上。
- 规格：N5，208 mm²，45×45 mm 封装，功耗低于 75 W，封装内 LPDDR5x（273 GB/s），PCIe Gen5 x8，25G 以太网。算力 160 TOPS（INT8）/ 80 TFLOPS（FP16），64 MB 片上 SRAM。
- 组成：自研部分是 carTPU 阵列、ISP、编解码和 MIPI 接入；两颗 GPU 和接口 IP 是第三方的；没有 DSP。
- 执行模型：确定性数据流，静态形状的"巨指令"，无缓存无分支；编译器提前把整个模型编成 mega-kernel 并切片放进 SRAM。
- 传感器链路：自研 HDR ISP 和去马赛克、多帧时域降噪；雷达和激光雷达的 FFT、点云处理在 GPU 上做。

## GPU

### 10. NVIDIA：Rubin GPU

- 讲法：以整座"AI 工厂"而非单芯片为单位。优化目标是每瓦 token 数、首 token 时间和平均无中断时间。
- 新特性：硬件支持的自适应稀疏（2:4 格式，作用于整个 transformer 块），称多数模型无需改动。稀疏注意力让 SoftMax 等运算快约 2 倍。GPU 间同步改用 counted-write 以降低 NVLink 延迟。
- 互连：NVLink 6，72 颗 GPU 一个域，每颗 3.6 TB/s 全互联。
- 机架：45°C 温水液冷，800 VDC，无线缆无风扇托盘。功率平滑使峰值降 13%，称每瓦配额可多放 40% GPU。支持不停机健康检查。
- 性能：称在长上下文智能体基准上，每兆瓦 token 数是 GB300 的 10–30 倍。

### 11. AMD：Instinct MI400 系列 GPU 架构

- 芯片：MI455X 由 8 颗 N2 计算 die 加 N3P 的 fabric、cache、I/O die 组成，3D 混合键合加 CoWoS-L。12 个 HBM4 堆叠，432 GB，23.3 TB/s。
- 算力：峰值 MXFP4 40.26 PFLOPS，称最高为 MI355X 的 4 倍。
- 改进方向：更大的内存和缓存、更快的计算、更少的数据搬运（专用 DMA 引擎与计算并行）。
- 实测对比 MI355X：FP4 算力 3.3 倍，scale-up 带宽 3.5 倍，能效 2.4 倍。软件上 ROCm 提供面向 AI 编程助手的"AI Skills"。

### 12. AMD：MI400 系统架构（Helios 机架）

- 组成：Helios 机架由 EPYC Venice（96 核）、MI455X 和 Pensando Vulcano 800G AI NIC 协同设计。
- 规模：72 颗 GPU，31 TB HBM4，2.9 EFLOPS。18 个计算托盘（每个 4 颗 GPU 加 1 颗 CPU），6 个交换托盘，液冷。
- 互连：scale-up 用 UALoE，建在开放以太网标准上，每颗 GPU 每方向 1.8 TB/s。整柜是共享内存 load/store 模型，由三节点 Fabric Manager 管理。
- 可靠性和隔离：演示了单链路到整个交换托盘失效时的重平衡；可划分相互隔离的虚拟 pod；支持机架级机密计算。
- NIC：Vulcano 是 P4 可编程的，支持 MRC 等新传输和拥塞控制协议。

### 13. Intel：Crescent Island

- 定位：面向企业数据中心智能体推理的 GPU，350 W，风冷，PCIe 卡。主打每瓦 token 数和大内存。
- 规格：160 GB LPDDR5x，合作伙伴版本最高 480 GB。Xe3p 架构，32 个 Xe 核，256 个第三代 XMX 矩阵引擎，支持 FP4/MXFP4，32 MB 统一 L2。
- 论点：模型权重容量需求和每 token 读取量已经脱钩，所以大容量 LPDDR 加 PCIe 交换扩展有空间；decode 空闲的算力可用于推测解码。
- 缺口：报道指出 Intel 没有公布内存带宽。

## FPGA

### 14. AMD：Versal Premium Gen2

- 定位：面向物理 AI、数据中心和关键任务系统的自适应 SoC，主线是安全。
- 安全：硬件信任根、内存加密和防重放、防侧信道、后量子密码。
- 封装内内存：LPDDR5X 封装内集成，面积省约 60%。
- 接口：PCIe Gen6 和 CXL 3.1，128G 收发器为 PCIe Gen7 / CXL 4.0 预留；100G/400G/600G 以太网。
- 报道者评价：用例多，规格细节少。

### 15. AMD：Versal RF 系列

- 定位：宽带射频自适应 SoC。ADC 最高 32 GSPS，射频带宽 18 GHz，14-bit。称 DSP 算力最高为上一代的 19 倍。
- 做法：把 FFT/iFFT、信道化器、LDPC 解码器等做成硬 IP，硬 FFT 比软实现功耗低约 87%。加上 AI Engine 阵列（最多 126 个 tile）和可编程逻辑。
- 集成度：一颗芯片相当于 4 颗 Virtex UltraScale+ VU13P 的 DSP 算力。
- 应用：国防、测试测量、通信和量子比特控制。支持 UCIe 外接小芯片。

## Memory

### 16. Samsung：LPDDR5X-PIM

- 定位：首个基于 LPDDR 的存内计算产品，作为比 HBM 更便宜、更省电的推理方案。
- 结构：DRAM bank 中放 16 个 PIM 块（并行 MAC 树加 ALU），支持 15 种精度组合。JEDEC 标准封装，可用常规 DRAM 控制器。
- 带宽：PIM 内部 614 GB/s，是常规 DRAM 接口的 8 倍。
- 实测：在自家边缘 AI SoC 上跑 Llama-3.1-8B，耗时 5.4 秒对 12.3 秒，输出 81.3 对 27.0 tokens/s。LPDDR6-PIM 正在走 JEDEC 标准化。

### 17. XCENA + Samsung：MX1 CXL 计算内存器件

- 器件：CXL Type 3，Samsung 4nm，三合一。
  - 内存扩展：4 通道 DDR5，最高 2 TB。
  - "Infinite Memory"：把 SSD 以字节可寻址的 CXL 内存形式暴露，DRAM 做缓存。
  - 近内存计算：3072 个简单顺序执行的 RISC-V 核加向量引擎。
- 软件：主机和器件共享虚拟地址空间，提供 MapReduce 式运行时 PXL。
- XCENA 的结果：吞吐最高为"主机经 CXL 访问"的 4.7 倍，功耗约四分之一。
- Samsung 的结果：RAG 向量检索 QPS 为 64 倍；LLM 解码把未命中的注意力计算下推到器件，10 万上下文时吞吐为 3.35 倍。

## Networking & Interconnect

### 18. Broadcom：Thor Ultra

- 规格：800GbE 网卡芯片，5nm，24 亿晶体管，40–42 W。PCIe Gen6 x16，8×100G SerDes。
- 核心是增强 RoCE：逐包多路径喷洒（最多 8 个平面）、乱序放置、选择性 ACK/NACK 重传、基于接收端信用的可编程拥塞控制。
- 实测：TCP 791 Gbps；RDMA 单向 781 Gbps、双向 1558 Gbps；集合通信多数操作达到线速的 96% 以上。

### 19. NVIDIA：BlueField-4

- 规格：64 个 Neoverse V2 核的 Grace CPU 加 ConnectX-9 800G，PCIe Gen6。
- 定位：每台 Vera Rubin 系统标配的"服务器前面的服务器"，负责租户隔离、零信任、遥测和存储，不再是可选插卡。
- 新概念：scale-in 网络，即主机与数据中心之间的流量。每个计算托盘聚合 7 Tb/s，由 DPU 统一管理所有 ConnectX-9。
- 数字：NVMe-oF 用 16 核达到 2000 万 IOPS；称不用 DPU 的方案功耗高 4 倍。

### 20. NVIDIA：Spectrum-X 多平面网络架构

- 框架：AI 工厂分五种专用网络，scale-up、scale-out、scale-in、scale-across、context。
- 多平面：网卡的 1.6T 拆成 8×200G，分别连到不同交换机。规模从多轨的 8 千颗 GPU 扩到 51.2 万颗，称交换机少 1.7 倍。
- 故障表现：2.68 ms 检测，100 ms 恢复，保持 90% 带宽。
- 其他：共封装光学已量产；NVLink Fusion 接入第三方 XPU；DSX 软件用于上线前仿真验证。

## AI 1

### 21. Meta：MTIA 自研 AI 芯片

- MTIA 300：面向推荐模型训练，72 个处理单元，216 GB HBM3e，称与 GPU 性能持平、TCO 有竞争力。
- MTIA 400：转向更通用的推理，兼顾推荐和生成式 AI。
  - 封装：2 颗计算小芯片加 SoC 和网络小芯片。
  - 计算：每颗计算小芯片 8×6 处理单元阵列加冗余行，每个单元含 2 个 RISC-V 核。硬件 MXFP4，12 PFLOPS（FP4）。
  - 内存和互连：8 个 HBM3e 堆叠，9.4 TB/s；以太网 scale-up，72 颗芯片一个域。
- 路线：后续 450 和 500 在开发中。

### 22. NVIDIA：LPU Accelerator（Groq 3 / LPX 机架）

- 定位：LPU 来自 Groq，用来补 GPU 在低延迟 decode 上的短板。
- 芯片：大量片上 SRAM 贴近计算；完全确定性执行，调度和路由都由编译器静态完成，没有硬件流控。
- 机架：256 颗 LPU，128 GB SRAM，聚合带宽 40 PB/s，315 PFLOPS（FP8）。单机架在 31B 模型上 decode 11,000 tokens/s。确定性还让功耗可预测，电压跌落减少 60%。
- 与 GPU 协同：prefill 和注意力在 GPU 上，decode 其余部分在 LPU 上，两边之间用 FPGA 做同步/异步桥。高交互率下每用户 token 速率最高提升 5 倍，代价是总吞吐效率下降。已纳入 CUDA。

### 23. Cerebras：晶圆级引擎的机架级架构

- 产品：CS-4 机架，基于 Nexus 平台，内含 3 片 WSE-3 Turbo。Turbo 的时钟频率翻倍。
- 对比 CS-3：token 速度 2 倍，每瓦 token 数 10 倍。
- 机械和供电：计算以可插拔"背包"形式装在机架后部，供电在前。垂直供电让 DC-DC 紧贴母线，降低电阻损耗。
- 互连：晶圆间直连，延迟低至 2 微秒，几乎不用线缆。
- 路线：CS-5 在 2027 年；CS-6 将首次在晶圆上堆叠 DRAM。

### 24. Microsoft：MAIA 200

- 规格：TSMC 3nm，750 W，1400 亿晶体管，6 个 HBM3e 堆叠（7 TB/s），约 10 PFLOPS（FP4），die 面积 820 mm²。
- 架构："软件定义数据流、本地数据访问"，数据流在编译期确定，执行确定性高。基本单元是 tile，含张量单元、向量处理器、控制处理器和 L1。
- 网络：自研 NIC 和协议，全以太网。只有 scale-up 没有 scale-out，示例是 128 个机架约 6000 颗芯片。
- 实测：GEMM 接近理论上限，AllReduce 约 1.3 TB/s。

## AI 2

### 25. SambaNova：Dataflow at Scale: the SN50 RDU

- 论点：智能体推理的时间主要花在 decode（DeepSeek V3 上占 97%），而 decode 受内存带宽限制。SambaNova 用"模型带宽利用率（MBU）"衡量，称 GPU 的 MBU 低，且随规模扩大而下降。
- 芯片：SN50 是第五代可重构数据流单元，由两颗满光罩逻辑 die 加 HBM 组成，没有独立 I/O die，仍用较旧的 HBM2e。算力约为 SN40 的 5 倍，片上是计算单元和存储单元的阵列，内存由软件管理。
- 组网：16 颗 RDU 装一个风冷机架。scale-up 用 800GbE，scale-out 用 400GbE；8 路全互联，经交换机扩到 64 和 512 路。
- 结果：256 颗时 MBU 仍有 45%，512 颗聚合模型带宽超过 350 TB/s。实际部署是 NVIDIA H200 做 prefill、SN50 做 decode；MiniMax M2.7 上超过 750 tokens/s。

### 26. Google：第八代 TPU 家族（TPU 8t 训练 + TPU 8i 推理）

- 变化：第一次在同一年推出训练和推理两颗芯片，原因是 MoE 和长上下文让两类需求分化。推理芯片反而更大（8 个 HBM 堆叠，训练芯片 6 个），因为推理每单位算力需要更多 HBM 和 SRAM。
- 8i：每两颗配一颗自研 Arm CPU Axion。网络从 3D Torus 换成 BoardFly 拓扑，最大跳数从 16 降到 7；集合通信在靠近网络的 I/O die 里完成。
- 8t：一个 superpod 有 9600 颗芯片、2 PB 共享 HBM、121 EFLOPS（FP4），性能功耗比约为上一代 Ironwood 的 2 倍。用光路交换（OCS）动态切片并绕过坏芯片；新的 Virgo 网络单域支持 13.4 万颗 TPU。
- 其他：空闲时做在线自检，光模块首次液冷，用 AI 辅助设计省功耗和面积。

### 27. OpenAI：You Can Just Build Things … Chips（Jalapeño）

- 产品：与 Broadcom 合作的自研推理 ASIC 和整机，从 RTL 到流片约 9 个月。时间线是 2024 年底架构概念、2025 年底流片、2026 年初跑通 Codex。
- 规格：单芯片 700 W，13.4 PFLOP/s（MXFP4），HBM4 带宽 15.4 TB/s、容量 216 GiB。128 颗组成低延迟本地域，经 Tomahawk6 两级 Clos 扩到 2048 颗。
- 设计取舍：不做 prefill/decode 异构机群，用一颗均衡芯片，按阶段关掉不用的模块，KV cache 留在本地。每个核配一片 HBM 切片，加专用低延迟集合通信网络。
- 对比：在 InferenceX 基准上对 GB200/GB300，称每千瓦吞吐高约 1.5–1.9 倍，端到端延迟低 1.7–3.6 倍。
- 方法：用内部模型和 XLS 硬件语言加速设计；编程模型（Gluon）面向 AI 自动搜索优化，AI 优化的注意力和 MoE kernel 比专家手写快 1.5–1.8 倍。

## Tutorial 1：Memory technology

### 28. Jim Handy（Objective Analysis）：Memory: Feeding AI's voracious hunger for data

内存市场综述。超大规模云厂商的 AI 资本开支造成 DRAM、HBM、NAND 需求冲击；这些产品出自同一批产线，HBM 挤占产能，带动 DDR 和 NAND 涨价，现货价约涨到 7 倍。内存是大宗商品，短缺时厂商优先卖给出价高的客户。HBM 买家排序是 NVIDIA、AMD、Broadcom。

### 29. Micron：Evolving memory architectures for AI

- 内存墙：加速器算力每两年约 3 倍，HBM 带宽每两年不到 2 倍。
- HBM 演进：HBM4 的 IO 从 1K 增到 2K，每 die 的 bank 数从 128 增到 256。
- 代价：同容量下 HBM3E 消耗的硅约为 DDR5 的 3 倍；封装内内存硅面积可超过 GPU die 的 8 倍。
- 后半部分：热膨胀失配带来的可靠性问题、两层 ECC、散热手段（液冷、混合键合）和封装趋势（更大的 CoWoS、玻璃基板、共封装光学）。

### 30. Samsung：HBM Base Die 的演进

- 起点：从 HBM4 起 base die 改用先进逻辑工艺（4nm），不再只是被动接口。
- 三阶段路线：
  1. 定制 HBM：用更小的 die-to-die 接口替换 PHY，把内存控制器从 XPU 搬到 base die，加入基于 SRAM 的修复和传感器自检。
  2. 扩展功能：从 base die 外接更多内存，放入处理单元分担 XPU 的计算。
  3. zHBM：XPU 与 DRAM 堆叠真正 3D 垂直集成，去掉 2.5D 中介层和 PHY；示例是配 1200 W GPU 可省约 100 W。
- 散热：提出 Heat Path Block，峰值温度降 35% 以上。

### 31. SK hynix：HBM 先进封装

- 结构和代际：HBM4 为 2048 个 IO、超过 2 TB/s、2 万多个 TSV，12 层量产，16 层在认证。
- 键合路线：TC-NCF 对比 MR-MUF 的取舍。16 层堆叠要在同样高度内把芯片厚度、间隙和凸点间距约减半。
- 混合键合：是 20 层以上堆叠的路径，凸点间距可小于 18 µm，散热更好。
- 其他：i-HBM 在发热的 PHY 区嵌入导热件，热阻降 30% 以上。系统集成中 HBM 现在最先组装；不同封装（CoWoS-S、CoWoS-L、EMIB）给 HBM 的应力不同。

### 32. d-Matrix + Meta：基于 3D DRAM 的生成式推理加速器（Raptor）

- 动机：SRAM 带宽高但容量小，HBM 容量大但带宽上限约 20 TB/s 且耗电。
- 方案：把 N4 逻辑 die 面对面叠在 3D DRAM die 上，垂直 IO 每 bit 能耗约为 HBM 的十分之一，目标带宽约 100 TB/s。
- 三个工程问题和解法：
  - bank 与数据宽度不整除：stream blocking，消除多取的浪费。
  - IO 功耗：stream flipping，每个数据单元加 1 bit 元数据，省 20% 翻转。
  - 高温和良率：ECC 与刷新策略，加上 bank chaining，用 72 个备用 bank 吸收故障。
- 宣称：每 mm² 带宽约为 HBM 方案的 20 倍；72 卡一柜可承载 1M 上下文的前沿模型，每用户约 1000 tokens/s。

### 33. Oxmiq Labs + PRAXMATI：HBF in AI Compute

- HBF（高带宽闪存）是什么：同成本下容量为 HBM 的 8–16 倍，带宽较低。
- 结论比较克制：HBF 是容量层，不是便宜版 HBM，每 GB 更便宜不等于每 token 更便宜。它只在带宽需求低的场景占优，比如小 batch 的大型 MoE 模型和稀疏注意力的长上下文。
- 仿真：72-GPU 机架、同成本下，HBF 换来约 14 倍容量、约 0.6 倍带宽。
- 限制和用法：读优化、写受限，85°C 下数据保持约 24 小时。提议在 vLLM 里把 MoE 专家权重和 KV cache 放 HBF，注意力权重和热数据放 HBM。

## Tutorial 2：RISC-V

### 34. SiFive（Krste Asanovic）：RISC-V 标准与采用进展

- 规范的模块化结构：基础 ISA、扩展、profile、平台标准。
- 内容：向量扩展（长度无关，一份二进制跑不同位宽）；矩阵扩展的几条路线；安全特性（Worlds、supervisor domains、CHERI 等）。
- profile：RVA20、RVA22、RVA23，其中 RVA23 强制要求向量和虚拟化；另有面向定制软件的 RVB23 和服务器平台规范。首批 RVA23 服务器芯片今年出现。
- 后半段是反驳常见批评：碎片化、扩展太多（RISC-V 约 200 个，AArch64 约 400 个，x86 约 800 个）、只是便宜、性能不行。

### 35. Canonical：企业级开源软件在 RISC-V 上的演进与 RVA23

- 做法：Ubuntu 给每个架构设基线，RISC-V 基线在 25.10 从 RVA20 升到 RVA23。
- 现状：约 95% 的软件包已在 RISC-V 上可用，但自动测试通过率约 55%（amd64 约 92%），部分原因是靠仿真构建，正在引入原生构建机。
- 其他：Kubernetes 和 MicroCloud 在移植，参与 RISE 项目。服务器级 RVA23 硬件预计 2026–2027 年出现。

### 36. NVIDIA：RISC-V 与 NVIDIA GPU 互操作的 profile 和平台

- 运行 CUDA 的要求：RVA23、启动和运行时服务规范、ACPI、服务器平台规范，加上硬件 PCIe I/O 一致性和 PCIe 点对点。
- 接入 NVLink Fusion 的额外要求：带一致性的 NVLink-C2C 接口、约 88 条 PCIe 通道、DOCA 和 NCCL 软件支持。
- 表态：SiFive 是 RISC-V 的 NVLink Fusion CPU 合作方；NVIDIA 称"有在其平台中使用 RISC-V 的计划"。

### 37. Infineon：RISC-V 用于汽车

- 背景：车载架构从域控制器走向区域控制器加中央计算。
- 主张：区域控制器应保留本地智能和对延迟敏感的控制环，这要求 MCU 同时承载实时控制、DSP/AI 推理和低功耗服务等异构负载。
- RISC-V 的价值：开放、可伸缩、避免 IP 锁定。
- 提醒：胜负更多取决于微架构、SoC 架构、车规认证工具链和生态，而不是指令集本身。

## Poster

### 38. Croc（ETH Zurich）

来自 arXiv 2606.25673 摘要。围绕可定制 RISC-V 平台 Croc 的全开源 SoC 设计和流片教学流程，用开源 IP、开源 EDA 和 130nm 开放 PDK。首次开课 65 名学生完成 33 个项目，30 个得到可制造版图，5 个已流片；首颗基线芯片已完成硅上测试。

### 39. ETHEREAL（KU Leuven、TU Delft）

来自 arXiv 2608.17787 摘要。首个事件驱动图神经网络处理器芯片，配合动态视觉传感器。采用邻居并行的样条卷积引擎和 2D/3D 分离的存储层次。在 VGA 分辨率数据集上每次推理 25.6 µs、1.6 µJ。论文写的是 25.6 µs，poster 标题写的是 17 µs。

### 40. CN101（Normal Computing）

只有流片时的背景新闻，不是 poster 内容。CN101 号称首颗热力学计算芯片，用数字 CMOS 实现。思路是利用芯片内的噪声和随机性：一组互联的谐振器从半随机状态出发，问题编码在耦合关系里，系统弛豫到平衡态即为解，适合矩阵求逆、高斯采样等任务。

### 41–48. 未找到公开资料的 poster（只有标题）

- Gemmelos（UC Berkeley）：Intel 16 工艺的双芯片多模态边缘 AI 平台
- Pistil（Harvard、Lockheed Martin）：16nm 加速器，配 20 小芯片 2.5D 封装，做边缘分布式小语言模型推理
- Opticore：大规模零差光子 crossbar 张量处理
- PNNL：端到端开源硬件编译器，从 Python 到首批流片
- LUTs and Bolts（CMU）：28nm eFPGA SoC，带硬化矩阵向量乘引擎
- HiVec（A*STAR、NUS）：可穿戴用 RISC-V SoC 中的 CGRA
- University of Tokyo：从微架构到硅片的 RISC-V CPU 设计课程
- KAIST：低功耗实时视觉语言导航处理器，带 3D 空间推理

## 来源

### ServeTheHome 现场报道

- <https://www.servethehome.com/amd-helios-mi400-system-architecture-at-hot-chips-2026/>
- <https://www.servethehome.com/amd-mi400-gpu-at-hot-chips-2026/>
- <https://www.servethehome.com/amd-versal-premium-gen2-at-hot-chips-2026/>
- <https://www.servethehome.com/amd-versal-rf-series-at-hot-chips-2026/>
- <https://www.servethehome.com/arms-agi-data-center-cpu-at-hot-chips-2026/>
- <https://www.servethehome.com/broadcom-thor-ultra-ethernet-nic-at-hot-chips-2026/>
- <https://www.servethehome.com/canonical-evolution-of-enterprise-open-source-risc-v-at-hot-chips-2026/>
- <https://www.servethehome.com/cerebras-talks-going-rack-scale-with-their-wses-at-hot-chips-2026/>
- <https://www.servethehome.com/d-matrix-raptor-3d-dram-accelerator-for-generative-inference-at-hot-chips-2026/>
- <https://www.servethehome.com/fujitsus-arm-based-monaka-data-center-cpu-at-hot-chips-2026/>
- <https://www.servethehome.com/googles-tpuv8s-for-training-and-inference-at-hot-chips-2026/>
- <https://www.servethehome.com/ibm-z-and-linuxone-dual-isa-processor-and-ai-acceleration-at-hot-chips-2026/>
- <https://www.servethehome.com/infineon-risc-v-for-automotive-at-hot-chips-2026/>
- <https://www.servethehome.com/intel-core-series-3-wildcat-lake-cpu-at-hot-chips-2026/>
- <https://www.servethehome.com/intel-crescent-island-160gb-to-480gb-lpddr5x-ai-gpu-at-hot-chips-2026/>
- <https://www.servethehome.com/intel-diamond-rapids-the-2027-intel-xeon-at-hot-chips-2026/>
- <https://www.servethehome.com/metas-mtia-custom-ai-silicon-at-hot-chips-2026/>
- <https://www.servethehome.com/micron-evolving-memory-architectures-for-ai-at-hot-chips-2026/>
- <https://www.servethehome.com/microsofts-maia-200-accelerator-at-hot-chips-2026/>
- <https://www.servethehome.com/nvidia-bluefield-4-processor-at-hot-chips-2026/>
- <https://www.servethehome.com/nvidia-risc-v-for-nvidia-gpus-at-hot-chips-2026/>
- <https://www.servethehome.com/nvidia-spectrum-x-ethernet-multiplane-network-architecture-at-hot-chips-2026/>
- <https://www.servethehome.com/nvidia-vera-cpu-at-hot-chips-2026/>
- <https://www.servethehome.com/nvidia-vera-rubin-nvl72-rack-at-hot-chips-2026/>
- <https://www.servethehome.com/nvidias-groq-3-lpu-accelerators-for-heterogeneous-ai-compute-at-hot-chips-2026/>
- <https://www.servethehome.com/openai-jalapeno-asic-at-hot-chips-2026/>
- <https://www.servethehome.com/oxmiq-labs-hbf-in-ai-compute-at-hot-chips-2026/>
- <https://www.servethehome.com/sambanovas-sn50-rdu-for-ai-at-hot-chips-2026/>
- <https://www.servethehome.com/samsung-evolving-hbm-base-die-at-hot-chips-2026/>
- <https://www.servethehome.com/samsung-lpddr5x-pim-at-hot-chips-2026/>
- <https://www.servethehome.com/sk-hynix-hbm-packaging-at-hot-chips-2026/>
- <https://www.servethehome.com/update-on-risc-v-standards-and-adoption-at-hot-chips-2026/>
- <https://www.servethehome.com/waymo-sensor-fusion-processor-at-hot-chips-2026/>
- <https://www.servethehome.com/xcena-mx1-cxl-computational-memory-device-at-hot-chips-2026/>

### 其他

- The Next Platform（Jim Handy tutorial）：<https://www.nextplatform.com/store/2026/08/25/you-probably-forget-how-cheap-memory-used-to-be-and-is-not-so-now/5292363>
- 每日经济（XCENA、BOS Eagle-N）：<https://www.mk.co.kr/en/business/12136672>
- 每日经济（Waymo keynote）：<https://www.mk.co.kr/en/it/12135448>
- BigGo Finance（Waymo keynote）：<https://finance.biggo.com/news/385ec83f-8469-4231-bd21-5506ddbaeb42>
- BigGo Finance（BOS Eagle-N）：<https://finance.biggo.com/news/c4289d9b-f21b-4e66-a484-fa769637a932>
- ChosunBiz（BOS Eagle-N）：<https://biz.chosun.com/en/en-it/2026/08/16/STRLJ6H5K5GB5HSTUTWCTCELXQ/>
- TechSpot（Normal Computing CN101）：<https://www.techspot.com/news/109082-normal-computing-tapes-out-world-first-thermodynamic-chip.html>
- arXiv 2606.25673（Croc）：<https://arxiv.org/abs/2606.25673>
- arXiv 2608.17787（ETHEREAL）：<https://arxiv.org/abs/2608.17787>
