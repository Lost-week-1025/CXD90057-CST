# 致谢 / Acknowledgements

CXD90057-CST 建立在一批公开研究之上。没有这些工作，本项目不可能存在。

按作用分类，并标注许可证状态——**本仓库不复制它们的代码**，只引用结论与方法；
需要本地对照时请自行获取。

---

## 一、壳结构与校验机制

| 项目 | 贡献 | 许可证 |
|---|---|---|
| **[`Lost-week-1025/CXD90045-FPSU`](https://github.com/Lost-week-1025/CXD90045-FPSU)** | CXD90045 三层校验完整破解（`DEND` CRC32 覆盖 `[0,N-12)`、`.sum` 文本清单规则、1024 B 帧块求和）、重打包设计、逐指令逆向 `FirmwareUpdaterEg.exe`。**本文档 CXD90045 侧的全部实测数据来自这里** | 见上游 |
| [`ma1co/fwtool.py`](https://github.com/ma1co/fwtool.py) | FDAT 容器格式与 `AesCbcCrypter` 实现基线，`fwtool-sdk` 的分发来源 | 见上游 |
| **[`Hearts-Ace/sony-a7r5-custom-firmware`](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware)** | CXD90057 `key_cxd90057_k0` / `k8`、`signature.py` 的 RSA 签名规范（`signed_size = FDAT size - 256`、`SONY_PUBLIC_SHA256`） | 见上游 |

## 二、机型侧研究

| 项目 | 贡献 | 许可证 |
|---|---|---|
| **[`ivica00/sony-a6400-research`](https://github.com/ivica00/sony-a6400-research)** | CXD90045 平台的完整证据链：`kmod/devno.ko` 设备表、`sbin/init` 挂载定义、`/etc/ld.so.preload` 与 `/tmp/autoexec.sh` 机制、`im.elf` 休眠恢复不 `exec` 的关键结论 | **MIT** |
| **[`DevCrashDay/a6400`](https://github.com/DevCrashDay/a6400)** | A6400 开机持久化 hook 的实现思路（patched `libAK8975.so` 的 `DT_INIT` → `autoexec.sh` → 挂 SD → 从卡同步二进制）、Ritual 影像管线 | **无 LICENSE**（不随本仓库分发，仅引用机制描述） |
| **[`PCIEARIA/A6400-Extra-Menu`](https://github.com/PCIEARIA/A6400-Extra-Menu)** | A6400 注入方式的对照：`PTRACE_POKETEXT` 写 `libObj.so` 代码洞穴、12 字节原始序言校验、精确版本地址、可逆性设计。其 `THIRD_PARTY.md` 也是本项目处理 DevCrashDay 授权问题的依据 | PolyForm Noncommercial 1.0.0 |
| **[`xyzhangxin/sony-a6700-powerful`](https://github.com/xyzhangxin/sony-a6700-powerful)** | A6700 FL2/FL3 解锁、载体文件（`/setting/fl23`）部署框架、Pico + BootROM 的 **只读 fastboot** 工具链与已验证载荷 | 见上游 |
| **[`Himpq/FireHydrant`](https://github.com/Himpq/FireHydrant)** | CineEI 与固件补丁工程化的早期探索 | 见上游 |

## 三、QEMU 与动态仿真

| 项目 | 贡献 | 许可证 |
|---|---|---|
| **[`chocotan/a7c2-qemu`](https://github.com/chocotan/a7c2-qemu)** | **同 SOC（CXD90057）** 的 A7C II 固件 QEMU 运行环境：`qemu-sony-native.patch`（虚拟板/输入/timer）、`qemu-sony-usb.patch`（sysbus xHCI）、`qemu-directory-sd.patch`（虚拟 SD/DMA/ATU/PCI）、DTB 资源、`overwrite/` 文件替换机制、Jiritsu USB 认证 7 步握手记录 | 见上游 |
| **[`Lincan19540/fx30-firmware-research`](https://github.com/Lincan19540/fx30-firmware-research)** | FX30 服务模式连接全链路（`054C:0E0E` → Senser 认证 → `054C:0336` → HASP 88 B）、**BK4 设置容器**的成对字节改动 + bank 校验和 + 自动回滚框架、以及上述 QEMU 方案在 **Windows 11 + WSL2** 上的实跑存档（85 个脚本、安装指北、已知阻塞点） | CC BY-NC-SA 4.0 |
| [QEMU](https://www.qemu.org/) 11.1.2 | 仿真器本体 | GPL-2.0 |
| [DTC / libfdt](https://git.kernel.org/pub/scm/utils/dtc/dtc.git/) | 设备树编译 | BSD-2-Clause |

## 四、固件格式工具

| 项目 | 贡献 | 许可证 |
|---|---|---|
| [`ReFirmLabs/binwalk`](https://github.com/ReFirmLabs/binwalk) | 固件区域探测（本项目可选依赖） | MIT |
| [Python Software Foundation](https://www.python.org/) / [`pycryptodome`](https://www.pycryptodome.org/) / [`capstone`](https://www.capstone-engine.org/) | 运行与反汇编依赖 | 各自许可 |

---

## 关于 Sony

本项目以 Sony 相机固件为**研究对象**，与 Sony Corporation 无任何关联，
不代表 Sony 立场，也不包含 Sony 签名的更新。
固件本体（`BODYDATA.DAT`）**永不进入本仓库**，需使用者自行从官方渠道获取。

文中出现的机型名、属性 ID、寄存器地址均来自公开逆向结果，**不是官方文档**，
可能有误，请以自己的实测为准。

---

## 如何引用本项目结论

若你使用本项目的数据或方法，请同时引用上述对应上游——尤其是
`Lost-week-1025/CXD90045-FPSU`（CXD90045 数据）与 `Hearts-Ace/sony-a7r5-custom-firmware`（CXD90057 密钥）。
本项目的价值主要在于**把两代平台放在一起对照**，而单代数据几乎都来自他们。