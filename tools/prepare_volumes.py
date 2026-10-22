"""Prepare and validate small installable branches without re-encoding source images."""
import copy
import csv
import hashlib
import io
import json
import math
import os
import subprocess
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
REPO = 'HoshiKurea/denia-meme-pack'
LIMIT = 650 * 1024 * 1024


def git(*args, data=None, env=None):
    return subprocess.check_output(['git', *args], cwd=ROOT, input=data, env=env).decode().strip()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def image_csv(entries):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['path', 'category', 'labels', 'artists', 'source_pages', 'sha256', 'bytes', 'frames'])
    for e in entries:
        writer.writerow([e['path'], e['category'], ' / '.join(e['source_labels']),
            ' / '.join(sorted({a for s in e['sources'] for a in s['artists']})),
            ' / '.join(sorted({s['source_page'] for s in e['sources']})),
            e['sha256'], e['bytes'], e['frames']])
    return ('\ufeff' + stream.getvalue()).encode()


def cover(entries, number, total):
    # A preview collage only; the installed source files keep their original bytes.
    chosen = []
    for category in sorted({e['category'] for e in entries}):
        chosen.append(next(e for e in entries if e['category'] == category))
    chosen = chosen[:20]
    canvas = Image.new('RGB', (1000, 1100), '#f3f0f7')
    draw = ImageDraw.Draw(canvas)
    title = ImageFont.load_default(size=30)
    small = ImageFont.load_default(size=16)
    draw.text((28, 18), f'DENIA MEME PACK  /  {number} of {total}', fill='#342641', font=title)
    draw.text((28, 58), f'{len(entries)} original images - categorized for AstrBot', fill='#6f607a', font=small)
    for index, item in enumerate(chosen):
        x, y = index % 5 * 200, index // 5 * 245 + 105
        with Image.open(ROOT / item['path']) as image:
            image.seek(getattr(image, 'n_frames', 1) // 3)
            frame = image.convert('RGBA')
            frame.thumbnail((180, 195))
            canvas.paste(frame, (x + (200 - frame.width) // 2, y), frame)
        draw.text((x + 15, y + 205), item['category'], fill='#51435d', font=small)
    stream = io.BytesIO()
    canvas.save(stream, format='PNG', optimize=True)
    return stream.getvalue()


def main():
    assert (ROOT / 'tools/curation.json').exists(), 'Curation must finish before publication'
    assert not (ROOT / 'incoming/records.json').exists(), 'Finalize collection first'
    entries = json.loads((ROOT / 'indexes/included-images.json').read_text(encoding='utf-8'))
    full_summary = json.loads((ROOT / 'indexes/summary.json').read_text(encoding='utf-8'))
    original_manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    original_semantic = json.loads((ROOT / 'semantic_metadata.json').read_text(encoding='utf-8'))
    catalog = json.loads((ROOT / 'indexes/source-catalog.json').read_text(encoding='utf-8'))
    part_count = max(1, math.ceil(sum(e['bytes'] for e in entries) / LIMIT))
    buckets = [[] for _ in range(part_count)]
    sizes = [0] * part_count
    for entry in sorted(entries, key=lambda e: (-e['bytes'], e['path'])):
        index = min(range(part_count), key=lambda n: (sizes[n], n))
        buckets[index].append(entry)
        sizes[index] += entry['bytes']
    for bucket in buckets:
        bucket.sort(key=lambda e: e['path'])
    refs = ['master'] + [f'part-{n}' for n in range(2, part_count + 1)]
    volume_by_path = {e['path']: refs[i] for i, bucket in enumerate(buckets) for e in bucket}
    all_images = [dict(e, install_ref=volume_by_path[e['path']]) for e in entries]
    for item in catalog['items']:
        item['install_ref'] = volume_by_path.get(item.get('path'))
    for item in all_images:
        item['github_url'] = f"https://github.com/{REPO}/blob/{item['install_ref']}/{item['path']}"
    install_rows = '\n'.join(f'| 第{i + 1}卷 | `{ref}` | {len(buckets[i])} | {sizes[i] / 1048576:.1f} MiB |'
                             for i, ref in enumerate(refs))
    global_categories = Counter(e['category'] for e in entries)
    category_rows = '\n'.join(f'| `{key}` | {global_categories[key]} | {original_manifest["categories"][key]["description"]} |'
                              for key in original_manifest['categories'])
    # Record the complete package first. The candidate volume commits descend from it.
    git('add', '-A')
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=ROOT).returncode:
        git('commit', '-m', 'Finalize curated Denia originals and provenance')
        git('push', 'origin', 'HEAD:asset-staging')
    parent = git('rev-parse', 'HEAD')
    publication = {'total_images': len(entries), 'total_bytes': sum(sizes), 'full_collection_commit': parent,
                   'archive_limit_bytes': 1024**3, 'volumes': []}
    for index, selected in enumerate(buckets):
        ref = refs[index]
        pack_id = 'denia-meme-pack' + (f'-{index + 1}' if index else '')
        selected_paths = {e['path'] for e in selected}
        manifest = copy.deepcopy(original_manifest)
        manifest.update(id=pack_id, name=f'达妮娅表情包 · 第{index + 1}卷',
            description=f'共{len(entries)}张达妮娅表情的第{index + 1}/{part_count}卷，本卷{len(selected)}张。原图、动画、分类及来源索引完整保留。')
        manifest['source']['ref'] = ref
        manifest['categories'] = {key: value for key, value in manifest['categories'].items()
                                  if any(e['category'] == key for e in selected)}
        semantic = copy.deepcopy(original_semantic)
        semantic['pack_id'] = pack_id
        semantic['images'] = {eid: value for eid, value in semantic['images'].items()
                              if value['relative_path'] in selected_paths}
        for label, value in [('manifest', manifest), ('semantic', semantic)]:
            Draft202012Validator(json.loads((ROOT / f'tools/{label}.schema.json').read_text(encoding='utf-8'))).validate(value)
        summary = dict(full_summary, volume={'number': index + 1, 'count': part_count, 'ref': ref,
            'images': len(selected), 'bytes': sizes[index], 'categories': dict(Counter(e['category'] for e in selected))})
        readme = f'''# 达妮娅 AstrBot 表情资源包

![预览](previews/cover.png)

共收录 **{len(entries)}张**去重后的达妮娅相关表情，分为 **{part_count}卷**。当前分支是**第{index + 1}卷，{len(selected)}张**。为适配插件单次安装归档的1 GiB上限，分卷保留原图及原动画，不进行压缩重编码。

## 从 GitHub 安装

插件 WebUI → 资源包 → 从 GitHub 安装，仓库均填写 **`{REPO}`**，包所在目录均填写 **`.`**；按照下表逐卷安装：

| 资源包 | 分支或版本 | 图片数 | 原图体积 |
| --- | --- | ---: | ---: |
{install_rows}

每卷拥有独立资源包ID，可同时安装。安装后在「设置中心 → 使用规则」将所需资源包绑定到人格或会话并保存。全部素材都在这个仓库，无需向官方索引提交PR。

## 全部分类

| 分类 | 总张数 | 适用场景 |
| --- | ---: | --- |
{category_rows}

## 收录范围与来源

处理范围为[呜哇小站](https://emoji.wuwa.games/tags/character-daniya)公开API列出的32个相关专辑，共{full_summary['source_records']}条记录，不声称覆盖整个互联网。混合角色合集经缩略图核对，排除{full_summary['excluded_non_target_records']}条不含目标角色的记录；其余{full_summary['included_source_records']}条按原文件SHA-256去除{full_summary['exact_duplicates_removed']}条重复，得到{len(entries)}张图片。不同尺寸、服装、动作或编码版本分别保留。

分类依据为原素材动作标签与模糊、混合角色条目的预览复核。`misc`表示暂无明确情绪标签，可继续在插件内语义化；来源标签不是逐帧视觉描述。语义元数据附有标签来源说明，不携带向量模型或服务商配置。

## 索引与授权

- [本卷逐图索引JSON](indexes/included-images.json) / [CSV](indexes/included-images.csv)
- [全部图片及所在分支](indexes/all-images.json)
- [统计](indexes/summary.json) / [来源记录](indexes/source-catalog.json) / [原专辑及画师](indexes/source-packs.json)
- [语义元数据](semantic_metadata.json) / [整理与排除记录](indexes/curation.json)

保留原始GIF/PNG/JPEG/WebP字节、来源专辑、资源标识、画师署名、哈希、尺寸和帧数。未去水印，未保存短效下载票据。使用者已确认取得图库素材打包上传公开GitHub仓库的许可，权利仍归原作者及相关权利人，详见[LICENSE.md](LICENSE.md)。这是玩家整理项目。

发布时验证图片可解码性、官方manifest与semantic JSON Schema、文件路径、SHA-256、语义条目ID和每卷归档大小。未声称在用户的AstrBot实例内完成聊天发送测试。
'''
        validation = '# 发布验证\n\n全部原图通过格式、尺寸、末帧可解码与SHA-256检查；本卷manifest及semantic通过官方JSON Schema。归档大小与逐图字节在构建时复核，低于插件1 GiB上限。\n\n' + json.dumps(summary, ensure_ascii=False, indent=2) + '\n'
        csv_stream = io.StringIO(newline='')
        writer = csv.writer(csv_stream)
        writer.writerow(['resource_id', 'pack_id', 'source_page', 'path', 'status', 'install_ref'])
        for item in catalog['items']:
            writer.writerow([item['id'], item['pack_id'], item['source_page'], item.get('path'), item['status'], item['install_ref']])
        changes = {'manifest.json': encoded(manifest), 'semantic_metadata.json': encoded(semantic),
            'README.md': readme.encode(), 'VALIDATION.md': validation.encode(),
            'indexes/included-images.json': encoded(selected), 'indexes/included-images.csv': image_csv(selected),
            'indexes/all-images.json': encoded(all_images), 'indexes/summary.json': encoded(summary),
            'indexes/source-catalog.json': encoded(catalog),
            'indexes/source-catalog.csv': ('\ufeff' + csv_stream.getvalue()).encode(),
            'previews/cover.png': cover(selected, index + 1, part_count)}
        with tempfile.TemporaryDirectory(prefix='denia-volume-') as directory:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / 'index'))
            git('read-tree', parent, env=env)
            removed = [e['path'] for e in entries if e['path'] not in selected_paths]
            if removed:
                git('update-index', '--force-remove', '--stdin', data=('\n'.join(removed) + '\n').encode(), env=env)
            for path, data in changes.items():
                blob = git('hash-object', '-w', '--stdin', data=data)
                git('update-index', '--add', '--cacheinfo', f'100644,{blob},{path}', env=env)
            tree = git('write-tree', env=env)
            commit = git('commit-tree', tree, '-p', parent, data=f'Prepare installable Denia volume {index + 1}/{part_count}\n'.encode())
            archive = Path(directory) / 'volume.zip'
            git('archive', '--format=zip', '-o', str(archive), commit)
            archive_bytes = archive.stat().st_size
            assert archive_bytes < 1024**3, f'Volume {index + 1} exceeds plugin limit'
            with zipfile.ZipFile(archive) as zipped:
                assert len(zipped.infolist()) < 20000
                assert sum(i.file_size for i in zipped.infolist()) < 4 * 1024**3
                actual_images = {name for name in zipped.namelist() if name.startswith('memes/') and not name.endswith('/')}
                assert actual_images == selected_paths
                assert len(semantic['images']) == len(selected)
                for e in selected:
                    assert hashlib.sha256(zipped.read(e['path'])).hexdigest() == e['sha256']
                for eid, e in semantic['images'].items():
                    assert eid == hashlib.sha256(f'{e["content_sha256"]}\0{e["category"]}\0{e["relative_path"]}'.encode()).hexdigest()
        candidate = f'release-part-{index + 1}-{parent[:8]}'
        git('push', 'origin', f'{commit}:refs/heads/{candidate}')
        volume = {'number': index + 1, 'ref': ref, 'candidate_ref': candidate, 'commit': commit,
                  'images': len(selected), 'bytes': sizes[index], 'archive_bytes': archive_bytes, 'pack_id': pack_id}
        publication['volumes'].append(volume)
        print(json.dumps(volume), flush=True)
    (ROOT / 'indexes/publication.json').write_bytes(encoded(publication))
    print('PUBLICATION_READY', json.dumps(publication), flush=True)


if __name__ == '__main__':
    main()
