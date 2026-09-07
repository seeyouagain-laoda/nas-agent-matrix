from astrbot.api.star import Context, Star, register
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain, Image, Reply
from astrbot.core.star.filter.command import GreedyStr
import aiohttp
import re
import os
import glob
import shutil
import random
import time
import json
import base64

RELAY_URL = "http://<NAS_LAN_IP>:8910/run"
IMAGE_URL = "http://<NAS_LAN_IP>:8910/image"
IMAGE_GEMINI_URL = "http://<NAS_LAN_IP>:8910/image-gemini"
RELAY_TOKEN = "<RELAY_TOKEN>"

MEME_DIR = "/AstrBot/data/memes"
INDEX_PATH = "/AstrBot/data/memes/meme_index.json"
LOCAL_PREFIX = "<NAS_DATA_DIR>/astrbot_data"
LOCAL_REPLACE = "/AstrBot/data"
IMG_EXT = r"\.(?:jpg|jpeg|png|gif|webp|bmp)"
URL_RE = re.compile(r"https?://\S+?" + IMG_EXT, re.I)
FILE_RE = re.compile(r"(?!\w)(/\S+?" + IMG_EXT + ")", re.I)


@register(
    name="openclaw_controller",
    author="WorkBuddy",
    desc="鲸鱼娘(QQ)通过 /任务 执行 OpenClaw，/梗图 按标签发 whale-chan 本地表情包（935张），/生成 默认走 NAS 浏览器 Gemini 生图（附图即参考图）、失败自动兜底 PokeAPI，/生成参考 显式参考图生图（可先发描述、再单独发参考图，多轮等待），结果图片直接显示为图",
    version="1.4.4",
)
class OpenClawController(Star):
    def __init__(self, context: Context) -> None:
        self.context = context
        self._pending_ref = {}   # session_id -> {"prompt": str, "ts": float} 等待用户单独发参考图
        self._pending_ttl = 300  # 参考图等待超时（秒）

    def _load_index(self):
        try:
            with open(INDEX_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _local_pics(self):
        pats = [os.path.join(MEME_DIR, "*" + ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")]
        pics = []
        for p in pats:
            pics += glob.glob(p)
        return [p for p in pics if not p.endswith("meme_index.json")]

    def _meme_image(self, v):
        """优先返回本地文件路径（in-container），否则回退 CDN url。"""
        local = v.get("local", "")
        if local and os.path.exists(local):
            return ("file", local)
        url = v.get("preview") or v.get("original", "")
        return ("url", url)

    def _emit_meme(self, event, v):
        kind, val = self._meme_image(v)
        if kind == "file":
            return event.chain_result([Image.fromFileSystem(val)])
        return event.image_result(val)

    # ---- 图片提取 / 落盘 ----
    def _extract_images(self, event):
        """从消息链（含 Reply 引用链）提取 Image 组件。"""
        chain = getattr(getattr(event, "message_obj", None), "message", []) or []
        imgs = []
        for comp in chain:
            if isinstance(comp, Image):
                imgs.append(comp)
            elif isinstance(comp, Reply) and getattr(comp, "chain", None):
                for c2 in comp.chain:
                    if isinstance(c2, Image):
                        imgs.append(c2)
        return imgs

    async def _ref_image_b64(self, img):
        """把 Image 组件解析为 base64 字符串（读取下载后的文件字节），直传 relay 解码。失败返回 None。"""
        src = None
        try:
            src = await img.convert_to_file_path()
        except Exception:
            src = None
        if src and os.path.exists(src):
            try:
                with open(src, "rb") as f:
                    return base64.b64encode(f.read()).decode("ascii")
            except Exception:
                return None
        b = getattr(img, "base64", None)
        if b:
            return b
        return None

    @filter.command("任务")
    async def renwu(self, event: AstrMessageEvent, task: GreedyStr):
        task = str(task).strip()
        if not task:
            yield event.plain_result("用法：/任务 <任务描述>\n例如：/任务 帮我查一下 NAS 上正在运行的 docker 容器并简要汇报")
            return
        yield event.plain_result("\U0001F433 鲸鱼娘已把任务交给 OpenClaw 执行中\u2026")
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(RELAY_URL, json={"task": task}, headers={"X-Relay-Token": RELAY_TOKEN}, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    data = await resp.json()
        except Exception as e:
            yield event.plain_result("\u26a0\ufe0f 调用 OpenClaw 失败：%s" % e)
            return
        if not data.get("ok"):
            yield event.plain_result("\u26a0\ufe0f OpenClaw 执行未返回有效结果：%s" % (data.get("error") or "未知错误"))
            return
        text = (data.get("text") or "").strip()
        calls = data.get("calls", 0)
        images = data.get("images") or []
        tail = "\n—— 由 OpenClaw 执行（调用工具 %d 次）" % calls if calls else ""
        chain = []
        if text:
            t = text if len(text) <= 3000 else text[:3000] + "\n\u2026(结果过长已截断)"
            chain.append(Plain(t + tail))
        for it in images:
            v = it.get("value", "")
            if not v:
                continue
            if it.get("type") == "url":
                chain.append(Image.fromURL(v))
            else:
                if v.startswith(LOCAL_PREFIX):
                    v = LOCAL_REPLACE + v[len(LOCAL_PREFIX):]
                chain.append(Image.fromFileSystem(v))
        if chain:
            yield event.chain_result(chain)
        else:
            yield event.plain_result("（OpenClaw 没有返回可读内容）" + tail)

    @filter.command("梗图")
    async def meme(self, event: AstrMessageEvent, arg: GreedyStr):
        kw = str(arg).strip()
        # 本地图库（手动丢进 memes/ 的非索引图）
        if kw == "本地":
            pics = self._local_pics()
            if not pics:
                yield event.plain_result("\U0001F433 本地梗图库空空如也，把图片丢进 NAS 的 <NAS_DATA_DIR>/memes 即可。")
                return
            yield event.image_result(random.choice(pics))
            return
        idx = self._load_index()
        if not idx:
            pics = self._local_pics()
            if pics:
                yield event.image_result(random.choice(pics))
            else:
                yield event.plain_result("\U0001F433 没找到表情包索引，先确认 meme_index.json 已部署到 <NAS_DATA_DIR>/memes。")
            return
        memes = idx.get("memes", {})
        if not kw:
            num = random.choice(list(memes.keys()))
            yield self._emit_meme(event, memes[num])
            return
        # 关键词匹配（含同义词扩展）
        kwl = kw.lower()
        terms = set([kwl])
        syn = idx.get("synonyms", {})
        if kw in syn:
            terms.update(t.lower() for t in syn[kw])
        hits = []
        for num, v in memes.items():
            text = (v.get("alt", "") + " " + v.get("alt_en", "") + " " + v.get("story_zh", "")).lower()
            if any(t in text for t in terms):
                hits.append(num)
        if not hits:
            yield event.plain_result("\U0001F433 没找到「%s」相关的图，换个词试试？可用标签如：高兴/悲伤/生气/震惊/打招呼/嘲讽/无奈/害怕/厌恶/告别/羞愧/摸鱼/吃饭/傲娇/认错/委屈" % kw)
            return
        num = random.choice(hits)
        yield self._emit_meme(event, memes[num])

    async def _do_gemini_gen(self, event: AstrMessageEvent, prompt: str, require_ref: bool = False, ref_b64: str = None):
        """走 NAS 浏览器 Gemini 生图；若消息带图则作为参考图（reference_image）。失败兜底 PokeAPI。"""
        if not ref_b64:
            imgs = self._extract_images(event)
            if imgs:
                ref_b64 = await self._ref_image_b64(imgs[0])
        if require_ref and not ref_b64:
            yield event.plain_result("用法：发一张参考图，配文字「/生成参考 <画面描述>」。\n例如：/生成参考 改成二次元蓝发鲸鱼娘风格")
            return
        if ref_b64:
            yield event.plain_result("\U0001F433 检测到参考图，鲸鱼娘正在用 Gemini（参考图生图）\u2026")
        else:
            yield event.plain_result("\U0001F433 鲸鱼娘正在用 Gemini（fygo 浏览器）生图\u2026")
        try:
            payload = {"prompt": prompt}
            if ref_b64:
                payload["reference_image_b64"] = ref_b64
            async with aiohttp.ClientSession() as sess:
                async with sess.post(IMAGE_GEMINI_URL, json=payload, headers={"X-Relay-Token": RELAY_TOKEN}, timeout=aiohttp.ClientTimeout(total=240)) as resp:
                    gdata = await resp.json()
        except Exception as e:
            gdata = {"ok": False, "error": str(e)}
        if gdata.get("ok"):
            cp = gdata.get("container_path", "")
            if cp and os.path.exists(cp):
                yield event.chain_result([Plain("\U0001F433 鲸鱼娘给你画好啦～（Gemini）已存进本地图库 <NAS_DATA_DIR>/memes/generated"), Image.fromFileSystem(cp)])
                return
            gdata = {"ok": False, "error": "本地文件未找到：" + str(cp)}
        # 兜底：PokeAPI（参考图模式下仅作纯文生图兜底，不传参考图）
        yield event.plain_result("\u26a0\ufe0f Gemini 生图失败（%s），自动切换 PokeAPI 兜底\u2026" % (gdata.get("error") or "未知"))
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(IMAGE_URL, json={"prompt": prompt, "model": "gpt-image-2", "size": "1024x1024"}, headers={"X-Relay-Token": RELAY_TOKEN}, timeout=aiohttp.ClientTimeout(total=150)) as resp:
                    pdata = await resp.json()
        except Exception as e:
            yield event.plain_result("\u26a0\ufe0f PokeAPI 兜底也失败：%s" % e)
            return
        if not pdata.get("ok"):
            yield event.plain_result("\u26a0\ufe0f 生图失败：%s" % (pdata.get("error") or "未知"))
            return
        cp = pdata.get("container_path", "")
        if cp and os.path.exists(cp):
            yield event.chain_result([Plain("\U0001F433 鲸鱼娘给你画好啦～（PokeAPI 兜底）已存进本地图库 <NAS_DATA_DIR>/memes/generated"), Image.fromFileSystem(cp)])
        else:
            yield event.plain_result("\u26a0\ufe0f 生图成功但本地文件未找到：%s" % cp)

    @filter.command("生成")
    async def shengcheng(self, event: AstrMessageEvent, arg: GreedyStr):
        raw = str(arg).strip()
        if not raw:
            yield event.plain_result("用法：\n/生成 <画面描述>  （默认 NAS 浏览器 Gemini，失败自动兜底 PokeAPI；附一张图即作为参考图）\n/生成 gemini <画面描述>  （同默认，显式走浏览器 Gemini）\n/生成 api <画面描述>  （强制走 PokeAPI gpt-image-2）\n/生成参考 <画面描述>  （显式参考图生图：可同条附图，或先发描述再单独发图）\n例如：/生成 一只戴眼镜的蓝色鲸鱼娘，二次元风格，白色背景")
            return
        # 模型路由：默认浏览器 Gemini 优先；前缀 api/poke → 强制 PokeAPI
        prompt = raw
        force_api = False
        low = raw.lower()
        if low.startswith("api "):
            force_api = True
            prompt = raw[4:].strip()
        elif low.startswith("poke "):
            force_api = True
            prompt = raw[5:].strip()
        elif low.startswith("gemini "):
            prompt = raw[7:].strip()  # 显式 gemini 前缀，等价于默认（浏览器 Gemini）
        if not prompt:
            yield event.plain_result("\u26a0\ufe0f 缺少画面描述。")
            return

        if force_api:
            # 强制 PokeAPI
            yield event.plain_result("\U0001F433 鲸鱼娘正在用 PokeAPI（gpt-image-2）生图\u2026")
            try:
                async with aiohttp.ClientSession() as sess:
                    async with sess.post(IMAGE_URL, json={"prompt": prompt, "model": "gpt-image-2", "size": "1024x1024"}, headers={"X-Relay-Token": RELAY_TOKEN}, timeout=aiohttp.ClientTimeout(total=150)) as resp:
                        pdata = await resp.json()
            except Exception as e:
                yield event.plain_result("\u26a0\ufe0f 生图调用失败：%s" % e)
                return
            if not pdata.get("ok"):
                yield event.plain_result("\u26a0\ufe0f 生图失败：%s" % (pdata.get("error") or "未知"))
                return
            cp = pdata.get("container_path", "")
            if cp and os.path.exists(cp):
                yield event.chain_result([Plain("\U0001F433 鲸鱼娘给你画好啦～已存进本地图库 <NAS_DATA_DIR>/memes/generated"), Image.fromFileSystem(cp)])
            else:
                yield event.plain_result("\u26a0\ufe0f 生图成功但本地文件未找到：%s" % cp)
        else:
            # 第一选项：浏览器 Gemini（带图即参考图）
            async for r in self._do_gemini_gen(event, prompt, require_ref=False):
                yield r

    def _session_key(self, event: AstrMessageEvent):
        try:
            return event.get_session_id()
        except Exception:
            try:
                return event.get_sender_id()
            except Exception:
                return "default"

    @filter.command("生成参考")
    async def shengcheng_ref(self, event: AstrMessageEvent, arg: GreedyStr):
        raw = str(arg).strip()
        prompt = raw if raw else "以此图为参考进行二次创作，保持主体与构图，提升画面质感与细节。"
        imgs = self._extract_images(event)
        if imgs:
            # 同一条消息已带参考图：直接生图
            async for r in self._do_gemini_gen(event, prompt, require_ref=True):
                yield r
            return
        # 本轮只有描述、没图：进入等待参考图状态，等用户随后单独发图
        key = self._session_key(event)
        self._pending_ref[key] = {"prompt": prompt, "ts": time.time()}
        yield event.plain_result("\U0001F433 收到描述啦～那参考图片呢？请直接发我一张参考图（不用带命令），鲸鱼娘拿到就开画。\n（5 分钟内有效，超时请重发 /生成参考 <描述>）")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def _on_any_message(self, event: AstrMessageEvent):
        """捕获「/生成参考 <描述>」之后用户单独发来的参考图，完成多轮生图。命令消息由 command handler 处理；本 handler 仅在有待定且收到图时才动作，其余消息直接 return，无副作用。"""
        key = self._session_key(event)
        pending = self._pending_ref.get(key)
        if not pending:
            return
        if time.time() - pending.get("ts", 0) > self._pending_ttl:
            self._pending_ref.pop(key, None)
            event.stop_event()
            yield event.plain_result("⚠️ 参考图等待已超时（5 分钟），请重新发 /生成参考 <描述>。")
            return
        imgs = self._extract_images(event)
        if not imgs:
            return
        event.stop_event()
        img = imgs[0]
        ref_b64 = await self._ref_image_b64(img)
        if not ref_b64:
            yield event.plain_result("⚠️ 没认出图片内容（已记录，鲸鱼娘正在修）。")
            return
        self._pending_ref.pop(key, None)
        async for r in self._do_gemini_gen(event, pending["prompt"], require_ref=False, ref_b64=ref_b64):
            yield r
