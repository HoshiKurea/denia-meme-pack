import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / 'incoming'
INCOMING.mkdir(exist_ok=True)
(INCOMING / 'images').mkdir(exist_ok=True)
API = 'https://emoji.wuwa.games/apis/api.random-emoji.wuwa.games/v1alpha1/'
SESSION = requests.Session()
RECORDS_FILE = INCOMING / 'records.json'
records = json.loads(RECORDS_FILE.read_text(encoding='utf-8')) if RECORDS_FILE.exists() else []
by_id = {r['id']: r for r in records}
CI = os.environ.get('DENIA_CI') == '1'
MIXED = {'sigrika-chat-memes-20261010', 'official-resonators-ch14',
         'official-bili-new-world-static', 'official-bili-new-world-animated',
         'official-bili-2nd-anniversary-static', 'official-bili-2nd-anniversary-animated',
         'official-mini-daily', 'wuyanmao-collection-1',
         'backlog-20260927-g011-v1', 'chisa-aimisi-daniya'}
CATEGORIES = {
    'happy': '开心、欢呼、庆祝和轻快的积极回应。',
    'like': '喜欢、赞同、比心、亲近、抱抱或温柔互动。',
    'angry': '表达生气、抗议、差评或友善地佯装发火；不要用于真实威胁。',
    'sad': '难过、哭泣、委屈与遗憾；认真安慰时谨慎使用搞笑表情。',
    'confused': '疑问、不解、迷惑和需要进一步说明的场景。',
    'shy': '害羞、脸红、心虚或不好意思的回应。',
    'sleep': '困倦、睡觉、晚安、疲惫和休息。',
    'eat': '吃东西、喝饮料、食物和甜点相关的闲聊。',
    'work': '工作、学习、打字、努力做事和任务推进。',
    'greeting': '打招呼、挥手、欢迎、早安、道别和再见。',
    'sigh': '无语、无奈、叹气、扶额和轻微抱怨。',
    'surprised': '惊讶、震惊、受到惊吓或意料之外的情况。',
    'see': '观望、偷看、探头、盯着看和持续关注。',
    'thinking': '思考、沉思、摸下巴、大脑过载和暂时卡住。',
    'fool': '搞怪、整活、唱跳、玩耍和轻松活跃气氛。',
    'cute': '捏捏、戳戳、揉脸、卖萌和普通可爱互动。',
    'givemoney': '红包、付款、要米、硬币和打赏相关的玩笑；不代表真实付款请求。',
    'stop': '摇头、停止、拒绝、静音和表达轻微边界。',
    'reply': '说话、回应、通知、提示和指向对方等普通交流。',
    'relax': '放松、冒泡、日常闲聊和休息中的轻松回应。',
    'misc': '尚无明确情绪标签的其他达妮娅表情；优先用于选图浏览或进一步语义化。',
}
RULES = [
    ('sad', r'哭|流泪|伤心|难过|委屈|呜呜|崩溃|抹泪|瘪嘴|伤感|破防'),
    ('angry', r'生气|愤怒|恼怒|暴怒|差评|叉腰|揍|发火|愤愤|气鼓|拍桌|打你|炸毛|赌气|记仇|你小子|哈气|气死|中指'),
    ('shy', r'害羞|脸红|捂脸|含羞|心虚|羞涩|紧张'),
    ('sleep', r'睡|晚安|困|哈欠|疲惫|累了|催眠|Zzz|zzz|午休|燃尽|趴'),
    ('confused', r'问号|疑惑|疑问|迷惑|懵|不懂|看不懂|不解|诶|嗯\?'),
    ('surprised', r'惊|震惊|吓|哇哦|大受震撼|害怕|叹号|我擦'),
    ('sigh', r'无语|无奈|叹气|扶额|摊手|嫌弃|流汗|麻了|烦|压力|汗颜|汗'),
    ('greeting', r'打招呼|招手|挥手|早安|你好|拜拜|再见|欢迎|到达|敬礼|ciallo|宝在吗'),
    ('like', r'爱心|比心|喜欢|亲亲|亲吻|抱抱|贴贴|宠溺|合影|送花|点赞|比耶|正确|谢谢|同意|点头|礼物|玫瑰|情书|wink|花花|yes|疯狂暗示|就是这个|眨眼|自我安慰'),
    ('eat', r'吃|喝|啃|饮|补水|茶|薯片|蛋糕|馋|刀叉|筷子|饼|冰棍|汽水|棒冰|冰淇淋|干杯|布丁|葱卷|炸虾|叼鱼|美味|奶酪|喂奶'),
    ('givemoney', r'红包|钱|刷卡|要米|硬币|打赏'),
    ('stop', r'停止|静音|摇头|不行|勿扰|拒绝|比x'),
    ('work', r'工作|学习|读书|打字|键盘|努力|认真|干活|画板|记录|书呆子|驾驶|指点|记下|看好书|手机'),
    ('thinking', r'思考|沉思|摸下巴|烧脑|脑袋|宕机|头疼|头痛|CPU|cpu|摸鱼|加载|头晕|动脑筋|鬼点子|开窍'),
    ('see', r'偷看|探头|盯|观察|围观|就这么看|看戏|呆|看看|看破|愣|冷脸萌'),
    ('reply', r'通知|提示|说话|说教|期待|指$'),
    ('relax', r'带薪|冒泡|闲置'),
    ('happy', r'开心|高兴|欢呼|庆祝|鼓掌|笑|快乐|欢快|打call|撒花|胜利|耶|加油|噗呲'),
    ('fool', r'唱歌|跳舞|舞蹈|摆动|扭|摇摆|转圈|滚|跑|跳|吐舌|伸舌|搞怪|整活|打游戏|魔法|发电|按钮|拍击|墨镜|小丑|音乐|吉他|摇铃|电风扇|反转|复活节|六七|拍蝇|枪|撬棍|拖鞋|敲头|扩音器|得分|刀|启动|阴险|中二|超电磁炮|太鼓|替身|火把|盖帽|拖走|吐息|击毙|浇水|胶带|垃圾桶|喷剂|死亡|烧|坐牢|Bug|Popcat|Raid|一切都好|荧光棒|可乐'),
    ('cute', r'捏|戳|摸头|摸摸|揉|rua|可爱|乖|被击中|按|脑瓜崩|黄油|挤脸|碰鼻子|舔舔|扣脸|好多猫|喵|嗷呜|纸箱'),
]


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def category(alt):
    action = alt.rsplit('达妮娅_', 1)[-1]
    if action == alt:
        action = re.sub(r'^.*(?:表情包|合集)\s*', '', alt)
    return next((key for key, pattern in RULES if re.search(pattern, action)), 'misc')


def checkpoint(message):
    dump(RECORDS_FILE, records)
    dump(INCOMING / 'progress.json', {'downloaded': sum(r.get('downloaded', False) for r in records),
         'records': len(records), 'bytes': sum(r.get('bytes', 0) for r in records), 'message': message})
    print(message, flush=True)
    if CI:
        subprocess.run(['git', 'add', 'incoming'], check=True, cwd=ROOT)
        if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=ROOT).returncode:
            subprocess.run(['git', 'commit', '-m', message], check=True, cwd=ROOT)
            subprocess.run(['git', 'push', 'origin', 'HEAD:asset-staging'], check=True, cwd=ROOT)


def api_get(resource, params):
    response = SESSION.get(API + resource, params=params, timeout=45)
    response.raise_for_status()
    return response.json()


def download(item):
    old = by_id.get(item['id'])
    if old and old.get('downloaded') and (ROOT / old['local_file']).is_file():
        return old
    clean = {k: v for k, v in item.items() if k not in ('url', 'expiresAt')}
    try:
        for attempt in range(3):
            try:
                response = requests.get(item['url'], timeout=(20, 120))
                break
            except requests.exceptions.ChunkedEncodingError:
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)
        if response.status_code != 200:
            return dict(clean, downloaded=False, status=response.status_code)
        data = response.content
        if len(data) >= 99_000_000:
            return dict(clean, downloaded=False, status='file_too_large')
        with Image.open(io.BytesIO(data)) as im:
            fmt = im.format.lower()
            if fmt not in ('gif', 'png', 'jpeg', 'webp'):
                return dict(clean, downloaded=False, status='unsupported_format')
            size = list(im.size)
            frames = getattr(im, 'n_frames', 1)
            im.seek(frames - 1)
            im.load()
        ext = 'jpg' if fmt == 'jpeg' else fmt
        digest = hashlib.sha256(data).hexdigest()
        relative = f'incoming/images/{digest}.{ext}'
        path = ROOT / relative
        if not path.exists():
            path.write_bytes(data)
        return dict(clean, downloaded=True, local_file=relative, sha256=digest,
                    bytes=len(data), actual_format=ext, size=size, frames=frames)
    except Exception as exc:
        return dict(clean, downloaded=False, status=type(exc).__name__)


def load_labels(packs):
    path = INCOMING / 'labels.json'
    labels = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    for pack in packs['items']:
        if any(v.get('pack') == pack['slug'] for v in labels.values()):
            continue
        response = SESSION.get(pack['sourceUrl'], timeout=45)
        response.raise_for_status()
        response.encoding = 'utf-8'
        for block in re.findall(r'<script[^>]*class="wuwa-emoji-manifest"[^>]*>(.*?)</script>', response.text, re.S):
            for item in json.loads(block).get('items', []):
                labels[item['resourceId']] = {'alt': item.get('alt', ''), 'pack': pack['slug']}
        dump(path, labels)
        time.sleep(.2)
    return labels


def make_sheets():
    labels = json.loads((INCOMING / 'labels.json').read_text(encoding='utf-8'))
    review = []
    for record in sorted(records, key=lambda r: (r.get('pack', {}).get('slug', ''), r['id'])):
        if not record.get('downloaded'):
            continue
        alt = labels.get(record['id'], {}).get('alt', '')
        if record['pack']['slug'] in MIXED or category(alt) == 'misc':
            review.append({'id': record['id'], 'file': record['local_file'],
                           'alt': alt, 'pack': record['pack']['slug'], 'suggested': category(alt)})
    directory = INCOMING / 'review'
    directory.mkdir(exist_ok=True)
    for offset in range(0, len(review), 56):
        sheet = Image.new('RGB', (1536, 1624), '#f2f2f2')
        draw = ImageDraw.Draw(sheet)
        for local, item in enumerate(review[offset:offset + 56]):
            x, y = local % 8 * 192, local // 8 * 232
            with Image.open(ROOT / item['file']) as im:
                im.seek(getattr(im, 'n_frames', 1) // 3)
                frame = im.convert('RGBA')
                frame.thumbnail((180, 180))
                sheet.paste(frame, (x + (192 - frame.width) // 2, y + 4), frame)
            draw.text((x + 5, y + 188), str(offset + local + 1), fill='#000')
            draw.text((x + 5, y + 204), item['pack'][:25], fill='#555')
        sheet.save(directory / f'sheet-{offset // 56 + 1:02}.jpg', quality=88)
    for i, item in enumerate(review, 1):
        item['number'] = i
    dump(directory / 'index.json', review)
    print('REVIEW', len(review), 'SHEETS', (len(review) + 55) // 56, flush=True)


def collect():
    packs = api_get('packs', {'character': '达妮娅', 'page': 1, 'size': 50})
    dump(INCOMING / 'packs.json', packs)
    load_labels(packs)
    page, total = 1, 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        while True:
            payload = api_get('emojis', {'character': '达妮娅', 'page': page, 'size': 50})
            total = payload['total']
            print('PAGE', page, 'TOTAL', total, flush=True)
            for offset in range(0, len(payload['items']), 4):
                batch = list(pool.map(download, payload['items'][offset:offset + 4]))
                for record in batch:
                    if record['id'] in by_id:
                        records[records.index(by_id[record['id']])] = record
                    else:
                        records.append(record)
                    by_id[record['id']] = record
                dump(RECORDS_FILE, records)
                if any(r.get('status') in (401, 403, 429) for r in batch):
                    checkpoint('Stop Denia collection after access or quota refusal')
                    raise RuntimeError('Access/quota refusal; collection stopped without bypass')
                time.sleep(.15)
            if page % 2 == 0:
                checkpoint(f'Checkpoint Denia collection: {sum(r.get("downloaded", False) for r in records)}/{total}')
            if not payload.get('hasNext'):
                break
            page += 1
    failed = [r for r in records if not r.get('downloaded')]
    checkpoint(f'Denia collection: {len(records) - len(failed)}/{total} downloaded')
    make_sheets()
    dump(INCOMING / 'summary.json', {'expected': total, 'records': len(records),
         'downloaded': len(records) - len(failed), 'failed': [{'id': r['id'], 'status': r.get('status')} for r in failed],
         'unique_files': len(list((INCOMING / 'images').iterdir()))})
    if failed or len(records) != total:
        raise RuntimeError('Collection incomplete; see incoming/summary.json')


def finalize(curation):
    labels = json.loads((INCOMING / 'labels.json').read_text(encoding='utf-8'))
    reviewed = json.loads((INCOMING / 'review/index.json').read_text(encoding='utf-8'))
    exclude_numbers = set(curation.get('exclude_numbers', []))
    excluded_ids = {r['id'] for r in reviewed if r['number'] in exclude_numbers}
    excluded_hashes = {r['sha256'] for r in records if r['id'] in excluded_ids}
    exclude = {r['id'] for r in records if r['sha256'] in excluded_hashes}
    overrides = {r['id']: curation.get('categories', {}).get(str(r['number'])) for r in reviewed}
    groups = defaultdict(list)
    for record in records:
        if record['id'] not in exclude:
            assert record.get('downloaded'), record['id']
            groups[record['sha256']].append(record)
    # Remove only the known package image directory inside this repository.
    image_root = (ROOT / 'memes').resolve()
    assert image_root.parent == ROOT.resolve()
    shutil.rmtree(image_root)
    image_root.mkdir()
    entries = []
    semantic = {'schema_version': '2.0', 'pack_id': 'denia-meme-pack', 'images': {}}
    counts = Counter()
    for digest, aliases in sorted(groups.items()):
        representative = next((r for r in aliases if overrides.get(r['id'])),
            next((r for r in aliases if category(labels.get(r['id'], {}).get('alt', '')) != 'misc'), aliases[0]))
        alt = labels.get(representative['id'], {}).get('alt', '')
        selected = overrides.get(representative['id']) or category(alt)
        assert selected in CATEGORIES
        relative = f'memes/{selected}/{digest[:24]}.{representative["actual_format"]}'
        destination = ROOT / relative
        destination.parent.mkdir(exist_ok=True)
        shutil.move(ROOT / representative['local_file'], destination)
        counts[selected] += 1
        source_labels = sorted(set(labels.get(r['id'], {}).get('alt', '') for r in aliases))
        source_labels = [re.sub(r'_?20\d\d-\d\d-\d\d(?:-\d\d){0,3}', '', s).strip() for s in source_labels if s]
        sources = [{'resource_id': r['id'], 'pack': r['pack']['title'], 'pack_id': r['pack']['slug'],
                    'source_page': r['sourceUrl'], 'artists': [a['name'] for a in r.get('artists', [])]}
                   for r in aliases]
        entry = {'path': relative, 'sha256': digest, 'category': selected, 'source_labels': source_labels,
                 'size': representative['size'], 'frames': representative['frames'],
                 'bytes': representative['bytes'], 'sources': sources,
                 'classification': 'source-label keywords plus manual review of ambiguous and mixed-character entries'}
        entries.append(entry)
        eid = hashlib.sha256(f'{digest}\0{selected}\0{relative}'.encode()).hexdigest()
        caption = ('预览分类：' if overrides.get(representative['id']) else '标签分类：') + CATEGORIES[selected]
        if source_labels:
            caption += ' 来源标签：' + '；'.join(source_labels)
        semantic['images'][eid] = {'entry_id': eid, 'content_sha256': digest, 'relative_path': relative,
            'category': selected, 'caption': caption, 'caption_status': 'done' if source_labels or overrides.get(representative['id']) else 'pending',
            'tags': ['达妮娅', selected], 'provenance': '原素材标签；分类根据标签关键词及预览人工复核，不冒充逐帧描述。'}
    assert len(entries) == len(groups)
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    manifest.update(name='达妮娅表情包', version='1.0.0',
        description=f'达妮娅图库素材整理：{len(entries)}张去重图片，{len(counts)}个聊天语义分类；附来源、署名、哈希与标签索引。',
        author='HoshiKurea（整理）；素材署名见来源索引',
        categories={key: {'description': CATEGORIES[key]} for key in CATEGORIES if counts[key]})
    dump(ROOT / 'manifest.json', manifest)
    dump(ROOT / 'semantic_metadata.json', semantic)
    dump(ROOT / 'indexes/included-images.json', entries)
    summary = {'source_records': len(records), 'excluded_non_target_records': len(exclude),
               'included_source_records': sum(len(v) for v in groups.values()), 'unique_images': len(entries),
               'exact_duplicates_removed': sum(len(v) - 1 for v in groups.values()),
               'categories': dict(counts), 'total_bytes': sum(e['bytes'] for e in entries)}
    dump(ROOT / 'indexes/summary.json', summary)
    dump(ROOT / 'indexes/source-packs.json', json.loads((INCOMING / 'packs.json').read_text(encoding='utf-8')))
    by_hash = {e['sha256']: e['path'] for e in entries}
    dump(ROOT / 'indexes/source-catalog.json', {'total': len(records), 'indexed_at': '2026-10-22',
         'source': 'https://emoji.wuwa.games/api', 'items': [
             {'id': r['id'], 'pack_id': r['pack']['slug'], 'format': r['actual_format'],
              'source_page': r['sourceUrl'], 'path': by_hash.get(r['sha256']),
              'status': 'excluded_non_target' if r['id'] in exclude else 'included'} for r in records]})
    with (ROOT / 'indexes/source-catalog.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['resource_id', 'pack_title', 'artists', 'source_page', 'path', 'status'])
        for r in records:
            writer.writerow([r['id'], r['pack']['title'], ' / '.join(a['name'] for a in r.get('artists', [])),
                             r['sourceUrl'], by_hash.get(r['sha256'], ''),
                             'excluded_non_target' if r['id'] in exclude else 'included'])
    with (ROOT / 'indexes/included-images.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['path', 'category', 'labels', 'artists', 'source_pages', 'sha256', 'bytes', 'frames'])
        for entry in entries:
            writer.writerow([entry['path'], entry['category'], ' / '.join(entry['source_labels']),
                ' / '.join(sorted({a for s in entry['sources'] for a in s['artists']})),
                ' / '.join(sorted({s['source_page'] for s in entry['sources']})), entry['sha256'], entry['bytes'], entry['frames']])
    # Verify all actual image bytes, path identities and supplied schema definitions.
    for label, value in [('manifest', manifest), ('semantic', semantic)]:
        Draft202012Validator(json.loads((ROOT / f'tools/{label}.schema.json').read_text(encoding='utf-8'))).validate(value)
    for eid, entry in semantic['images'].items():
        path = ROOT / entry['relative_path']
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == entry['content_sha256']
        assert eid == hashlib.sha256(f'{digest}\0{entry["category"]}\0{entry["relative_path"]}'.encode()).hexdigest()
    # The local draft/source list is retained as provenance; raw duplicate images and QA sheets are removed.
    dump(ROOT / 'indexes/curation.json', [{'resource_id': r['id'], 'source_label': r['alt'],
         'excluded': r['id'] in exclude, 'category_override': overrides.get(r['id'])} for r in reviewed])
    shutil.rmtree(INCOMING)
    (ROOT / 'LICENSE.md').write_text('''# 素材与整理文件说明\n\n使用者于2026-10-22确认已取得图库素材打包上传公开GitHub仓库的许可。本仓库据此整理，未声称素材版权转移，也不授予超出原许可的商业或二次授权。\n\n各图片来源、原专辑和公开画师署名见 indexes/included-images.json 与 CSV；原素材权利仍归库洛游戏、相应创作者或其他权利人所有。请保留署名、按原许可范围用于个人非商业聊天，不倒卖或冒充官方。\n\n本仓库未将全部图片统一改授MIT或CC许可。若权利人发现归属或收录范围问题，可在本仓库Issue提出具体资源与权属信息，维护者可核对处理。\n''', encoding='utf-8')
    rows = '\n'.join(f'| `{key}` | {counts[key]} | {CATEGORIES[key]} |' for key in CATEGORIES if counts[key])
    (ROOT / 'README.md').write_text(f'''# 达妮娅 AstrBot 表情资源包\n\n![预览](previews/cover.png)\n\n收录 **{len(entries)}张**去重后的达妮娅相关表情，按 **{len(counts)}个类别**整理，保留原始GIF/PNG/JPEG/WebP文件。处理范围为[呜哇小站](https://emoji.wuwa.games/tags/character-daniya)公开API列出的32个相关专辑，不声称覆盖整个互联网。\n\n## 安装\n\n在表情包管理插件「从GitHub安装」中填写：\n\n- 仓库：`HoshiKurea/denia-meme-pack`\n- 分支：`master`\n- 包所在目录：`.`\n\n安装后在「设置中心 → 使用规则」绑定人格或会话并保存。普通分类模式可直接使用；逐图索引附来源标签，语义模式如需更细的视觉描述可在插件内进一步处理。本仓库不携带向量模型或服务商配置。\n\n## 收录与分类\n\n| 分类 | 数量 | 适用场景 |\n| --- | ---: | --- |\n{rows}\n\n源API共列出{len(records)}条相关记录；混合角色合集经预览核对，排除{len(exclude)}条不含目标角色的记录。其余{summary['included_source_records']}条按原文件SHA-256去除{summary['exact_duplicates_removed']}条重复，得到{len(entries)}张。不同尺寸、服装、动作或编码版本可能仍分别保留，不声称完成像素级近似去重。\n\n主要根据原素材动作标签分类，模糊标签和混合角色条目另作预览复核。`misc`用于未能明确判定情绪的图片；来源标签不是逐帧视觉描述。\n\n## 索引\n\n- [逐图索引JSON](indexes/included-images.json) / [CSV](indexes/included-images.csv)\n- [统计](indexes/summary.json)\n- [原始来源记录索引](indexes/source-catalog.json) / [专辑索引](indexes/source-packs.json)\n- [语义元数据](semantic_metadata.json)\n\n保留来源专辑、资源标识、画师署名、原文件哈希、尺寸和帧数。未保存短效下载票据；未去水印、重画或重新编码原图。使用者已确认取得图库素材打包上传许可，权利说明见[LICENSE.md](LICENSE.md)。这是玩家整理项目，未向官方社区索引提交PR。\n\n## 验证\n\n发布流程检查官方manifest/semantic JSON Schema、实际文件路径、图片可解码性、SHA-256及语义条目ID。此为资源包结构与文件完整性验证，未声称在用户AstrBot实例内完成聊天发送测试。\n''', encoding='utf-8')
    (ROOT / 'VALIDATION.md').write_text('# 发布前校验\n\n2026-10-22：全部图片下载后验证格式、尺寸与末帧可解码；按原文件SHA-256去重。manifest和semantic元数据通过官方JSON Schema，逐图内容哈希、分类路径和entry_id一致。\n\n'+json.dumps(summary, ensure_ascii=False, indent=2)+'\n\n分类依据为来源动作标签与缩略图人工复核，未进行完整逐帧情绪审核。\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    curation_path = ROOT / 'tools/curation.json'
    if curation_path.exists() and not RECORDS_FILE.exists():
        print('Already finalized; no source checkpoint to rebuild. Package left unchanged.')
    elif curation_path.exists():
        finalize(json.loads(curation_path.read_text(encoding='utf-8')))
    else:
        collect()
