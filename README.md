# Denia-meme-pack
![预览](previews/cover.png)

可通过 `astrbot_plugin_meme_manager` 的「从 GitHub 安装」使用。当前版本是 **4 张 GIF 的官方基础版**，附 **32 个相关专辑、1,224 条图片记录的来源索引**，不是全图库镜像。

## 安装

| 字段 | 填写内容 |
| --- | --- |
| GitHub 仓库 | `HoshiKurea/denia-meme-pack` |
| 分支或版本 | `master` |
| 包所在目录 | `.` |

安装后，在插件「设置中心 → 使用规则」绑定需要使用的人格或会话并保存。普通分类模式可直接使用；语义模式附带图片描述，但本仓库不携带本机向量或服务商配置。

## 当前收录

| 分类 | 内容 | 数量 |
| --- | --- | --- |
| relax | 吹泡泡、放松闲聊 | 1 |
| happy | 开心摇摆 | 1 |
| like | 眨眼比耶、赞同 | 1 |
| fool | 敲打节奏、友善整活 | 1 |

4 张图片均从 [雷蛇 × 鸣潮官方联名页面](https://cn.razerzone.com/collabs/wuthering-waves) 提供的图片地址取得。使用官方提供的195×195聊天尺寸，保留GIF原字节与动画；未去水印、重画或重新编码。逐图下载地址、哈希和署名见 [included-images.json](indexes/included-images.json)。

## 完整来源索引与范围

通过[呜哇小站公开API页面](https://emoji.wuwa.games/api)文档中的分页接口整理，截至2026-10-22共32个专辑、1,224条达妮娅相关记录。部分合集含多个角色，标签不代表每张图片都是达妮娅单人图；本索引不声称已逐张完成角色视觉核验。

- [图片来源索引 JSON](indexes/source-catalog.json)
- [图片来源索引 CSV](indexes/source-catalog.csv)
- [专辑索引 JSON](indexes/source-packs.json)

图库API页面明确写着“如需二次配布，请联系站长”。因此图库素材暂仅收录来源、画师署名和资源标识，不将其原图整库公开上传，也不把短效下载票据保存到仓库。取得相应授权后，才能继续扩充分发内容。

## 校验与权利说明

包遵循 [AstrBot表情包规范](https://github.com/anka-afk/astrbot-meme-pack-index/blob/main/ASTRBOT_MEME_PACK_PROTOCOL_ZH.md)，提供`manifest.json`、分类图片、预览和`semantic_metadata.json`。发布前检查JSON Schema、实际路径、图片可解码性、SHA-256与语义条目ID；校验记录见[VALIDATION.md](VALIDATION.md)。

本仓库是玩家整理，不是库洛、雷蛇或AstrBot官方项目。原图权利归相应权利人所有，不将图片统一改授MIT或CC许可。详见[LICENSE.md](LICENSE.md)。未向官方社区索引提交PR。
