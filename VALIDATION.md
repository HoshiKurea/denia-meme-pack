# 发布前校验

2026-10-22：全部图片下载后验证格式、尺寸与末帧可解码；按原文件SHA-256去重。manifest和semantic元数据通过官方JSON Schema，逐图内容哈希、分类路径和entry_id一致。

{
  "source_records": 1224,
  "excluded_non_target_records": 274,
  "included_source_records": 950,
  "unique_images": 934,
  "exact_duplicates_removed": 16,
  "categories": {
    "eat": 83,
    "like": 97,
    "see": 35,
    "cute": 63,
    "fool": 225,
    "sad": 28,
    "angry": 39,
    "sigh": 16,
    "happy": 37,
    "reply": 35,
    "work": 50,
    "thinking": 31,
    "shy": 18,
    "givemoney": 26,
    "sleep": 43,
    "greeting": 26,
    "stop": 17,
    "confused": 15,
    "surprised": 26,
    "relax": 23,
    "misc": 1
  },
  "total_bytes": 1222441014
}

分类依据为来源动作标签与缩略图人工复核，未进行完整逐帧情绪审核。
