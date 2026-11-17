# 03 · 校验与签名边界

## 三层可重算校验

| 层 | 位置 | 算法 | 覆盖 | 校验方 |
|---|---|---|---|---|
| **L1** | `DEND` 记录 | zlib CRC-32（poly `0xEDB88320`, init `0xFFFFFFFF`, 取反），**大端** | `[0, N-12)` | 电脑端升级器 |
| **L2** | tar 内 `NN01_x_sum/*.sum` | 标准 CRC-32，8 位小写 hex **文本** | 段内逐文件 | 相机端（推断） |
| **L3** | 每 1024 B 块 | `Σ(511 × u16le of block[2:1024]) & 0xFFFF` | 块内 payload | 解帧器 |

### L1 实测数值

| 机型 | 文件大小 | 存储 | 重算 |
|---|---:|---|---|
| ZV-E10 v2.03 | 372,454,920 | `0x90BF49CC` | `0x90BF49CC` ✅ |
| ZV-1F | 443,505,056 | `0x9B12703E` | `0x9B12703E` ✅ |
| **A6700 v2.00** | **1,024,017,848** | **`0xEABB5F09`** | **`0xEABB5F09`** ✅ |

排除项：全文件 CRC32 = `0x9E2BB565` ✗；`[0,N-16)` = `0xDE98536E` ✗。

### L2 格式

```
type,crc32_hex8,size_hex8,mtime_hex,0,0x3e8,owner,group,-1,-1,name,
  0 = 文件      5 = 目录
```

A6700：9 份清单 / 88 文件条目 / 15 目录条目，实算 **88/88 通过**。
`part_image.sum` 恰为 **454 bytes、LF-only**（`\r\n` 会撑到 460，破坏构建脚本断言）。

### L3 帧块

```c
struct FdatBlock {        // 固定 1024 B
    uint16_t sum16;       // 后续 511 个 u16le 之和（含 0xFF padding）& 0xFFFF
    uint16_t sizeAndEnd;  // 低15位=长度(1..1020)；bit15=最后一块
    uint8_t  payload[1020];
};
```

A6700：1,000,017 帧，`bad=0`，`endflag` 恰好 1 个。

## 不可重算的那一层：RSA-2048

```
signed_offset    = FDAT 数据起点
signed_size      = FDAT size - 256        (= 帧区 + 16B IV)
signature_offset = FDAT 起点 + size - 256
算法 = RSASSA-PKCS1-v1_5 / SHA-256 over 整个 signed region
```

**签名覆盖整个 FDAT 载荷** —— 也就是 `FdatHeader + updater.img + tar(全部 5 个分区镜像)`。
一切可执行内容都在里面。

不在签名范围内的只有：容器头（DATV/PROV/UDID/FDAT 记录头）与 `DEND` 记录 ——
**里面没有任何可执行内容**。

所以：改得到的地方没东西可塞，有东西可塞的地方改不了。

## 信任边界：识别 vs 执行

| 阶段 | 执行者 | 环境 | 验 RSA？ |
|---|---|---|---|
| 菜单提示"发现新版本" | `appFw.so`（`nflasha15`） | 正常运行 | **不验**（实机确认） |
| 点「执行」后 | updater（`nflasha1` 的 `initrd.img`） | 重启进更新环境 | **验**（文献） |

公钥在 `nflasha1:/etc/VerificationKey.pem`（451 B，SHA-256 `8281413b…c6c2e2`），
而 **`BODYDATA.DAT` 不含 `nflasha1`** —— 实测扫遍明文与 `updater.img` 均无该公钥。

**结论：「能弹出更新提示」≠「能刷入」。两者是完全不同的信任边界。**