# 第 10 篇 设备驱动模型

> 目标：理解 Linux 如何用统一的"总线-设备-驱动"模型管理成千上万种硬件，驱动如何被匹配和 probe，以及 sysfs、设备树/ACPI、DMA、电源管理在其中的位置。

## 1. 统一设备模型

2.6 之前每类子系统各自管理设备，电源管理、热插拔、sysfs 无法统一。现代驱动模型（`drivers/base/`）引入一组通用对象：

| 对象 | 含义 | sysfs 位置 |
|---|---|---|
| `struct bus_type` | 一种总线（PCI、USB、I2C、SPI、platform、virtio） | `/sys/bus/<bus>/` |
| `struct device` | 一个设备实例（几乎所有设备结构体都内嵌它） | `/sys/devices/...`（按物理拓扑） |
| `struct device_driver` | 一个驱动 | `/sys/bus/<bus>/drivers/<drv>/` |
| `struct class` | 按功能分类（net、block、input、tty），与物理位置无关 | `/sys/class/<class>/` |
| `struct kobject` | 底层引用计数 + sysfs 目录的基础对象 | 每个 kobject 一个目录 |

具体总线在此基础上"派生"：`pci_dev` 内嵌 `device`，`pci_driver` 内嵌 `device_driver`，再一次体现了 `container_of` 继承模式。

## 2. 匹配与 probe

```
设备出现（启动枚举 / 热插拔 / 设备树解析）       驱动注册（module_init → pci_register_driver）
            │                                             │
            └──────────── bus->match(dev, drv) ───────────┘
                          （比较 ID 表）
                                │ 匹配
                                ▼
                       drv->probe(dev)   ← 驱动初始化设备、申请资源、注册到上层子系统
                                │
                            dev->driver = drv，生成 sysfs 链接，发 uevent
```

ID 表举例：

```c
static const struct pci_device_id my_ids[] = {
    { PCI_DEVICE(0x8086, 0x1572) },          /* vendor, device */
    { }
};
MODULE_DEVICE_TABLE(pci, my_ids);            /* 导出到 modules.alias，供 udev 自动加载模块 */

static struct pci_driver my_driver = {
    .name     = "mydrv",
    .id_table = my_ids,
    .probe    = my_probe,
    .remove   = my_remove,
};
module_pci_driver(my_driver);
```

**自动加载**：设备出现 → 内核发 uevent，带 `MODALIAS=pci:v00008086d00001572...` → udev 执行 `modprobe $MODALIAS` → 根据 `modules.alias` 找到模块 → 加载后注册驱动 → 匹配 → probe。

**延迟 probe**（`-EPROBE_DEFER`）：驱动依赖的资源（时钟、GPIO、regulator）尚未就绪时返回该值，驱动核心稍后重试。`/sys/kernel/debug/devices_deferred` 可查看。

**手动绑定/解绑**：

```bash
echo 0000:03:00.0 > /sys/bus/pci/drivers/ixgbe/unbind
echo vfio-pci > /sys/bus/pci/devices/0000:03:00.0/driver_override
echo 0000:03:00.0 > /sys/bus/pci/drivers_probe     # 交给 vfio-pci，用于虚拟机直通
```

## 3. 设备是怎么被发现的

| 方式 | 适用 | 说明 |
|---|---|---|
| **可枚举总线** | PCI(e)、USB | 硬件有标准的配置空间/描述符，内核主动扫描读取 vendor/device ID |
| **ACPI** | x86 服务器/PC，部分 arm64 服务器 | 固件提供 DSDT/SSDT 表（AML 字节码）描述不可枚举的设备、电源方法 |
| **设备树（Device Tree）** | 嵌入式 ARM、RISC-V | bootloader 传入 `.dtb`，描述 SoC 上的设备、地址、中断、时钟；驱动用 `of_match_table` 的 `compatible` 字符串匹配 |
| **platform 设备** | SoC 内部的非可枚举设备 | 由设备树/ACPI/板级代码创建，挂在虚拟的 platform 总线上 |

设备树片段：

```dts
uart0: serial@10000000 {
    compatible = "ns16550a";
    reg = <0x10000000 0x100>;
    interrupts = <10>;
    clock-frequency = <3686400>;
};
```

驱动用 `platform_get_resource`、`devm_ioremap_resource`、`platform_get_irq`、`of_property_read_u32` 取得这些信息，因此**同一个驱动可以在不同板子上复用，硬件差异在数据中描述**。

## 4. 设备的三大类与上层框架

| 类别 | 访问方式 | 上层框架 | 例子 |
|---|---|---|---|
| **字符设备** | 字节流，`/dev/xxx`，`file_operations` | `cdev`、`misc`（简化版） | 串口、`/dev/null`、GPU 控制节点、`/dev/kvm` |
| **块设备** | 按块随机访问，经块层 | `gendisk` + blk-mq（第 8 篇） | 磁盘、NVMe、loop |
| **网络设备** | 不在 `/dev` 中，通过 socket 访问 | `net_device` + `net_device_ops`（第 9 篇） | 网卡、虚拟网卡 |

此外还有大量**子系统框架**，驱动只需填充框架要求的回调：input（键盘鼠标触摸屏）、DRM/KMS（显卡）、ALSA（声卡）、V4L2（摄像头）、hwmon（传感器）、I2C/SPI 控制器、GPIO、regulator、clk、pinctrl、watchdog、RTC、MTD（裸 flash）、IIO（工业传感器）……

字符设备号：`dev_t` = 主设备号（区分驱动）+ 次设备号（区分实例）。`ls -l /dev/sda` 中的 `8, 0` 就是这两个数。

## 5. 驱动访问硬件的方式

### MMIO 与端口 I/O

```c
void __iomem *base = pci_iomap(pdev, 0, 0);   /* 映射 BAR0 */
u32 v = readl(base + REG_STATUS);             /* 带正确屏障语义的访问器 */
writel(CMD_START, base + REG_CMD);
```

- 设备寄存器被映射到物理地址空间（PCI BAR），用 `ioremap` 得到内核虚拟地址，**必须用 `readl`/`writel` 等访问器**，不能直接解引用（需要禁止编译器优化和保证顺序）。
- x86 还保留 I/O 端口空间（`inb`/`outb`），现代设备很少使用。

### DMA

设备直接读写内存，而不通过 CPU。驱动关心三件事：**地址、一致性、映射生命周期**。

| API | 用途 |
|---|---|
| `dma_alloc_coherent()` | 分配 CPU 和设备都能一致访问的长期缓冲区（描述符环） |
| `dma_map_single()` / `dma_map_page()` | 把已有缓冲区临时映射给设备（流式 DMA，每次 I/O 一次） |
| `dma_map_sg()` | 分散/聚集列表映射 |
| `dma_sync_single_for_cpu/device()` | 流式映射期间切换所有权，在非一致性架构上刷/无效缓存 |
| `dma_set_mask_and_coherent()` | 声明设备能寻址的位数（32 位设备只能访问低 4GB） |

- **DMA 地址 ≠ 物理地址**：中间可能有 **IOMMU**（Intel VT-d、AMD-Vi、ARM SMMU）翻译。IOMMU 能隔离设备（防止恶意/出错设备写任意内存），也是 VFIO 设备直通的前提。
- **SWIOTLB**：设备寻址能力不足或机密计算（加密内存）时，用一块"跳板"缓冲区中转。
- 驱动从不应把 `virt_to_phys()` 的结果交给设备——始终使用 DMA API。

### 中断

见第 5 篇；PCI 驱动用 `pci_alloc_irq_vectors(pdev, min, max, PCI_IRQ_MSIX)` 申请多个向量，再逐个 `request_irq`。

## 6. 资源管理：`devm_*`

驱动 probe 里申请的资源很多（内存、IRQ、MMIO 映射、时钟、GPIO），出错时要按逆序释放，`remove` 时也要释放，极易遗漏。**托管资源（devres）** 把资源和 `struct device` 绑定，设备解绑时自动逆序释放：

```c
base = devm_ioremap_resource(&pdev->dev, res);
ret  = devm_request_irq(&pdev->dev, irq, handler, 0, "mydev", priv);
priv = devm_kzalloc(&pdev->dev, sizeof(*priv), GFP_KERNEL);
/* probe 中途失败直接 return 错误码，无需 goto 清理 */
```

## 7. 电源管理

| 机制 | 范围 | 回调 |
|---|---|---|
| **系统睡眠**（suspend-to-RAM `s2idle`/`deep`、hibernate） | 整机 | `dev_pm_ops` 的 `suspend`/`resume`/`freeze`/`thaw`/`poweroff`/`restore` |
| **运行时 PM**（runtime PM） | 单设备空闲时降功耗 | `runtime_suspend`/`runtime_resume`；驱动用 `pm_runtime_get_sync`/`pm_runtime_put` 维护使用计数 |
| CPU 频率/空闲 | CPU | cpufreq（governor：`schedutil`、`performance`、`powersave`）、cpuidle（C-states） |
| 设备频率 | GPU、总线 | devfreq |
| 电源域 / regulator / clk | SoC | 依赖关系由框架维护，最后一个用户释放时才关电 |

设备的 suspend 顺序遵循设备层级（子先于父，resume 相反），`device_link` 可以表达非父子的依赖。

`cat /sys/power/state`、`cat /sys/power/mem_sleep`、`powertop`、`/sys/devices/.../power/runtime_status` 可观察。

## 8. 用户态驱动与虚拟化

| 机制 | 说明 |
|---|---|
| **UIO** | 把设备寄存器 mmap 给用户态，中断通过读 fd 等待；简单但无 DMA 隔离 |
| **VFIO** | 基于 IOMMU 的安全用户态设备访问，DPDK/SPDK 与虚拟机直通（QEMU）使用 |
| **virtio** | 半虚拟化标准：前端驱动（`virtio_net`、`virtio_blk`）与后端（QEMU/vhost）通过共享内存环 virtqueue 通信 |
| **vhost / vhost-user** | 把 virtio 后端放进内核或另一用户态进程，减少 QEMU 介入 |
| **SR-IOV** | 一个 PCIe 设备虚拟出多个 VF 直接分给虚拟机 |
| **VDUSE / ublk** | 用户态实现 virtio 设备 / 块设备 |

## 9. 驱动开发的典型骨架（platform 驱动）

```c
static int my_probe(struct platform_device *pdev)
{
    struct my_priv *p = devm_kzalloc(&pdev->dev, sizeof(*p), GFP_KERNEL);
    if (!p) return -ENOMEM;

    p->base = devm_platform_ioremap_resource(pdev, 0);
    if (IS_ERR(p->base)) return PTR_ERR(p->base);

    p->irq = platform_get_irq(pdev, 0);
    if (p->irq < 0) return p->irq;

    p->clk = devm_clk_get_enabled(&pdev->dev, NULL);
    if (IS_ERR(p->clk)) return dev_err_probe(&pdev->dev, PTR_ERR(p->clk), "no clk\n");

    platform_set_drvdata(pdev, p);
    return my_register_to_subsystem(p);      /* 例如注册 misc 设备或 input 设备 */
}

static const struct of_device_id my_of_match[] = {
    { .compatible = "vendor,my-device" },
    { }
};
MODULE_DEVICE_TABLE(of, my_of_match);

static struct platform_driver my_driver = {
    .probe  = my_probe,
    .remove = my_remove,
    .driver = { .name = "my-device", .of_match_table = my_of_match },
};
module_platform_driver(my_driver);
MODULE_LICENSE("GPL");
```

## 10. 观测与调试

```bash
lspci -vvnn -k                        # PCI 设备、ID、正在使用的驱动（-k）
lsusb -t                              # USB 拓扑
ls -l /sys/bus/pci/devices/0000:03:00.0/driver
udevadm info -a /dev/nvme0n1          # sysfs 属性链（写 udev 规则用）
udevadm monitor --kernel --udev       # 实时观察 uevent
dmesg -w | grep -i mydrv              # 驱动日志（dev_info/dev_err 带设备前缀）
cat /proc/iomem /proc/ioports         # 物理地址与端口分配
echo 'module mydrv +p' > /sys/kernel/debug/dynamic_debug/control   # 打开 dev_dbg/pr_debug
```

## 11. 关键文件

| 路径 | 内容 |
|---|---|
| `drivers/base/` | `core.c`（device）、`bus.c`、`driver.c`、`dd.c`（match/probe）、`devres.c`、`power/` |
| `lib/kobject.c`、`fs/sysfs/` | kobject 与 sysfs |
| `include/linux/device.h` | `device`、`device_driver`、`bus_type` |
| `drivers/pci/` | PCI 核心 |
| `drivers/of/`、`drivers/acpi/` | 设备树与 ACPI |
| `kernel/dma/`、`drivers/iommu/` | DMA 映射与 IOMMU |
| `drivers/vfio/`、`drivers/virtio/` | 用户态直通与 virtio |
| `Documentation/driver-api/` | 驱动 API 文档 |

## 小结

驱动模型的核心是 **bus 负责匹配、driver 负责 probe、device 负责描述**，kobject/sysfs 自动把这棵对象树暴露给用户态，uevent + udev 实现热插拔和模块自动加载。驱动本身应当只关心"这个硬件怎么操作"，资源描述交给设备树/ACPI，资源释放交给 devres，地址翻译交给 DMA API 与 IOMMU，功能接口交给对应的子系统框架。
