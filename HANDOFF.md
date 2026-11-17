# CXD90057-CST 交接文档

**项目**：CXD90057-CST（**C**RC-**S**hell-Check）—— 索尼 BIONZ XR（CXD90057）固件"壳"机制探讨
**日期**：2026-11-16
**目标机**：Sony ILCE-6700（A6700），固件 **2.00**
**定位**：**格式研究与校验复现**。不提供刷写指引，不包含固件本体。

---

## 0. 一句话结论

A6700 的固件"壳"（DAT 容器 + 三层校验 + 双层 AES）**已完全解出并逐字节验证**；
`DEND` CRC32、L2 `.sum`、L3 帧校验**全部可离线重算**，**唯一不可伪造的是 RSA-2048 签名**，
而 RSA **只在"执行"阶段生效**——"识别"阶段（菜单发现新版本）**完全不验签**，已实机确认。

---

## 1. 项目边界

| 做 | 不做 |
|---|---|
| 解析 DAT/FDAT 结构、复现全部校验层 | 分发索尼固件本体 |
| 无损/有损重打包（本地验证） | 提供刷机步骤 |
| 记录识别层与执行层的信任边界 | 绕过 RSA 私钥 |
| 整理 A6400 生态对比 | 传播第三方无授权代码 |

> 仓库内**不包含**：`BODYDATA.DAT`、解密后的分区镜像、任何密钥以外的绕行工具。
> DevCrashDay/a6400 的代码**不在本仓库**（该上游无 LICENSE，按 A6400-Extra-Menu 的第三方声明处理）。

---

## 2. 已确认事实

证据等级：**【实测】** 本次跑通并校验通过 ／ **【文献】** 上游记录 ／ **【推断】** 结构推导

### 2.1 容器结构【实测】

```
0x00  89 55 46 55 0D 0A 1A 0A        8 B 魔数（仿 PNG）
0x08  [u32be 4]["DATV"][01 00 00 00]
0x14  [u32be 4]["PROV"][01 00 00 00]
0x20  [u32be 0x6C=108]["UDID"][108 B]
0x94  [u32be 0x3D094510]["FDAT"][密文…]     载荷起于 0x9C
N-12  [u32be 4]["DEND"][u32be CRC32]
```

A6700 v2.00 实测：`N = 1,024,017,848`，FDAT 载荷 `1,024,017,680`
= **1,000,017 × 1024 + 272**（帧区 + trailer）。

**UDID 长度随机型而异**（A6700=108、ZV-E10=188、ZV-1F=84、A7R V=20【文献】），
所以**不能写死 FDAT 偏移**，必须扫锚点。

### 2.2 三层校验【实测，全部通过】

| 层 | 位置 | 算法 | 覆盖 | 校验方 |
|---|---|---|---|---|
| **L1** | `DEND` 记录 | zlib CRC-32（poly `0xEDB88320`, init `0xFFFFFFFF`, 取反），**大端** | `[0, N-12)` | 电脑端升级器 |
| **L2** | tar 内 `NN01_x_sum/*.sum` | 标准 CRC-32，8 位小写 hex **文本** | 段内逐文件 | 相机端【推断】 |
| **L3** | 每 1024 B 块 | `Σ(511 × u16le of block[2:1024]) & 0xFFFF` | 块内 payload | 解帧器 |

A6700 v2.00 实测值：

```
L1  DEND   stored = 0xEABB5F09  calc = 0xEABB5F09   ✅
L3  1,000,017 帧   bad_checksum = 0   endflag = 1     ✅
H   FdatHeader CRC32 0x5D0B3237 = 0x5D0B3237          ✅
L2  9 份清单 / 88 文件条目 / 88 通过                   ✅
```

**排除的近似假设**（L1）：全文件 CRC32=`0x9E2BB565` ✗、`[0,N-16)`=`0xDE98536E` ✗。

### 2.3 加密【实测】

4th-gen `AesCbcCrypter`：

```
[0, 512)   AES-128-ECB, key = key_aes
[512, L)   AES-256-CBC, key = 机型密钥, IV = 载荷尾 -0x110
```

| 项 | 值 |
|---|---|
| `key_aes`（ECB，跨代复用） | `E3B0C44298FC1C149AFBF4C8996FB924` |
| **A6700 CBC 密钥** | **`key_cxd90057_k8`** = `434589432D319010F1132727353286CE4D7EDE8B9C4F7217A0E0226E0F0EDC69` |
| A6700 IV | `payload[-0x110:-0x100]` = `f0cbfa99f5c960ed56fc44bcb8d1aec1` |

> ⚠️ **IV 对齐陷阱（本次实测确认）**：`fwtool` 的 `seek(-0x110, 2)` 必须作用于
> **FDAT 载荷切片**，不能传整个 `.DAT`。差 12 字节（DEND）时，**只有 block0 后半错、block1+ 全过**
> （CBC 链特性），症状极隐蔽。实测：`N-272 → ok=5 bad=1`，`N-284 → ok=6 bad=0`。

`cxd90057_k0` 对 A6700 **6/6 全错**，故 A6700 用 **k8**（与 A7R V 相同）。
密钥来源：[Hearts-Ace/sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware)。

### 2.4 RSA-2048 签名【规范已定，未验签】

```
signed_offset    = FDAT 数据起点  = 0x9C
signed_size      = FDAT size - 256 = 1,024,017,424  (= 帧区 + 16B IV)
signature_offset = N-268 .. N-12   (256 B)
算法 = RSASSA-PKCS1-v1_5 / SHA-256 over 整个 signed region
```

**公钥不在更新包内**：实测扫过 `BODYDATA.DAT` 明文（1,020,017,152 B）与 `updater.img`
（1,253,376 B），均**无** `VerificationKey` / PEM 公钥 / `libupdaterapi`。
按 A7R V 文献，公钥在 **`nflasha1` 的 `initrd.img:/etc/VerificationKey.pem`**（451 B，
SHA-256 `8281413b5607446939613e07d020b2c7d8ee2371349099de56bc8288f7be0a43`），
而 **`BODYDATA.DAT` 不含 `nflasha1`**。

### 2.5 内层布局【实测】

```
[0, 512)                FdatHeader
[512, 1,253,888)        updater.img  (SquashFS 4.0, 1,253,376 B, magic "hsqs")
[1,253,888, 1,020,017,152)  tar (137 成员 = 39 目录 + 97 文件)
```

FdatHeader 实测：`magic=UDTRFIRM` `version=0100` `modeType='U'` `luwFlag='N'`
`versionMajor=0x02 versionMinor=0x00` → **v2.00**，`model=0x20030001`，`region=0`，
`numFileSystems=2`，`FS[0]=U(offset 512,size 1,253,376)`，`FS[1]=P(512,0)`。

布局闭合：`512 + 1,253,376 + 1,018,763,264 = 1,020,017,152` ✅

A6700 分区：`nflasha15`=673,741,824（AP 根 ext2）／`nflasha5`=248,637,568（WBI 快照）／
`nflasha3`=32,762,880（内核）／`nflasha8`=25,008,128（CP）／`nflasha7`=5,222,400。

### 2.6 识别层 vs 执行层 —— 本项目最重要的结论

| 阶段 | 执行者 | 环境 | 验 RSA？ |
|---|---|---|---|
| 菜单"发现新版本" | `appFw.so`（`nflasha15`） | 正常运行 | **不验**【实测】 |
| 点「执行」后 | `initrd.img` updater（`nflasha1`） | 重启进更新环境 | **验**【文献】 |

**实机验证**：把 `versionMinor 0x00→0x01`（v2.00→2.01），重算 header CRC + L3 + L1，
签名失效但保留原字节，放 SD 卡 → **相机弹出"发现新版本 2.01"**。

→ **"能弹出提示" ≠ "能刷入"**。这是社区里最容易混淆的一点。

---

## 3. 已完成的实验

| # | 实验 | 结果 |
|---|---|---|
| 1 | 官方 CDN 直链抓包 | `https://di.update.sony.net/NEX/tF4c94033c/BODYDATA.DAT`（1,024,017,848 B，MD5 = 源站 ETag `92cefb207c53e3ac3f00ee8b3bdb8bd2`） |
| 2 | L1/L2/L3/H 全层校验 | **VERDICT: PASS** |
| 3 | 无损重打包 roundtrip | **与原厂逐字节一致**（MD5 相同），证明打包器正确 |
| 4 | 有损重打包（改 1 字节） | 全层 PASS，签名失效（预期） |
| 5 | 版本号改 2.01 → 实机识别 | **相机弹出"发现新版本 2.01"** ✅ |
| 6 | ext2 解析 + `appFw.so` 提取 | 89,027,992 B，SHA-256 `e65fd595…b0ef3` = stock ✅ |
| 7 | A6700 启动链扫描 | **无** A6400 式 `autoexec`/`ld.so.preload` 机制 |

---

## 4. 工具清单

| 脚本 | 用途 |
|---|---|
| `src/cst_verify.py` | **壳校验器**：L0 容器链 + L1 DEND + L2 九份 `.sum` + L3 全帧。输出 JSON |
| `src/cst_repack_lossless.py` | 无损重打包（验证用，应得到字节一致结果） |
| `src/cst_repack_patch.py` | 有损重打包示例（改 padding） |
| `src/cst_patch_header.py` | **header 定点改写**：`patch <out> <off>:<hex>`，自动重算 header CRC + L3 + L1 |
| `src/ext2.py` | ext2 只读解析（直接/单/双/三间接块），可提任意文件 |
| `tools/dump_appfw.py` | 从 `nflasha15.img` 提 `/lib/appFw.so` 并比对 stock 哈希 |
| `tools/locate_string_owner.py` | 定位字符串属于 ext2 里哪个文件 |
| `tools/list_tar.py` / `verify_sums.py` / `full_unpack.py` | tar 列目录 / `.sum` 校验 / 全量解密 |
| `tools/disasm_helper.py` | AArch64 反汇编辅助（需 capstone） |

**运行前提**：Python 3.13（建议 `_runtime`）+ `pycryptodome` + `capstone`。
把官方 `BODYDATA.DAT` 放在项目根目录，产物落 `_work/`。

```powershell
python src\cst_verify.py BODYDATA.DAT
python src\cst_patch_header.py _work\test.DAT 0x20:01   # 版本号 2.00 -> 2.01
python tools\dump_appfw.py                              # 需先有 _work/nflasha15.img
```

---

## 5. 关键位置

| 内容 | 路径 |
|---|---|
| 官方固件 | `BODYDATA.DAT`（项目根，不入库） |
| 解密明文 | `_work/a6700_fdat_plain.bin` |
| AP 根镜像 | `_work/nflasha15.img`（673,741,824 B） |
| stock appFw.so | `_work/appFw_stock.so`（89,027,992 B） |
| 校验报告 | `_work/verify_a6700.json` |

---

## 6. 未解问题

| # | 问题 | 影响 |
|---|---|---|
| 1 | A6700 的 RSA 公钥实体未取得 | 验签无法完成；需 `nflasha1`（fastboot 只读）或官方更新器 exe |
| 2 | PC 端 updater 对 A6700 是否只验 L1 | 决定"改内容能否过电脑端" |
| 3 | `Service mode`（`/setting/updater/mode3`）真实行为 | 行为在 LSI/bootloader 侧，不在 `nflasha15` |
| 4 | `sshd` 的 CamRemote 触发条件 | 已定位 `executeNotifyCamRemoteCmd`（0xA1E4, 576 B）待反汇编 |
| 5 | `nflasha1:/boot/kemco.txt` 内容 | 内核命令行位置已确认（`up.sh func_cons` 会写它），需 fastboot 读 |
| 6 | 帧 0 的 `sum16` 特殊规则 | A6700 实测 `bad=0`，说明本机种通用规则成立；与 CXD90045 记录的差异待核 |

---

## 7. 下一步优先级

1. **fastboot 只读确认**（用户手上已有 Pico 工具链）
   - 先 `--检查Pico` / 离线校验载荷，不碰相机
   - 注入后只发 `getvar:product` / `oem partition`，预期 `A6700-AP-read-candidate`
   - ⚠️ 注入要求冷启动 → **WBI 快照重建 → FL23 补丁丢失**，事后需重刷 Powerful
2. 反汇编 `executeNotifyCamRemoteCmd`，定出 CamRemote 设置 → `SSHD_START_CMD` 的映射
3. 若取得公钥 → 补全验签，闭合整条信任链

---

## 8. 风险与禁止事项

- ❌ **不要**把改过的 `BODYDATA.DAT` 真正执行更新：`nflasha1` 会 RSA 验签拦下，最坏是升级失败重来。
- ❌ **不要**把 FASTBOOT 当救砖工具：当前开源工具**只读**（`oem partition dump` + `upload`），
  写路径未开放，手册原话"完整恢复尚未验证"。
- ❌ **不要**在未备份的情况下改 `nflasha1`（boot 分区，含 `boot/kemco.txt`）。
- ⚠️ 改 `versionMinor` 后若真刷成功，版本号变高将**无法用 SD 卡回退**到 2.00。
- ⚠️ 刷入类操作中途断电 = 变砖；SD 卡更新全程约 6 分钟。

---

## 9. 参考来源

| 来源 | 用途 |
|---|---|
| `ma1co/fwtool.py` | FDAT 格式与 crypter 实现基线 |
| [Hearts-Ace/sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware) | CXD90057 `k0`/`k8` 密钥、`signature.py` 签名规范 |
| [blog.simplypatrick.com A7R V 逆向](https://blog.simplypatrick.com/posts/2026/10-29-sony-a7r5-custom-firmware/) | CXD90057 架构、nflasha1 信任链、Fastboot/mira |
| `ivica00/sony-a6400-research` | CXD90045 平台证据、`ld.so.preload`/`autoexec` 机制 |
| [PCIEARIA/A6400-Extra-Menu](https://github.com/PCIEARIA/A6400-Extra-Menu) | A6400 注入方式对比（PTRACE 路径） |
| DevCrashDay/a6400 | A6400 开机 hook 实现（**上游无 LICENSE，仅本地参考，不入库**） |

---

*本文所有【实测】结论均可用第 4 节脚本复现。*
---

# 附录 A · 版本三元组与救砖分级（2026-11-16 追加）

## A.1 为什么"改版本号"这件事还没定性

把三个不同位置的"版本"分开建模，问题立刻清楚：

| # | 载体 | 位置 | 谁写 | 状态 |
|---|---|---|---|---|
| ① | 包声明版本 | `FdatHeader` @0x21(major)/0x20(minor) | 我们（重打包） | ✅ 实测可控 |
| ② | 相机当前版本 | `/setting/updater/dat4` | updater（`ud_datcnv.elf`） | ❓ 未验证 |
| ③ | 菜单显示 | 未知，读 ① 还是 ② | — | ❓ 未验证 |

证据（`/bin/up.sh`）：

```sh
ud_datcnv.elf -d -i /setting/updater/dat4 -o /tmp_updater/upcurver -a
_current=`cat /tmp_updater/upcurver`         # 相机自身的版本记录位于 dat4
```

**推论**：
- 识别阶段 = ①（包）对比 ②（dat4） → 提示 "2.00 → 2.01"（与实测现象吻合）
- **能不能回滚，取决于刷入后 ② 是否被写成 2.01**

| 刷后 ② 的状态 | 后果 |
|---|---|
| 被写成 2.01 | 官方 2.00 判为降级 → **锁死，无法 SD 卡回退** |
| 仍为 2.00 | 版本显示与实际固件内容不一致 → **状态更危险** |

→ **结论：改版本号的安全性不取决于 FdatHeader，取决于 updater 是否回写 dat4。**

## A.2 未验证的"另一层校验"

已知 RSA-2048 在 `nflasha1` 的 updater 内，但以下三点**完全未验证**：

1. 验签发生在流程的**哪一步**（解包前 / 写分区前 / 每分区前）
2. 校验失败时是**安全中止**，还是**已写入部分分区**
3. 是否存在 `.sum` 之外的**第四层校验**

**在此之前，任何"真刷测试"都应定性为"不可逆且后果未知"，而非"低风险尝试"。**

## A.3 救砖能力分级

| 级 | 手段 | 前置条件 | 现状 |
|---|---|---|---|
| **L0** | 官方 SD 卡刷 `BODYDATA.DAT` | 相机能进菜单 | ✅ 有原厂包（MD5 `92cefb207c53e3ac3f00ee8b3bdb8bd2`） |
| **L1** | 强制进 Updater mode | 能写 `/setting/updater/mode`，或 bootloader 有 fallback | ❓ **关键未知** |
| **L2** | fastboot 写 flash | 需带写命令的载荷 | ❌ 上游仅只读 |
| **L3** | 拆机 / 送修 | — | 最后手段 |

**L1 是核心命题**：bootloader 读 `/setting/updater/mode*` 决定启动模式（`up.sh` 已证实），
但**"读不到 mode 文件"时的默认行为未知** —— 即 WBI 快照损坏/被清时，是自动回落 updater 还是黑屏。

若 L1 成立，则"AP 层写坏"仍可自救；若 L1 不成立，则 A 层（`appFw.so` 112 B）写入 = 必送修。
**该结论直接改变风险评估等级，应优先取证。**

有利条件：`/setting` 是独立 vfat（`nflasha2`），AP 分区损坏不影响它。

## A.4 fastboot 只读的取证清单（按价值排序）

| 排序 | 目标 | 内容 | 价值 |
|---|---|---|---|
| 1 | `nflasha1` | `dat4`（相机版本基线） | 回滚判断的基准 |
| 2 | `nflasha1` | updater 二进制/脚本 | **RSA 步骤位置、失败行为、是否回写 dat4** |
| 3 | `nflasha1` | `boot/kemco.txt` | 内核命令行、是否存在 fallback 参数 |
| 4 | `nflasha1` | `initrd.img` → `/etc/VerificationKey.pem` | 公钥（451 B，目标 `8281413b…c6c2e2`） |

> **1、2 项价值高于公钥**：公钥只能"验别人给的包"，而 1/2 决定"自己做的事安不安全"。

## A.5 推进顺序（在 A.2/A.3 未结之前不得真刷）

```
① fastboot 只读 → nflasha1（24 MiB），nflasha7 若可达
② 静态判定：RSA 步骤位置 / 失败行为 / dat4 是否回写
③ 判定 L1：bootloader fallback 是否存在
④ ①②③ 结论齐备后，才评估"真刷 2.01"的后果
```

## A.6 项目合并说明

CST 作为总项目，保留对以下逆向材料的引用（**不在本仓库内分发代码**）：

- `_repos/a6700-powerful/`（xyzhangxin/sony-a6700-powerful，fastboot 工具链与只读载荷）
- `_repos/r5cf/`（Hearts-Ace/sony-a7r5-custom-firmware，CXD90057 密钥与签名规范）
- `_repos/A6400-Extra-Menu/`、`_repos/DevCrashDay-a6400/`（A6400 生态对照）
- `_repos/SONY-PMCA-RE/`（格式基线）

许可证状态见 `reference/README.md`；DevCrashDay 无 LICENSE，仅本地参考。

---

# 附录 B · 静态取证清单（无需相机）

详见 `docs/04-rescue-plan.md` §4。优先级从高到低：

## B.1 `dat4` 的读写方（第一优先）

| 项 | 查什么 | 判定依据 |
|---|---|---|
| **P1** | 谁**读** `dat4` | `nflasha15` 搜 `dat4` / `/setting/updater`；看引用者的加载路径 |
| **P2** | 是否在启动路径 | 引用者是否出现在 `libIMDB.so` 服务表内 |
| **P3** | bootloader 是否读 | 在 `nflasha1` / `nflasha7` 内搜 `dat4` |
| **P4** | `dat4` 格式 | 已提取样本 + `ud_datcnv.elf` 反汇编 |

**判读**：若 P1/P2 显示只有 `up.sh` 与 updater 使用、且 P3 为否 →
`up.sh modver` 的风险可从「中」降到「低」。

## B.2 updater 验签行为（第二优先）

| 项 | 查什么 |
|---|---|
| **U1** | RSA 验签在流程的**哪一步**（解包前 / 写分区前） |
| **U2** | 失败时**是否已写入**部分分区 |
| **U3** | 是否存在 `.sum` 之外的第四层校验 |

## B.3 bootloader 退化行为（第三优先）

| 项 | 查什么 |
|---|---|
| **B1** | `/setting/updater/mode*` 缺失时的默认行为 |
| **B2** | WBI 快照失效时是否自动回落 updater |
| **B3** | `kemco.txt` 支持的参数（有无 `init=` 类覆盖入口） |

## B.4 公钥（第四优先）

| 项 | 查什么 |
|---|---|
| **K1** | `nflasha1` 内是否有 `VerificationKey.pem`（451 B，`8281413b…`） |

> K1 价值低于 P/U 组：公钥只能"验别人给的包"，P/U 决定"自己做的事安不安全"。

## B.5 R1 安全性结论（已写入 docs/04）

| 命令 | 写入 | 原子性 | 风险 |
|---|---|---|---|
| `up.sh ver` | 两个空文件 | `touch`，高 | 低 |
| `up.sh modver` | **覆盖写** `dat4` | **无**（直接 `-o`） | 中（有备份可降级） |

**官方脚本的原子性低于社区实现**（对比 `fl23_files.c` 的 `O_EXCL` + 哈希 + rename），
这是评估时必须注意的不对称。

---

# 追加工作记录（2026-11-17）

## 完成

1. **v2.00 → v2.01 重打包并真机验证**
   - 改 `FdatHeader[32]`（`versionMinor` `0x00 → 0x01`），重算 header CRC32 / L3 / DEND
   - 只 2 个 4096 块差异（`0x0` 文件头、`0x3d094000` DEND 区），固件内容零改动
   - **真机弹出「2.00 → 2.01」**（见 `docs/evidence/`）——识别层不验 RSA 的直接证据

2. **交叉矫正**
   - 用 `cst_verify.py` 独立验证 A6700 官方固件：L0/L1/L2/L3 全 PASS
   - 与另一次独立实现逐项吻合（DEND `EABB5F09`、1,000,017 帧、model `0x20030001`）

3. **EI 补丁链路验证**（FireHydrant 的 9 处文件级补丁）
   - `appFw.so` 9 处 patch（Step 4/5/6），sha256 `e65fd595…` → `7326dba9…`
   - 完整重打包链路跑通：`debugfs` 写 `nflasha15` → 重算 `part_image.sum` →
     **字节级替换 tar 内成员**（不重建 tar）→ 改 versionMinor → 重算 L3/header/DEND
   - 壳校验全层 PASS
   - **重点经验**：不要用 `tarfile` 重建 tar，它对目录 padding 处理与原 tar 不一致，
     会多 4,096 B；直接在原 tar 的成员数据区覆写等长字节才干净

## 未完成 / 待办

1. **fastboot 写入 + 重打包的完整闭环** —— 这是重打包脚本暂不公开的直接原因。
   fastboot 工具链还在路上；现有社区工具的 `oem partition dump` 只有读能力。
2. Step 1（菜单四项）/ Step 2（Base ISO 面板）的完整计数表未获得
   （FireHydrant 只发布了样例，114 对全表未公开）
3. Step 3（HIGH 基准 26→19）是运行期地址（`0x8D915E8` > 文件大小），无法做文件补丁
4. QEMU 仿真部分暂不并入本仓库

## 公开策略

- 仓库只放：校验器、文档、机制说明、真机证据
- 不放：固件本体、改动版产物、三个重打包脚本（`_private/` 且 `.gitignore` 排除）
- 原因：fastboot + 重打包闭环未跑完，过早放出脚本会引导他人做未经验证的刷写

## 追加（2026-11-17 傍晚）

### 新增文档

- `docs/07-platform-crossvalidation.md` —— CXD90045 / CXD90057 / FX30 BK4 三平台对照
- `docs/08-rollback-and-ei-rampatch.md` —— 2.01 回滚阶梯 + EI 的 RAM 补丁路径 + 不下放原因

### 从 FireHydrant 提取的关键结论

1. **`wbi rewrite`（212）是防砖第一道闸**：写回原样 512 B，`verify=OK` 才说明写通道可用
2. **FX30 的上游排除结论「菜单可见性不在 BK4 属性层」** —— 与 A6700 一致
3. **EI 的 Step 0–8 全是 RAM 补丁**，改内存不改 flash，断电自动消失
4. **Step 3 的 `0x8D915E8` 超出文件范围**（> `0x54E6C98`），只能 RAM 补
5. **回滚硬约束**：不要在 BIS/更新流程关机（会走 warm 重建快照），必须拔电池

### 公开状态的诚实说明

EI 测试固件不下放的五个原因：
1. fastboot 防砖保护未测试
2. 完整回滚方案未验证
3. fastboot 工具未到位（只有读命令）
4. `debugfs write` 导致 ext2 块重新分配（242,633 个 4096 块差异）
5. EI 版无真机验证（只有 `a6700_v201.DAT` 验过）

**干净的替代做法**：用 `debugfs -R "blocks"` 找数据块 + `dd` 原地改 36 字节 —— 未做。

## 追加（2026-11-17 晚）

### 新增 docs/09-ap-mechanism.md

从 `_repos/a6700-powerful` 提取的实证数据：

**六项功能的改动量**（Powerful 实测）：
```
FTP          App  89 B  WBI 151 B  CP 0
关机快门帘    App   9 B  WBI  21 B  CP 0
灵活曝光      App  17 B  WBI  39 B  CP 0
电子快门声音  App   2 B  WBI   4 B  CP 1
位移多帧合成  App   3 B  WBI   9 B  CP 0
动态增强防抖  App   2 B  WBI   4 B  CP 0
────────────────────────────────────
合计          App 122 B  WBI 228 B  CP 1 B（355 个字段定义）
```

**第三次交叉验证**：Powerful 的镜像身份表与我们的记录完全一致
- `app` 89,027,992 B `/ e65fd595…b0ef3`
- `cpapp` 25,008,128 B `/ f12fa369…91ed`

**关键差异**：Powerful 用**文件偏移**，FireHydrant 用 **ELF VA**
- RX 段 `off=0 vaddr=0` → VA 可直接当文件偏移
- RW 段 `off=0x4489aa0 vaddr=0x4499aa0` → 差 0x10000

**机型差异**：A6700 与 A7C2 的 `appFw.so` 大小相同（89,027,992）但 sha256 不同
→ 跨机型不能照搬偏移

**重要澄清**：索尼从未发布 A6700 的 2.01 官方固件。
我们的 `a6700_v201.DAT` 是自改版本号的产物，不存在「A6700 2.01 的偏移」。
