# 发布前校验

日期：2026-10-22。

- manifest.json通过官方JSON Schema。
- semantic_metadata.json通过官方JSON Schema。
- 分类、相对路径、实际文件、内容哈希、语义条目ID相互匹配。
- 4张图按SHA-256去重后均不重复。
- 预览图和图标存在且可读取。
- 来源索引包含32个专辑、1224条记录，未保存临时下载票据。

- `memes/relax/denia_bubbles.gif`：GIF全部45帧可解码；哈希和条目ID匹配。
- `memes/happy/denia_sway.gif`：GIF全部40帧可解码；哈希和条目ID匹配。
- `memes/like/denia_victory.gif`：GIF全部20帧可解码；哈希和条目ID匹配。
- `memes/fool/denia_rhythm.gif`：GIF全部20帧可解码；哈希和条目ID匹配。

此记录确认资源包结构与文件完整性；未连接用户AstrBot实例进行聊天发送测试。
