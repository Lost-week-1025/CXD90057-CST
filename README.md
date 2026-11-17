# CXD90057-CST

**CRC-Shell-Check** — 索尼 BIONZ XR（`CXD90057`）相机固件「壳」机制探讨。

目标机：Sony ILCE-6700（A6700），固件 **2.00**。

本仓库只做一件事：**把固件外层的封装、校验、加密机制讲清楚，并给出可离线复现的验证器**。
它不包含固件本体，不提供刷机步骤，也不试图绕过 RSA 私钥。

---

## 结论摘要

| 层 | 机制 | 能否离线重算 |
|---|---|---|
| L0 | `UFU` 容器 / 记录链（DATV·PROV·UDID·FDAT·DEND） | 解析 ✅ |
| L1 | `DEND` 记录里的 **zlib CRC-32**，覆盖 `[0, N-12)`，大端 | **✅ 实测命中** |
| L2 | tar 内 `NN01_*_sum/*.sum` 文本清单，逐文件 CRC-32 | **✅ 88/88** |
| L3 | 每 1024 B 块的 `Σ(511 × u16le) & 0xFFFF` | **✅ bad=0** |
| — | **RSA-2048 签名**（PKCS#1 v1.5 / SHA-256，覆盖整个 FDAT 载荷） | ❌ 需公钥 |

**A6700 v2.00 实测**：

```
文件大小       1,024,017,848
FDAT 载荷      1,024,017,680  = 1,000,017 × 1024 + 272
L1 DEND        0xEABB5F09 == 0xEABB5F09        PASS
L3 帧          1,000,017 帧, bad=0, endflag=1  PASS
Header CRC32   0x5D0B3237 == 0x5D0B3237        PASS
L2 .sum        9 清单 / 88 条目 / 88 通过       PASS
版本           v2.00 (versionMajor=0x02, versionMinor=0x00)
机型码         model = 0x20030001
```

### 最重要的一条

**「识别」和「执行」是两个独立阶段，信任边界不同：**

- **识别**（菜单提示"发现新版本"）由 `appFw.so` 在正常运行环境完成 → **不验签名**（已实机确认）
- **执行**（点「执行」后）在 `nflasha1` 更新环境 → **验 RSA-2048**（文献确认）

所以：**"能弹出更新提示" ≠ "能刷进去"**。这一点在社区讨论里经常被混为一谈。

### 真机验证（2026-11-17 16:20）

把改动版 `BODYDATA.DAT` 放 SD 卡根目录，A6700（当前 2.00）开机后菜单弹出：

> **机身更新 / 更新? 2.00 → 2.01**

![真机识别](docs/evidence/a6700-v201-identified-on-camera.jpg)

**仅拍摄此屏，未点击「执行」。** 这是「识别层不验 RSA」的直接证据。
详见 [docs/evidence/README.md](docs/evidence/README.md)。

### v2.00 → v2.01 重打包实测（2026-11-17）

改 `FdatHeader[32]`（`versionMinor` `0x00 → 0x01`），重算 header CRC32、第一帧 L3 校验、DEND CRC32：

```
原版 1,024,017,848 B  sha256 d3c7db5b…b847c  DEND EABB5F09
新版 1,024,017,848 B  sha256 c35a00da…f07be1  DEND 5F8FFD51
字节差异: 仅 2 个 4096 块（偏移 0x0 文件头、0x3d094000 DEND 区）
重校验: L0 ✅  L1 ✅ 5F8FFD51 == 5F8FFD51  L3 ✅ bad=0  header ✅ v2.01  L2 ✅ 88/88
VERDICT: PASS
```

**产物给真机后，菜单弹「发现新版本 2.01」** —— 这就是识别层不验签的直接证据。
RSA 签名必然失效（无私钥），所以此产物**不能用于执行更新**。

---

## 快速开始

需要 Python 3.13 + `pycryptodome`（反汇编另需 `capstone`）。
把官方 `BODYDATA.DAT` 放到仓库根目录（**本仓库不附带固件**）。

```powershell
# 1. 全层校验（L0+L1+L2+L3）
python src\cst_verify.py BODYDATA.DAT

# 2. 只改头部字段（不重算 L3/DEND）—— 仅用于离线研究，产物不能给相机
python src\cst_patch_header.py _work\test_v201.DAT 0x20:01   # versionMinor 0x00 -> 0x01

# 3. 解包内层（updater.img + tar 成员）
python tools\full_unpack.py
python tools\list_tar.py
python tools\verify_sums.py

# 4. 从 AP 根分区提取 appFw.so（需先有 _work/nflasha15.img）
python tools\dump_appfw.py
```

> **关于重打包**：`cst_repack_lossless.py` / `cst_repack_patch.py` / `cst_repack_v201.py`
> 三个脚本**暂不公开**。原因见 [docs/06-rescue-and-ei.md](docs/06-rescue-and-ei.md)：
> fastboot 写入 + 重打包的完整闭环尚未跑完，工具链还在路上。
> 重打包的**原理与数值**已在 `docs/03-integrity.md` 和 `docs/06-rescue-and-ei.md` 里说明，
> 任何人有官方固件都能自行复算。

`cst_verify.py` 会输出人类可读结果并写 `_work/verify_a6700.json`，`verdict` 字段为 `PASS` / `FAIL`。

---

## 目录

```
src/
  cst_verify.py           壳校验器（主工具，L0+L1+L2+L3 全层）
  cst_patch_header.py     FdatHeader 定点改写（轻量，不重算 L3/DEND）
  ext2.py                 ext2 只读解析（支持三间接块）
  parse_nflasha1.py       分区与镜像解析
tools/
  dump_appfw.py           提取 appFw.so 并比对 stock 哈希
  locate_string_owner.py  定位字符串归属文件
  full_unpack.py / list_tar.py / verify_sums.py / dend_check.py
  disasm_helper.py        AArch64 反汇编辅助
docs/
  01 容器 / 02 加密 / 03 校验 / 04 救砖规划 / 05 两代对比
  06 救砖与 EI 路线（fastboot 回滚思路、CineEI 补丁表）
  07 三平台交叉验证（CXD90045 / CXD90057 / FX30 BK4）
  08 回滚方案与 EI 的 RAM 补丁路径（含 EI 固件不下放的原因）
  09 AP 机制探讨（Powerful 实证、文件偏移 vs ELF VA、机型差异）
  evidence/               真机验证照片与说明
reference/                外部来源引用（不含第三方代码）
_work/                    产物输出（不入库）
_private/                 暂不公开的重打包脚本（.gitignore 排除）
```

---

## 关键常量（A6700 / CXD90057）

```
PAY_OFFSET   = 0x9C
FRAMES       = 1,000,017
KEY_ECB      = E3B0C44298FC1C149AFBF4C8996FB924          (key_aes, 跨代复用)
KEY_CBC(k8)  = 434589432D319010F1132727353286CE4D7EDE8B9C4F7217A0E0226E0F0EDC69
IV           = payload[-0x110 : -0x100]                  (载荷对齐，非文件对齐)
DEND         = file[N-12 : N]
```

> ⚠️ **IV 对齐陷阱**：`fwtool` 里 `seek(-0x110, 2)` 必须作用在 **FDAT 载荷切片**上。
> 若传整个 `.DAT`，会差 12 字节（DEND），症状是「只有 block0 后 512 B 校验失败、其余全过」
> （CBC 链特性，极隐蔽）。实测：`N-272 → ok=5 bad=1`；`N-284 → ok=6 bad=0`。

---

## 边界声明

- 本仓库**不含**索尼固件、解密后的分区镜像、私钥或任何刷写工具。
- 不提供绕过签名、刷机或修改相机的操作指引。
- 外部参考仓库的代码**不随本仓库分发**（见 `reference/README.md`），仅记录来源。
- 引用到的密钥来自已公开的上游项目，用于**格式研究与兼容性验证**。

已知风险（供使用者自行评估）：任何刷写类操作都存在变砖可能；
本文档记录的部分机制涉及 boot 分区，误操作不可逆。

---

## 致谢

完整清单见 **[ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md)**。核心来源：

- [`Lost-week-1025/CXD90045-FPSU`](https://github.com/Lost-week-1025/CXD90045-FPSU) — CXD90045 三层校验与 CRC 破解（本文档 CXD90045 数据来源）
- [`Hearts-Ace/sony-a7r5-custom-firmware`](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware) — CXD90057 密钥与签名规范
- [`ivica00/sony-a6400-research`](https://github.com/ivica00/sony-a6400-research)（MIT）— CXD90045 平台证据链
- [`DevCrashDay/a6400`](https://github.com/DevCrashDay/a6400) — A6400 开机 hook（无 LICENSE，仅引用机制）
- [`PCIEARIA/A6400-Extra-Menu`](https://github.com/PCIEARIA/A6400-Extra-Menu) — 注入方式对照
- [`xyzhangxin/sony-a6700-powerful`](https://github.com/xyzhangxin/sony-a6700-powerful) — A6700 fastboot 只读工具链
- [`Himpq/FireHydrant`](https://github.com/Himpq/FireHydrant) — CineEI 工程化探索
- [`chocotan/a7c2-qemu`](https://github.com/chocotan/a7c2-qemu) / [`Lincan19540/fx30-firmware-research`](https://github.com/Lincan19540/fx30-firmware-research) — 同 SOC QEMU 与 BK4 设置容器方法

> 上游代码不随本仓库分发，仅引用结论与方法。Sony 固件本体永不入库。