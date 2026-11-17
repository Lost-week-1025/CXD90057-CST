# 文档索引

完整技术细节与证据等级见仓库根的 **`交接_2026-11-16.md`**（推荐先读）。

| 文档 | 内容 |
|---|---|
| [01-container.md](01-container.md) | DAT/UFU 容器、FDAT 内层布局、逐机型偏移差异 |
| [02-crypto.md](02-crypto.md) | 双态 AES（ECB+CBC）、机型密钥、**IV 对齐陷阱** |
| [03-integrity.md](03-integrity.md) | 三层校验（L1/L2/L3）与 RSA 签名边界 |
| [04-rescue-plan.md](04-rescue-plan.md) | **救砖方案规划**：版本三元组、R0–R3 分级、静态取证清单 |
| [05-cxd90045-vs-cxd90057.md](05-cxd90045-vs-cxd90057.md) | **两代对比**：实测数据、帧 0 规则差异、更新机制演进、致谢 |

## 一句话版

- **L1**：`DEND` 里 zlib CRC-32，覆盖 `[0, N-12)`，大端 → 可重算
- **L2**：tar 内 `.sum` 文本清单，逐文件 CRC-32 → 可重算
- **L3**：每 1024 B 块 `Σ(511×u16) & 0xFFFF` → 可重算
- **RSA-2048**：覆盖整个 FDAT 载荷 → **不可重算**（无私钥）
- **识别层不验 RSA，执行层验** → "能提示" ≠ "能刷入"
## 文档索引

| 文件 | 内容 |
|---|---|
| `01-container.md` | UFU 容器与记录链（DATV/PROV/UDID/FDAT/DEND） |
| `02-crypto.md` | 第四代 AesCbcCrypter：密钥、IV 对齐、分帧 |
| `03-integrity.md` | 三层校验（L1 zlib CRC-32 / L2 tar .sum / L3 分帧 sum16） |
| `04-rescue-plan.md` | 救砖分级 R0–R3 |
| `05-cxd90045-vs-cxd90057.md` | 两代机制演进：从 PC 端到机身端 |
| `06-rescue-and-ei.md` | fastboot 回滚思路、EI 三层菜单结构、9 处补丁表与重打包实证 |
| `07-platform-crossvalidation.md` | CXD90045 / CXD90057 / FX30 BK4 三平台校验机制对照 |
| `08-rollback-and-ei-rampatch.md` | 2.01 回滚阶梯、EI 的 RAM 补丁路径、EI 固件不下放的原因 |
| `09-ap-mechanism.md` | AP 机制：Powerful 实证的 122+228+1 字节、文件偏移 vs ELF VA、机型差异 |
| `evidence/` | 真机验证照片（v2.01 被相机识别）与说明 |
