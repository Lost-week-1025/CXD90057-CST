# 救砖思路与 EI 解锁路线（v1）

> 本文只写**机制与方向**，不含可执行的重打包工具、不含固件本体。
> 所有校验数据来自对官方固件的离线分析，未修改任何相机。

---

## 一、先厘清一件事：v2.01 是「原版」还是「改动版」

| 名称 | 性质 | 是否提供 |
|---|---|---|
| 官方 `BODYDATA.DAT` v2.00 | **原版**，索尼原厂签名，可正常执行更新 | 用户自行从官方渠道获取 |
| `a6700_v201.DAT` | **改动版**：`FdatHeader[32]` 从 `0x00` 改为 `0x01`，重算 header CRC / L3 / DEND | 仅测试，不入库 |
| 重打包工具 | 能生成上述改动版 | **暂不开源** |

**改动版的 RSA 签名必然失效**（无私钥无法重签）。它能过识别层（菜单弹「发现新版本」），但点执行会在 `nflasha1` 更新环境被拒。

**所以：改动版不能用来刷机，只用来验证「识别层不验签」这个机制。**

---

## 二、下一个救砖方案：fastboot 跳过版本号做回滚

### 2.1 为什么需要「跳过版本号」

索尼的更新链会做版本比较：`新版本 > 当前版本` 才允许写入。这带来两个后果：

1. **降级被拒**：想把 v2.01 降回 v2.00，正常路径走不通
2. **救砖受限**：相机被刷坏后，想写回同版本或更低版本原厂固件，会被版本检查拦下

### 2.2 已确认的 fastboot 能力

A6700 的 fastboot 模式（`0x18D1:0x4EE0`）已由社区工具链摸清：

```
接口        (0xff, 0x42, 3)   厂商自定义
端点        0x01 / 0x81
命令        oem partition dump <type> <off_hex> <sec_hex>    + upload
上限        ≤ 0x8000 sectors
RAM 载荷    20,992 B @ 0xFE020000
```

**关键约束：现有命令集只有读，没有写。**

社区已有工具（`xyzhangxin/sony-a6700-powerful` 等）也是**只读**——
这是当前 fastboot 生态的真实边界，不是遗漏。

### 2.3 待验证的路径（fastboot 工具到位后）

工具已在路上，到位后按这个顺序验证：

| 步骤 | 做什么 | 期望 |
|---|---|---|
| 1 | `oem partition dump` 读出 `nflasha5` 的 WBI 头（512 B） | 拿到当前 boot 快照的魔数 `WBI2` |
| 2 | 读出 `nflasha1`（更新环境）前 4 KB | 确认版本比较代码位置 |
| 3 | 若工具支持写：覆写 `nflasha5` 的 WBI 头前 512 B | 让 loader 回落到 cold boot |
| 4 | 冷启动（拔电池 ≥30 s） | 观察是否跳过版本检查 |

**为什么瞄准 `nflasha5` 的 WBI 头**：

- 它是 **1314 个小节的快照索引**，只占 512 B
- 它的校验**不是强制的**（实测）
- 清掉它 → loader 走 cold boot → **重新扫描分区**，而不是走"上次已知良好"的路径
- 相比刷 AP（`nflasha15` 673 MB），**改动面小三个数量级**

### 2.4 与「跳过版本号回滚」的关系

版本比较发生在两个地方（根据现有证据）：

1. **识别层**：`appFw.so` 读 `FdatHeader[32:34]`，与 `/setting/updater/dat4` 比对 → 决定是否提示"发现新版本"
2. **执行层**：`nflasha1` 的 updater 读同一对值 → 决定是否允许写入

**fastboot 路线瞄准的是绕开第 2 层**：

- 若能直接写 `nflasha5`，就不需要经过 `nflasha1` 的 updater
- 跳过 updater = 跳过版本比较 = **可以实现降级/同版本回滚**

**这是理论上最干净的降级路径**，但前提是 fastboot 工具支持写。工具到位后第一时间验证。

### 2.5 备选：`up.sh ver` / `up.sh modver`

如果相机还有 shell（通过 Powerful 等途径）：

```bash
up.sh ver       # 只 touch 两个空文件，安全
up.sh modver    # 非原子覆盖 dat4，有风险
```

**`ver` 比 `modver` 安全**，因为它不写 `dat4`。但两者都只能影响识别层，改不了执行层的判断。

---

## 三、EI 解锁的技术路线（待深入）

### 3.1 已确认的事实

A6700 的 `appFw.so`（89,027,992 B）里，**EI 相关代码和字符串全都存在**：

```
BASE_ISO_SWITCH_EI_1000_EI        BASE_ISO_SWITCH_EI_1250_EI
BASE_ISO_SWITCH_EI_1600_EI        BASE_ISO_SWITCH_EI_2000_EI
BASE_ISO_SWITCH_EI_2500_EI        BASE_ISO_SWITCH_EI_3200_EI
BASE_ISO_HIGH_12800               BASE_ISO_LOW_800
BKID_APP_setting_exposure_index   BKID_APP_setting_base_iso_switch_ei
BKID_APP_setting_exposure_index_base_iso_auto / _high / _low
CAUTION_ID_FACTOR_LOG_SHOOTING_CINE_EI_MSG
CAUTION_ID_FACTOR_LOG_SHOOTING_CINE_EI_QUICK_MSG
ASSIGNABLE_SWITCH_BASE_ISO_SENSITIVITY
```

屏幕阅读器资源里也有对应条目：

```
usr/share/screenreader/german/asrid_other_ei_and_baseiso_set_v_2_german_1.bin
usr/share/screenreader/german/asrid_other_ei_and_baseiso_set_v_6_german_1.bin
```

**结论：A6700 不是「没有 EI 功能」，而是「EI 菜单项被隐藏」。**

### 3.2 菜单显隐的三层结构

参考 FX30 的同类研究（`OlliV/fx30_fw`），Sony 的菜单可见性分三层：

| 层 | 机制 | 位置 |
|---|---|---|
| **产品菜单类型** | `PRM_FEATURE_MANAGER_menu_item` 返回类型枚举 | `appFw.so` |
| **派生可用性** | `771PRM_HAITA_*` 属性 + `6859VAL_HAITA_*` 标签，运行时计算 | `appFw.so` |
| **编译布局** | `master_camera.uxc` / `LayoutMaster_Menu.uxc` 节点树 | `usr/share/app/` |

A6700 的 `master_camera.uxc` 是 101,868 B 的二进制（magic `uxc\a`），
`LayoutMaster_Menu.uxc` 是 3,636 B。两者都**不含字符串**，只含**节点 ID 与坐标**。

### 3.3 可行的突破方向（按难度递增）

**方向 A：改产品模型类型**

`feature_manager::update_product_model()` 决定用哪套菜单布局。
A6700 是 `PRODUCT_MODEL_DZ`（消费级），如果改成 `PRODUCT_MODEL_LAX`（Cinema Line），
可能挂载 Cinema 的菜单布局。

- 优点：一个枚举值
- 风险：`LAX` 布局依赖 FX 系列特有的硬件（如内置 ND），A6700 没有 → 可能崩

**方向 B：改 `VAL_HAITA_*` 派生可用性**

找到 `setting_exposure_index` 对应的 `VAL_HAITA_*` 标签，
把「不可用」改成「可用」。

- 优点：只影响一个功能
- 风险：这类表通常是编译进 `.rodata` 的静态数组，需要定位精确偏移

**方向 C：改 `.uxc` 布局节点树**

直接往 `master_camera.uxc` 里插入 EI 的菜单节点。

- 优点：最直接
- 风险：`.uxc` 格式未完全逆向，且文件带校验

### 3.4 壳校验层面的影响

**这是本次真正要验证的部分。**

无论改 `appFw.so` 还是 `.uxc`，文件都在 `nflasha15`（ext2）里，
改动会引发连锁重算：

```
改 appFw.so 一个字节
  → 重算 nflasha15 的 ext2 结构（如果文件大小不变，只需改块内容）
    → 重算 tar 里 0700_part_image_sum/part_image.sum 的 nflasha15 CRC
      → 重算 L2 全部 88 条
        → 重算 L3（1,000,017 帧的 sum16）
          → 重算 L1（DEND zlib CRC-32）
            → 重新生成 FDAT header CRC
```

**重点**：这条链路**能不能全自动重算**，决定了改动版能否通过识别层的完整性检查。

**已知**：L1/L2/L3 全部可重算（`cst_repack_lossless.py` 已证明无损往返）。
**未知**：`nflasha15` 的 ext2 是否有额外的文件系统级校验（Sony 自定义）。

### 3.5 建议的验证顺序

1. 先改 `appFw.so` 里一个**无副作用的 padding 字节**，走完整链路重打包
2. 验证器应给出 PASS（L0/L1/L2/L3 全过）
3. 产物给相机 → 观察是否仍能正常启动（不改行为，只验证壳）
4. 如果能过，再改真正的功能字段（`VAL_HAITA_*`）
5. 每步都保留原版备份

**第 1、2 步是本次要交付的**，第 3 步需要真机。

---

## 四、边界与免责

- 本文所有结论来自**离线固件分析**，未修改相机、未刷写
- 改动版固件（`a6700_v201.DAT`）**签名失效，不可用于执行更新**
- fastboot 写能力**尚未验证**（工具未到位），相关步骤属**待验证假设**
- EI 解锁的三种方向都**未实测**，其中方向 A（改产品模型）风险最高
- 任何刷写操作都有变砖风险，本文不构成操作建议

---

## 五、EI 补丁实证（2026-11-17 完成）

### 5.1 数据来源

`_rt/firehydrant/FireHydrant-main/cine_ei/rampatch/README.md`（Himpq/FireHydrant，已下载到本地工作区）。
该文档给出了 A6700 2.00 的**运行期补丁**落点与替换字节。

### 5.2 可做文件补丁的 9 处（全部在 RX 段，VA < 0x4488EED）

| VA | 原字节 | 改后 | 说明 |
|---|---|---|---|
| `0x2A02CE4` | `01 1C 4A B9` | `E1 00 80 52` | Step4 标题槽A `ldr` → `mov w1,#7` |
| `0x2A02D6C` | `01 44 4A B9` | `81 01 80 52` | Step4 标题槽A' |
| `0x2C55DDC` | `01 A0 55 B9` | `E1 00 80 52` | Step4 标题槽B `mov w1,#12` |
| `0x2C55E64` | `01 C8 55 B9` | `81 01 80 52` | Step4 标题槽B' |
| `0x3082218` | `15 00 40 B9` | `75 02 80 52` | Step5 `ldr w21` → `mov #0x13` |
| `0x31856AC` | `A1 7A 45 B9` | `61 02 80 52` | Step5 `ldr w1` → `mov #0x13` |
| `0x319F748` | `81 7A 45 B9` | `61 02 80 52` | Step5 `ldr w1` → `mov #0x13` |
| `0x223A618` | `70 6F FF 97` | `9B 6F FF 97` | Step6 ISO 波轮 `BL` 目标改到 EI |

**注意**：Step3 的 `0x8D915E8/EC`（HIGH 基准 26→19）**不在文件里**
（`0x8D915E8` > 文件大小 `0x54E6C98`），只能做运行期补丁。

### 5.3 完整重打包链路（已实测通过）

```
改 appFw.so 9 处
  → debugfs 写回 nflasha15（ext2，大小不变 673,741,824）
    → 重算 part_image.sum 里 dev/nflasha15 的 CRC（a9121271 → 433be511）
      → 字节级替换 tar 内的 nflasha15 与 part_image.sum（不重建 tar）
        → 改 FdatHeader[32] versionMinor 00→01
          → 重算 header CRC32 / L3 全部帧 / DEND CRC32
```

**关键经验**：**不要用 `tarfile` 重建 tar**。
`tarfile` 对目录的 padding 处理与原 tar 不一致，会多出 4,096 B，
导致 `fwSize` 和帧数都要跟着变。直接在原 tar 的成员数据区**覆写等长字节**才是干净的。

### 5.4 验证结果

```
[L0] DATV/PROV/UDID/FDAT 链 OK   FDAT payload @0x9C len=1,024,017,680
[L1] DEND  OK  stored=ED1BEC0D calc=ED1BEC0D
[L3] 帧   OK  frames=1,000,017 bad=0 endflag=1
[H ] FDAT OK magic=b'UDTRFIRM' v2.01 model=0x20030001 layout=OK
[L2] .sum OK  清单=9 条目=88 通过=88
=== VERDICT: PASS ===

文件大小 1,024,017,848 B（与原版完全相同）
sha256 d30c3ea2717632248816ae7f3ff2d1dedda96e14fd83da9d00e2653bc575597e
```

**这条链路的成功证明了：壳校验的 L1/L2/L3 全部可重算，改 AP 内容不会破坏壳（只要同步更新 3 处 CRC）。**

### 5.5 还差什么才能真正解锁 EI

上表的 9 处只覆盖 **Step 4 / 5 / 6**（标题阶梯、EI 范围、波轮映射）。
FireHydrant 文档明确说明以下内容**不发布**：

- Step 1（菜单四项可选）：需要 `persist_unit` 运行时指针 + 10 列 product-class
- Step 2（Base ISO 面板）：需要 114 对计数/标志的**完整表**（文档只给了 3 对样例）
- Step 3（HIGH 基准）：需运行期补丁
- Step 5 的 27 条数据记录全表
- Step 7/8 的岛代码

**所以这个产物能让 EI 的「计算层」就位，但菜单和面板仍不会出现。**
它的价值是**证明壳可改**，不是「已经解锁」。

### 5.6 真机试验前的提醒

1. 该产物 RSA 签名失效 → **只能用于识别层测试，不能执行更新**
2. 改的是 `/lib/appFw.so`，冷启动会重建 WBI 快照 → 如果相机有快照恢复机制，改动可能不生效
3. FireHydrant 文档强调：改 AP 后**必须清 WBI 512 B 头 + 断电冷启动**，否则加载的是旧段布局
4. 建议先做 `cst_verify.py` 离线复核（已 PASS），再考虑真机
