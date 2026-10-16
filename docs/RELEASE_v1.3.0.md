# v1.3.0 · 深潜

## 更新

- **深潜 DIVE**：NABO 的单键下潜游戏。按 OK 换方向，在岩壁、水母和鮟鱇之间“之”字下潜；按住下键俯冲，速度翻倍、耗氧 1.5 倍。氧气随深度消耗，吃上浮的气泡补氧，擦边躲过 +4，氧气归零后还有 1.5 秒“最后一口气”。阳光层到海沟五层海域，最深纪录在水里插旗。
- 绕过 LVGL 直接驱动屏幕，用 ST7789 硬件垂直滚动；游戏中约 30 fps，标题与结束页 59 fps。
- NABO 白褂潜水造型 9 组动作，按深度染色、顶部受光边随海域变色；16 kHz 实时合成配乐与音效。
- 工具菜单第六项，或对小智说“打开深潜”。
- **移除网络电台**为深潜腾出应用空间。需要电台请继续使用 [ai-passport-nabo-xiaozhi v1.2.0](https://github.com/Liutupi/ai-passport-nabo-xiaozhi/releases/tag/v1.2.0)，两版可随时互相升级切换。

## 下载与安装

- `xiaozhi.bin`：应用镜像，偏移 `0x10000`。
- `ai-passport-nabo-xiaozhi-dive-v1.3.0.zip`：四个镜像、manifest、刷写工具、文档与字体许可证。bootloader、分区表和资源与 v1.0.0–v1.2.0 相同。
- `manifest.json`、`SHA256SUMS.txt`：校验和。

**应用 SHA256**：`7cd8589aff5aa7eacf66bdff93a9cd5accc19613aa9add2ce80504507ac0a45a`

已安装 v1.0.0–v1.2.0：`python tools/flash_release.py --package . --mode upgrade --port 端口 --expected-mac 设备MAC`，只写应用，保留配网、激活和各项成绩。详见 [刷写说明](https://github.com/Liutupi/ai-passport-nabo-xiaozhi-dive/blob/v1.3.0/docs/FLASHING.md)，验证范围见 [验证记录](https://github.com/Liutupi/ai-passport-nabo-xiaozhi-dive/blob/v1.3.0/docs/VALIDATION.md)。

美术与原型：[nabo-dive](https://github.com/Liutupi/nabo-dive)。NABO 形象与美术不随 MIT 授权，见第三方说明。字体：思源黑体 Source Han Sans（Adobe，OFL 1.1）、Archivo Black、Space Mono（OFL 1.1），许可证随包提供。
