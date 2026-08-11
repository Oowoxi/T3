import random
import time
import re
import json
import os
import asyncio
import requests
import difflib
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, JobQueue
from telegram.error import BadRequest, RetryAfter
from collections import defaultdict, Counter
from cachetools import TTLCache, LRUCache
from functools import lru_cache
import aiohttp

BOT_TOKEN = "8494424963:AAFUkn_z3RUgDQ2sWG4PxewyPtzN39mAwYk"
OWNER_ID = 5562144078
REQUIRED_CHANNEL = "@vvnusn"
REQUIRED_CHANNEL_LINK = "https://t.me/vvnusn"
BOT_COMMAND_TEXTS = {
    "عرض", "مقالات", "بوت", "تفعيل الدقة", "تعطيل الدقة", "عرض جميع الاوامر", "جميع الاوامر", "الاوامر كاملة",
    "خصص", "المحفوظ", "المستخدمين", "المحظورين", "عرض الكل", "الإشراف", "إدارة", "اداره", "ادارة", "ايديه",
    "جمم", "ويكي", "مس", "اص", "صج", "شك", "جش", "قص", "نص", "طب", "كرر", "شرط", "فكك", "دبل", "تر", "عكس", "فر", "E", "e", "رق", "حر", "جب", "ريست", "تلقائي",
    "الصدارة", "توب", "أيدي الصدارة", "ايدي الصدارة", "أيدي صدارة الجوال", "ايدي صدارة الجوال", "أيدي صدارة خارجي", "ايدي صدارة خارجي",
    "باند", "تقييد", "كتم", "الغاء تقييد", "الغاء باند", "فك باند", "طرد", "الغاء كتم",
    "اطلع من هنا", "طرد الكل", "اطرد الكل", "روابط القروبات",
    "وقف هنا", "شغل هنا", "أيدي الإشراف", "نزل مالك"
}

message_cache = {}
last_save_time = time.time()
save_interval = 60.0
dirty_count = 0
max_dirty_count = 200

file_cache = LRUCache(maxsize=50)
admin_cache = LRUCache(maxsize=50)
banned_cache = LRUCache(maxsize=100)

chat_locks = defaultdict(asyncio.Lock)
last_command_time = defaultdict(lambda: defaultdict(float))
sent_message_tracker = defaultdict(lambda: defaultdict(float))
last_bot_send_time = defaultdict(float)
bot_send_lock = asyncio.Lock()

http_session = None

speed_bot_states = {}
speed_bot_lock = asyncio.Lock()
speed_bot_tasks = {}

spam_states = {}  # تتبع حالة السبام المتواصل
spam_tasks = {}  # تتبع مهام السبام النشطة
spam_running = {}  # تتبع حالة السبام (شغال/متوقف)

user_random_section_state = {}  # تتبع حالة الأقسام العشوائية لكل مستخدم

# حالات الإذاعة المخصصة
private_broadcast_mode = {}  # تتبع وضع إذاعة الخاص
groups_broadcast_mode = {}  # تتبع وضع إذاعة القروبات

# حالات الباند السريع
fast_ban_mode = {}  # تتبع وضع الباند السريع للمالك الأساسي

# حالات قسم كشف
user_kashf_type = {}  # تتبع نوع كشف لكل مستخدم: "براد" / "مايك" / "نسوخي"
user_kashf_separator = {}  # تتبع الحرف الفاصل لكشف البراد لكل مستخدم

# الحروف العربية للفصل في كشف البراد
ARABIC_LETTERS = ["ا", "ب", "ت", "ث", "ج", "ح", "خ", "د", "ذ", "ر", "ز", "س", "ش", "ص", "ض", "ط", "ظ", "ع", "غ", "ف", "ق", "ك", "ل", "م", "ن", "ه", "و", "ي"]

processed_updates = set()
last_processed_update_cleanup = time.time()
MAX_PROCESSED_UPDATES = 1000

last_message_second = defaultdict(int)
messages_in_current_second = defaultdict(int)
sent_messages_per_second = defaultdict(list)
message_send_lock = asyncio.Lock()


URLS = {
    "جمم": "https://raw.githubusercontent.com/AL3ATEL/TXT-bot-telegram-/refs/heads/main/sentences.txt",
    "شرط": "https://raw.githubusercontent.com/AL3ATEL/txt-telegram-2/refs/heads/main/conditions.txt",
    "فكك": "https://raw.githubusercontent.com/AL3ATEL/3ks---dbl---trbl---fkk-/refs/heads/main/N9a8sam.txt",
    "صج": "https://raw.githubusercontent.com/AL3ATEL/txt-telegram-4/refs/heads/main/arabic_sentences.json",
    "جش": "https://raw.githubusercontent.com/BoulahiaAhmed/Arabic-Quotes-Dataset/main/Arabic_Quotes.csv",
    "شك": "https://raw.githubusercontent.com/AL3ATEL/txt-telegram-5/refs/heads/main/3amh.txt",
    "ويكي": "https://raw.githubusercontent.com/AL3ATEL/Wwweeeke/refs/heads/main/m8alatweke.txt",
    "مس": "https://drive.google.com/file/d/1BT4mnhBNsHDw-rObSF1M1YXhFUMdJRmt/view?usp=drivesdk",
    "دبل": "https://raw.githubusercontent.com/AL3ATEL/3ks---dbl---trbl---fkk-/refs/heads/main/N9a8sam.txt",
    "تر": "https://raw.githubusercontent.com/AL3ATEL/3ks---dbl---trbl---fkk-/refs/heads/main/N9a8sam.txt",
    "عكس": "https://raw.githubusercontent.com/AL3ATEL/3ks---dbl---trbl---fkk-/refs/heads/main/N9a8sam.txt",
    "فر": "https://raw.githubusercontent.com/AL3ATEL/Fffarsee/refs/heads/main/Faaarse.txt",
    "E": "https://raw.githubusercontent.com/AL3ATEL/English-wike-/refs/heads/main/English.txt",
    "قص": "https://drive.google.com/file/d/1wiW-O09wfLy6LbpAbCb8YseFIQ26W4Zn/view?usp=drivesdk",
    "طب": "https://drive.google.com/file/d/1iZkVksf_PzSpbKU0jvj8Y83XLym1JMDH/view?usp=drivesdk"
}

REPEAT_WORDS = ["صمت", "روق", "سين", "عين", "جيم", "لون", "خبر", "حلم", "جمل", "تعب", "فعل", "شمس", "نحل", "نسر", "حصن", "حل", "دور", "صك", "كل", "صوت", "سون", "كل", "حلو", "عطر", "همس", "حلو", "كمل", "فرق", "ود", "يوم", "رمل"]

NUMBER_WORDS = ["واحد", "اثنين", "ثلاثه", "اربعه", "خمسه", "سته", "سبعه", "ثمانيه", "تسعه", "عشرة", "عشرين", "خمسين", "ميه", "الف", "مليون", "ون", "تو", "ثري", "فور", "فايف", "سكس", "سفن", "ايت", "ناين", "تن", "تولف", "ايلفن", "تونتي"]

LETTER_WORDS = ["الف", "باء", "جيم", "دال", "شين", "ضاد", "قاف", "كاف", "لام", "ميم", "نون", "واو", "اكس", "واي", "ام", "جي", "كيو", "باي", "رو", "بيتا", "فاي"]

JAB_WORDS = ["حي", "اسرع", "هيا", "عز", "رجال", "اكتب", "سريع", "ولد", "لا", "روح", "خصم", "جلد", "اي", "دوس", "وين", "ادعس", "فوز", "تكلج", "شيل", "مقال", "هرب", "رتب", "اول", "خش", "في", "حق", "طير", "ولع", "كاتب", "جبل", "تصير", "ركب", "نور", "لعب", "حد", "روق", "وحش", "ضرب", "نهر", "ما", "جري", "برق", "حيك", "راس", "رعد", "ريح", "شيم", "واصل", "ركز", "خرج", "يبو", "سر", "نسخ", "مايك", "براد", "من", "شد", "ليه", "مر", "حب", "طار", "وفر", "لي", "ليل", "شطب", "اصمل", "درس", "بطل", "صح", "عيون"]

# كلمات جب حسب عدد الحروف
JAB_2_LETTERS = ["سم", "يد", "ام", "اي", "جد", "سن", "حب", "كم", "حي", "حق", "حس", "خط", "ظل", "بر", "قم", "شد", "بس", "صب", "تم", "دب", "صف", "حد", "لا", "ما", "في", "من", "لو", "دم", "هي", "كل", "له", "لي", "مت", "ذا", "هو", "مع", "او", "لب", "صك", "كف", "ود"]
JAB_3_LETTERS = ["كلب", "شمس", "وصل", "بحر", "قلم", "برق", "ريح", "صقر", "سمك", "جبل", "حلم", "ملك", "باب", "صوت", "رسم", "طير", "عسل", "بنت", "ضحك", "خبر", "ملح", "جبن", "علم", "وين", "كيف", "سور", "جسم", "مشي", "ايه", "نفس", "جرس", "مسك", "فيك"]
JAB_4_LETTERS = ["طريق", "قلبك", "حبيب", "جمله", "مقال", "عميل", "جديد", "وينه", "محمد", "خصيم", "نادر", "شموخ", "رجال", "عليك", "كثير", "شروق", "ايام", "ايوه", "كتاب", "عروض", "طيار", "قريب", "جميل", "خبير", "حياة", "سريع", "جرير"]
JAB_5_LETTERS = ["خلاص", "عاديه", "كتابه", "كثيره", "شمالي", "جنوبي", "خساره", "جريده", "مشكله", "صغيره", "كلمات", "خميره", "شهامه", "مرحبا", "مليون", "دولار", "يسعدك", "باردة", "مواقع", "سعودي", "اتحاد", "أصناف", "صداره", "صلابه", "كابوس", "احلام", "الناس", "اختراع", "الظلم", "ظلمات", "دقايق"]

# تتبع نوع جب لكل مستخدم
user_jab_type = {}  # {uid: "حرفين" / "ثلاث" / "اربع" / "خمس" / "مختلط"}

NASS_DRIVE_URLS = [
    "https://drive.google.com/file/d/1AwJ5s6aAeGnH5JQ6LjvGMOunlKlhDZYg/view?usp=drivesdk",
    "https://drive.google.com/file/d/1oVR2c9bUrziGg3M-QsYduV-j_zGFK8v5/view?usp=drivesdk",
    "https://drive.google.com/file/d/1_2IhMuw3ejAXq6cgTYtowSa6wCGTbgJw/view?usp=drivesdk",
    "https://drive.google.com/file/d/1Jy1LYGW7PLDSAChy4euUTl2J7boR9_bb/view?usp=drivesdk",
    "https://drive.google.com/file/d/1X5xl8kvTwjNmHO6BY1tlGyuflrV2-YYL/view?usp=drivesdk",
    "https://drive.google.com/file/d/1ozXsI-FdaMdzO4yToMYXKe_NFOBG-OTu/view?usp=drivesdk",
    "https://drive.google.com/file/d/1GCv06T6vGGKNRfMCq7tLkjR35sMvPUg3/view?usp=drivesdk",
    "https://drive.google.com/file/d/1awe5WHPiuLH_Pubi1usPSMbW0bAqWJCO/view?usp=drivesdk",
    "https://drive.google.com/file/d/192GKrNseDLyrUiSYm0slGfQevjM6u2nh/view?usp=drivesdk",
    "https://drive.google.com/file/d/1HykcSAX8PdkmgHXWLVoVFit1ZoGVSp-j/view?usp=drivesdk",
    "https://drive.google.com/file/d/1LlTBYUrCsrO50g4y7S-cnsgLx_rAxuDG/view?usp=drivesdk",
    "https://drive.google.com/file/d/1fibh-s7qosrUAtrQln6UQ9UDzre7wgzI/view?usp=drivesdk",
    "https://drive.google.com/file/d/1MnqUqtVZAYDO16TBin-h9OOL0S4ZFQTH/view?usp=drivesdk",
    "https://drive.google.com/file/d/1L53NoUAwIL6Ki84O_l6KK_Bmg4MOj1iv/view?usp=drivesdk",
    "https://drive.google.com/file/d/1VYrQY0Na8wzmRZdgWYl3mA_y7vfYhPFr/view?usp=drivesdk",
    "https://drive.google.com/file/d/1GA6Yi13CokJzx40aViGuNqvFe21HsAhQ/view?usp=drivesdk",
    "https://drive.google.com/file/d/1rd9l8Rzp1MxKaV55gvsDbypDfRcMeVAp/view?usp=drivesdk",
    "https://drive.google.com/file/d/1vGPWDzJLbBNDciozwiRCRzu89POiR80-/view?usp=drivesdk",
    "https://drive.google.com/file/d/1zpfQb2JnWRERoZBD6Nof7o83T_O9MVm_/view?usp=drivesdk",
    "https://drive.google.com/file/d/1p62GBB9bJ7tWrLiAx3Dyhemc9SgonHDQ/view?usp=drivesdk",
    "https://drive.google.com/file/d/1Medd6sRGxg2XjDnexq9vwxscpZi-U8Dq/view?usp=drivesdk",
    "https://drive.google.com/file/d/1-TujLpPljWM5ttz3F4Den6CkC27gVL9S/view?usp=drivesdk",
    "https://drive.google.com/file/d/10YiLlQvoB8GdgEmyXsyjS-dhau8RLGCN/view?usp=drivesdk",
    "https://drive.google.com/file/d/1naAUbU5Ji0sENuJOA5JWMk4QHbsxGQpr/view?usp=drivesdk",
    "https://drive.google.com/file/d/1RY1ghRYgPVwiH9lEsjM38XNzd0wzHk_C/view?usp=drivesdk",
    "https://drive.google.com/file/d/1uW6Je9Lqt3WV1d9qsJgQLev0fILOvjsj/view?usp=drivesdk",
    "https://drive.google.com/file/d/1g7R_ESOIFXZbsE_nTTE_ZesDOfuF9AMW/view?usp=drivesdk",
    "https://drive.google.com/file/d/1mXIJWP-NBWI0WXA-Uv1G9IFtxdAuT9_O/view?usp=drivesdk",
    "https://drive.google.com/file/d/1UfgAnJ8kg8e9nqddZObYhp-0yNd7J1oy/view?usp=drivesdk",
    "https://drive.google.com/file/d/16gLkV3GfIDkovm0Ty47AoXwqdq4G7qZM/view?usp=drivesdk",
    "https://drive.google.com/file/d/1FhzyGzMHtbYFGJ00ayJL6vGFybZx5EXk/view?usp=drivesdk",
    "https://drive.google.com/file/d/1PHzu7eERF43hG92LHmkSUMX6zo4u1_f7/view?usp=drivesdk",
    "https://drive.google.com/file/d/1zfymM9mB-EbrgcJPKkxMkrQSKGJUUMWh/view?usp=drivesdk",
    "https://drive.google.com/file/d/1_L6ThPRrotnEgHV-UtVJerlQRUYtI7sy/view?usp=drivesdk",
    "https://drive.google.com/file/d/17T2BrwV8cVCDSbgRfypFOolOMm9-Vo3L/view?usp=drivesdk",
    "https://drive.google.com/file/d/1zpmxWY5wE4ppYd-zJ_z_PLWNaMsptQtL/view?usp=drivesdk",
    "https://drive.google.com/file/d/18aU2SJoeBw_-JZY6NtM7Ue2mky0T5uPe/view?usp=drivesdk",
    "https://drive.google.com/file/d/11wJD6WkKw_Gc4KGPTsoMgzFOjdcYIfRw/view?usp=drivesdk",
    "https://drive.google.com/file/d/1ARWqrKLPu8mGNJvqLx1bbvCPQ9a4F4pk/view?usp=drivesdk",
    "https://drive.google.com/file/d/1uSi3EoCgVXiwHxAvcOKyObFtPQxYcKlb/view?usp=drivesdk",
    "https://drive.google.com/file/d/1xjk112E_bBk52x56RINmBjx58uKsFJmx/view?usp=drivesdk",
    "https://drive.google.com/file/d/1ATNu42EPouBumxNRaMWUxlem1IUlUmbz/view?usp=drivesdk",
    "https://drive.google.com/file/d/1-Au6SwhMTHUUBk3uC9l6bli_Fp-WEwZM/view?usp=drivesdk",
    "https://drive.google.com/file/d/1hHZCAeLamkTv0jaZ7QBewJU1B9K9Jbr6/view?usp=drivesdk",
    "https://drive.google.com/file/d/1ON9R9m3Qh4u8yrOus-f296P-I4Nu2fGe/view?usp=drivesdk",
    "https://drive.google.com/file/d/1F8fL0BUSIXWpSsoH_7ESWGQv26pxNepq/view?usp=drivesdk",
    "https://drive.google.com/file/d/17pWPIiPZ_vTISjmw2B-KNFhMgklu_mwP/view?usp=drivesdk",
    "https://drive.google.com/file/d/10H5sHixnkZO5fI0d480C4hW6SF6503Pp/view?usp=drivesdk",
    "https://drive.google.com/file/d/1qhRdVhBqZV0eHj0rYX9dvpIIRnlkjAh5/view?usp=drivesdk",
    "https://drive.google.com/file/d/1idOMgj4EH1iJwxPPHMS-nM-VAKMmhkWP/view?usp=drivesdk",
    "https://drive.google.com/file/d/1ekcxe8pw0xWAiFVqHNf8y4MefjyL0lpC/view?usp=drivesdk",
    "https://drive.google.com/file/d/1kQdGclgAJWOZ2KHM5d_xl85yOAS6azI7/view?usp=drivesdk",
    "https://drive.google.com/file/d/1VXptSX4PNRC9o9mZZ6wsewmVaY3Nzg5S/view?usp=drivesdk",
    "https://drive.google.com/file/d/1aIYilqapzAO-8BUNX48jeX_ugafJiqGV/view?usp=drivesdk",
    "https://drive.google.com/file/d/10dtSEapz-N-jela0PA9U1oCXr35abaiz/view?usp=drivesdk",
    "https://drive.google.com/file/d/1G3ffM94zldw6Uy50gsvMheR8b2wtFEyf/view?usp=drivesdk",
    "https://drive.google.com/file/d/1dBCxMIBaDYKb_g-9UYwxxXaD4awnSur1/view?usp=drivesdk",
    "https://drive.google.com/file/d/1xs2sxsilxttcI8FFGYflTRu__fFEqQJf/view?usp=drivesdk",
    "https://drive.google.com/file/d/1SoVQP6a9FaHXPVk31lnUDI2z6lO-3oA5/view?usp=drivesdk",
    "https://drive.google.com/file/d/1Usvvt5HQyocYqhlEXlIKs2jh7dlI9bhd/view?usp=drivesdk",
    "https://drive.google.com/file/d/19AWenU_8s7F3ImYUxVUFLbf0C5aF069p/view?usp=drivesdk"
]

CONDITIONS = [
    "كرر أول كلمة",
    "كرر ثاني كلمة",
    "كرر آخر كلمة",
    "كرر أول كلمة وآخر كلمة",
    "فكك أول كلمة",
    "فكك آخر كلمة",
    "بدل أول كلمتين",
    "بدل آخر كلمتين",
    "بدل ثاني كلمة والكلمة الأخيرة"
]

CHAR_MAP = {'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي', 'ة': 'ه', 'ئ': 'ي', 'ؤ': 'و', 'ٱ': 'ا', 'ٳ': 'ا'}
NUM_WORDS = {'0': 'صفر', '1': 'واحد', '2': 'اثنان', '3': 'ثلاثة', '4': 'أربعة', '5': 'خمسة', '6': 'ستة', '7': 'سبعة', '8': 'ثمانية', '9': 'تسعة', '10': 'عشرة', '20': 'عشرون', '30': 'ثلاثون', '40': 'أربعون', '50': 'خمسون', '60': 'ستون', '70': 'سبعون', '80': 'ثمانون', '90': 'تسعون', '100': 'مائة', '1000': 'ألف'}

# قفل لمنع استدعاءات متزامنة في الجملة الواحدة
game_sending_locks = {}

# تتبع الإجابات المعلقة: {game_id: {uid: timestamp}}
pending_match_answers = {}

# تتبع حالة التخصيصات: {uid: {stage: "waiting_type"|"waiting_words"|"waiting_save"|"waiting_shortcut", data: {...}}}
customization_state = {}

# حالة أمر نشبه/نشبة للمالك الأساسي
nshabeh_state = {}

# تتبع طلب الصدارة لمستخدم جديد: {uid: True/False}
leaderboard_state = {}

async def init_http_session():
    global http_session
    if http_session is None:
        timeout = aiohttp.ClientTimeout(total=15)
        connector = aiohttp.TCPConnector(limit=5, limit_per_host=3)
        http_session = aiohttp.ClientSession(timeout=timeout, connector=connector)
    return http_session

async def send_next_match_sentence(c, uid, opponent_uid, game_id, exclude_section=None):
    """إرسال جملة جديدة من قسم مختلف - مرة واحدة فقط لكل مستخدم"""
    global game_sending_locks

    # إنشاء قفل فريد لكل لعبة
    if game_id not in game_sending_locks:
        game_sending_locks[game_id] = asyncio.Lock()

    lock = game_sending_locks[game_id]

    try:
        # محاولة الحصول على القفل (مع مهلة 0.1 ثانية)
        try:
            acquired = await asyncio.wait_for(lock.acquire(), timeout=0.1)
            if not acquired:
                print(f"[MATCH_SEND] فشل الحصول على القفل - استدعاء مرفوض للعبة {game_id}")
                return
        except asyncio.TimeoutError:
            print(f"[MATCH_SEND] انتظار القفل انتهى - رسالة أخرى قيد الإرسال للعبة {game_id}")
            return

        # حماية إضافية: تحقق من اللعبة
        game = storage.get_matchmaking_game(game_id)
        if not game:
            print(f"[MATCH_SEND] اللعبة {game_id} غير موجودة")
            return

        current_time = time.time()
        last_send_time = game.get("last_send_time", 0)
        time_since_last_send = current_time - last_send_time

        # إذا أقل من 3 ثواني من آخر إرسال، رفض
        if time_since_last_send < 3:
            print(f"[MATCH_SEND] استدعاء سريع جداً - مرفوض (بعد {time_since_last_send:.2f} ثانية من آخر إرسال)")
            return

        print(f"[MATCH_SEND] بدء إرسال جملة جديدة للعبة {game_id}")
        game["last_send_time"] = current_time
        storage.data["matchmaking_games"][game_id] = game
        storage.save(force=True)

        sections = ["كرر", "ويكي", "مس", "شك", "حر"]
        # اختر قسم مختلف عن الأخير
        if exclude_section is not None and exclude_section in sections:
            sections.remove(exclude_section)

        chosen_section = random.choice(sections)

        # تأخير قصير قبل إرسال العد
        await asyncio.sleep(2)

        # اختيار جملة عشوائية
        sentence = None
        display_text = None

        if chosen_section == "كرر":
            patterns = gen_pattern(uid, random.randint(3, 5))
            sentence = " ".join(patterns)
            display_text = sentence
        elif chosen_section == "ويكي":
            if managers and "ويكي" in managers:
                word_count = random.randint(10, 15)
                sentence = get_text_with_word_count(managers["ويكي"], word_count)
                if not sentence:
                    sentence = managers["ويكي"].get()
                if sentence:
                    display_text = format_display(sentence)
        elif chosen_section == "مس":
            if managers and "مس" in managers:
                word_count = random.randint(10, 15)
                sentence = get_text_with_word_count(managers["مس"], word_count)
                if not sentence:
                    sentence = managers["مس"].get()
                if sentence:
                    display_text = format_display(sentence)
        elif chosen_section == "شك":
            if managers and "شك" in managers:
                word_count = random.randint(10, 15)
                sentence = get_text_with_word_count(managers["شك"], word_count)
                if not sentence:
                    sentence = managers["شك"].get()
                if sentence:
                    display_text = format_display(sentence)

        if sentence and display_text:
            # تحديث آخر قسم بشكل آمن
            storage.update_game_section(game_id, chosen_section)

            # حذف أي جلسات قديمة قبل حفظ جلسات جديدة
            session_type = f"match_{game_id}"
            storage.del_session(uid, session_type)
            storage.del_session(opponent_uid, session_type)

            current_time = time.time()

            # إرسال العد والجملة للاعب الأول
            try:
                print(f"[MATCH_SEND] إرسال العد والجملة للاعب 1 (uid={uid})")
                await c.bot.send_message(uid, "111122223333")
                await asyncio.sleep(1.5)
                await c.bot.send_message(uid, display_text)
            except Exception as e:
                print(f"[MATCH_SEND] خطأ في إرسال للاعب 1: {e}")

            # حفظ الجلسة للاعب الأول
            storage.save_session(uid, uid, session_type, sentence, current_time)

            await asyncio.sleep(0.1)

            # إرسال العد والجملة للاعب الثاني (فقط إذا لم يكن البوت الافتراضي)
            if opponent_uid != -1:
                try:
                    print(f"[MATCH_SEND] إرسال العد والجملة للاعب 2 (uid={opponent_uid})")
                    await c.bot.send_message(opponent_uid, "111122223333")
                    await asyncio.sleep(1.5)
                    await c.bot.send_message(opponent_uid, display_text)
                except Exception as e:
                    print(f"[MATCH_SEND] خطأ في إرسال للاعب 2: {e}")

            # حفظ الجلسة للاعب الثاني (إذا كان البوت الافتراضي، لا نحفظ جلسة له)
            if opponent_uid != -1:
                storage.save_session(opponent_uid, opponent_uid, session_type, sentence, current_time)

            storage.save()
        else:
            # حالة احتياطية: لا توجد جملة - جرب قسم آخر
            print(f"[MATCH_SEND] لم توجد جملة من القسم {chosen_section}، محاولة قسم بديل")
            sections = ["كرر", "ويكي", "مس", "شك", "حر"]
            if chosen_section in sections:
                sections.remove(chosen_section)
            if exclude_section is not None and exclude_section in sections:
                sections.remove(exclude_section)
            if sections:
                # جرب قسم بديل
                fallback_section = random.choice(sections)
                print(f"[MATCH_SEND] محاولة القسم البديل: {fallback_section}")
                await asyncio.sleep(1)
                asyncio.create_task(send_next_match_sentence(c, uid, opponent_uid, game_id, exclude_section=chosen_section))
    except Exception as e:
        print(f"[MATCH] Error sending next sentence: {e}")
    finally:
        # تحرير القفل دائماً - حتى عند حدوث خطأ
        try:
            lock.release()
            print(f"[MATCH_SEND] تحرير القفل للعبة {game_id}")
        except Exception as e:
            print(f"[MATCH_SEND] خطأ في تحرير القفل: {e}")


async def close_http_session():
    global http_session
    if http_session:
        await http_session.close()
        http_session = None

def clean_text_for_word_count(text):
    # حذف جميع الرموز والعلامات الترقيمية
    symbol_pattern = r'[~=\-_|/\\*#@%$&!+^<>{}[\]()"\'،,:;؛\.\!؟\?\(\)\[\]\{\}""''«»…≈]+'
    text = re.sub(symbol_pattern, ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_number_from_text(text):
    match = re.search(r'\s+(\d+)$', text)
    if match:
        number = int(match.group(1))
        command = text[:match.start()].strip()
        return command, number
    return text, None

def contains_11_to_19(num):
    """فحص إذا كان الرقم يحتوي على 11-19 داخله"""
    num_str = str(num)
    for i in range(len(num_str) - 1):
        two_digit = int(num_str[i:i+2])
        if 11 <= two_digit <= 19:
            return True
    return False

def number_to_arabic_words(num):
    ones = ["صفر", "واحد", "اثنين", "ثلاثه", "اربعه", "خمسه", "سته", "سبعه", "ثمانيه", "تسعه"]
    tens = ["", "", "عشرين", "ثلاثين", "اربعين", "خمسين", "ستين", "سبعين", "ثمانين", "تسعين"]
    teens = ["عشرة", "احدعشر", "اثنعشر", "ثلاثعشر", "اربععشر", "خمسعشر", "ستعشر", "سبععشر", "ثمانعشر", "تسععشر"]

    if contains_11_to_19(num):
        return ""
    if num == 0:
        return "صفر"
    if num < 10:
        return ones[num]
    elif num < 20:
        return teens[num - 10]
    elif num < 100:
        tens_digit = num // 10
        ones_digit = num % 10
        if ones_digit == 0:
            return tens[tens_digit]
        return ones[ones_digit] + " و" + tens[tens_digit]
    else:
        hundreds_digit = num // 100
        remainder = num % 100
        result = "ميه" if hundreds_digit == 1 else ones[hundreds_digit] + " ميه"
        if remainder == 0:
            return result
        return result + " و" + number_to_arabic_words(remainder)

def generate_hard_numbers_sentence(count=None):
    if count is None:
        count = random.randint(5, 10)
    else:
        count = max(1, min(int(count), 40))
    numbers = []
    for _ in range(count):
        for attempt in range(100):  # ✅ حد أقصى 100 محاولة بدل while True
            num = random.randint(0, 1000)
            if not contains_11_to_19(num):
                numbers.append(num)
                break
    return numbers, " , ".join(str(n) for n in numbers)

def generate_easy_numbers_sentence(count=None):
    if count is None:
        count = random.randint(5, 10)
    else:
        count = max(1, min(int(count), 40))
    numbers = []
    for _ in range(count):
        for attempt in range(100):  # ✅ حد أقصى 100 محاولة بدل while True
            num = random.randint(0, 100)
            if not contains_11_to_19(num):
                numbers.append(num)
                break
    return numbers, " , ".join(str(n) for n in numbers)

def convert_numbers_to_arabic_words(numbers_str):
    numbers = [int(n.strip()) for n in numbers_str.split(',') if n.strip().isdigit()]
    words = []
    for num in numbers:
        words.append(number_to_arabic_words(num))
    return " ".join(words)

def normalize_number_text(text):
    normalized = text
    normalized = re.sub(r'\s*و\s*', ' و ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    replacements = {
        r'\b(ميتين|ميه\s*و\s*اثنين|مائتين|مائتان)\b': 'اثنين ميه',
        r'\b(ثلاث\s*ميه|ثلاثه\s*ميه|ثلاثميه)\b': 'ثلاثه ميه',
        r'\b(اربع\s*ميه|اربعه\s*ميه|اربعميه)\b': 'اربعه ميه',
        r'\b(خمس\s*ميه|خمسه\s*ميه|خمسميه)\b': 'خمسه ميه',
        r'\b(ست\s*ميه|سته\s*ميه|ستميه)\b': 'سته ميه',
        r'\b(سبع\s*ميه|سبعه\s*ميه|سبعميه)\b': 'سبعه ميه',
        r'\b(ثمان\s*ميه|ثمانيه\s*ميه|ثمانه\s*ميه|ثمانميه)\b': 'ثمانيه ميه',
        r'\b(تسع\s*ميه|تسعه\s*ميه|تسعميه)\b': 'تسعه ميه',
        r'\b(واحد|احد)\b': 'واحد', r'\b(اثنين|اثنان)\b': 'اثنين',
        r'\b(ثلاثه|ثلاثة|ثلاث)\b': 'ثلاثه', r'\b(اربعه|اربعة|اربع)\b': 'اربعه',
        r'\b(خمسه|خمسة|خمس)\b': 'خمسه', r'\b(سته|ستة|ست)\b': 'سته',
        r'\b(سبعه|سبعة|سبع)\b': 'سبعه', r'\b(ثمانيه|ثمانية|ثمان)\b': 'ثمانيه',
        r'\b(تسعه|تسعة|تسع)\b': 'تسعه', r'\b(عشرة|عشره|عشر)\b': 'عشرة',
        r'\b(احدعشر|احد\s*عشر|احدعش|احد\s*عش|احدى\s*عشر|احدى\s*عش|احدعشرة)\b': 'احدعشر',
        r'\b(اثنعشر|اثن\s*عشر|اثنعش|اثن\s*عش|اثنا\s*عشر|اثنا\s*عش|اثنعشرة)\b': 'اثنعشر',
        r'\b(ثلاثعشر|ثلاث\s*عشر|ثلاثعش|ثلاث\s*عش|ثل\s*عشر|ثل\s*عش|ثلاطعش|ثل\s*طعش|ثلاثعشرة)\b': 'ثلاثعشر',
        r'\b(اربععشر|اربع\s*عشر|اربععش|اربع\s*عش|اربعطعش|اربع\s*طعش|اربععشرة)\b': 'اربععشر',
        r'\b(خمسعشر|خمس\s*عشر|خمسعش|خمس\s*عش|خمسطعش|خمس\s*طعش|خمسعشرة)\b': 'خمسعشر',
        r'\b(ستعشر|ست\s*عشر|ستعش|ست\s*عش|سطعش|ست\s*طعش|ستعشرة)\b': 'ستعشر',
        r'\b(سبععشر|سبع\s*عشر|سبععش|سبع\s*عش|سبعطعش|سبع\s*طعش|سبععشرة)\b': 'سبععشر',
        r'\b(ثمانعشر|ثمان\s*عشر|ثمانعش|ثمان\s*عش|ثمنطعش|ثمن\s*طعش|ثمانعشرة)\b': 'ثمانعشر',
        r'\b(تسععشر|تسع\s*عشر|تسععش|تسع\s*عش|تسعطعش|تسع\s*طعش|تسععشرة)\b': 'تسععشر',
        r'\b(عشرين|عشرون|عشري)\b': 'عشرين',
        r'\b(ثلاثين|ثلاثون|ثلاثي)\b': 'ثلاثين',
        r'\b(اربعين|اربعون|اربعي)\b': 'اربعين',
        r'\b(خمسين|خمسون|خمسي)\b': 'خمسين',
        r'\b(ستين|ستون|ستي)\b': 'ستين',
        r'\b(سبعين|سبعون|سبعي)\b': 'سبعين',
        r'\b(ثمانين|ثمانون|ثماني)\b': 'ثمانين',
        r'\b(تسعين|تسعون|تسعي)\b': 'تسعين',
        r'\b(مئة|ميه|مائة|مية)\b': 'ميه',
        r'\b(الف|الفة)\b': 'الف'
    }

    for pattern, replacement in replacements.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

async def can_bot_send(cid):
    async with message_send_lock:
        current_second = int(time.time())

        if last_message_second[cid] == current_second:
            return False

        last_message_second[cid] = current_second
        messages_in_current_second[cid] = 1

        return True

async def track_and_verify_message(context, cid, message_id):
    async with message_send_lock:
        current_second = int(time.time())

        sent_messages_per_second[cid] = [
            (sec, msg_id) for sec, msg_id in sent_messages_per_second[cid]
            if current_second - sec < 3
        ]

        sent_messages_per_second[cid].append((current_second, message_id))

        messages_in_this_second = [
            msg_id for sec, msg_id in sent_messages_per_second[cid]
            if sec == current_second
        ]

        if len(messages_in_this_second) >= 2:
            for msg_id in messages_in_this_second:
                try:
                    await context.bot.delete_message(chat_id=cid, message_id=msg_id)
                except Exception as e:
                    print(f"Error deleting duplicate message {msg_id}: {e}")

            sent_messages_per_second[cid] = [
                (sec, msg_id) for sec, msg_id in sent_messages_per_second[cid]
                if sec != current_second
            ]

            return False

        return True

async def safe_reply(update, context, text, sleep_if_blocked=False):
    cid = update.effective_chat.id

    if not await can_bot_send(cid):
        if sleep_if_blocked:
            await asyncio.sleep(1.0)
            if not await can_bot_send(cid):
                return None
        else:
            return None

    try:
        sent_message = await update.message.reply_text(text)

        if sent_message:
            keep_message = await track_and_verify_message(context, cid, sent_message.message_id)
            if not keep_message:
                return None

        return sent_message
    except Exception as e:
        print(f"Error sending safe reply: {e}")
        return None

def get_text_with_word_count(manager, target_word_count):
    if target_word_count < 1 or target_word_count > 60:
        return None

    combined_words = []
    attempt = 0
    max_attempts = 10

    while len(combined_words) < target_word_count and attempt < max_attempts:
        if hasattr(manager, 'get_multiple'):
            new_sentences = manager.get_multiple(3)
        else:
            new_sentences = [manager.get() for _ in range(3)]

        for sentence in new_sentences:
            cleaned_sentence = clean_text_for_word_count(sentence)
            combined_words.extend(cleaned_sentence.split())
            if len(combined_words) >= target_word_count:
                break

        attempt += 1

    if len(combined_words) >= target_word_count:
        return ' '.join(combined_words[:target_word_count])
    else:
        return ' '.join(combined_words)

def convert_repeat_pattern_to_words(pattern):
    def replace_pattern(match):
        word = match.group(1)
        count = int(match.group(2))
        return ' '.join([word] * count)

    converted = re.sub(r'(\S+)\((\d+)\)', replace_pattern, pattern)
    return converted

def convert_to_double(sentence):
    words = sentence.split()
    result_words = []
    for word in words:
        result_words.append(word)
        result_words.append(word)
    return ' '.join(result_words)

def convert_to_triple(sentence):
    words = sentence.split()
    result_words = []
    for word in words:
        result_words.append(word)
        result_words.append(word)
        result_words.append(word)
    return ' '.join(result_words)

def calculate_typing_speed(base_wpm, sentence_type=None):
    base_fluctuation = random.uniform(-0.05, -0.15) if random.random() < 0.5 else random.uniform(0.05, 0.15)

    multiplier = 1.0
    if sentence_type in ["كرر", "دبل", "تر"]:
        multiplier = random.uniform(1.20, 1.30)

    final_wpm = base_wpm * (1 + base_fluctuation) * multiplier
    final_wpm += 20

    return max(50, min(5000, final_wpm))

def build_speed_output(sentence):
    words = sentence.split()
    return " ~ ".join(words)

async def speed_bot_type_sentence(context, cid, sentence, wpm, sentence_type, start_time):
    try:
        speed_text = build_speed_output(sentence)
        words = sentence.split()
        total_chars = sum(len(w) for w in words)

        chars_per_second = (wpm * 5) / 60.0
        total_time_needed = total_chars / chars_per_second

        chunks = []
        current_chunk = ""
        current_word_idx = 0

        for word in words:
            if current_chunk:
                current_chunk += " ~ " + word
            else:
                current_chunk = word
            current_word_idx += 1

            if current_word_idx % 2 == 0 or current_word_idx == len(words):
                chunks.append(current_chunk)

        if not chunks:
            chunks = [speed_text]

        chunk_delay = total_time_needed / len(chunks)

        message = None
        for i, chunk in enumerate(chunks):
            if i > 0:
                jitter = random.uniform(0.8, 1.2)
                await asyncio.sleep(chunk_delay * jitter)

            try:
                if message is None:
                    if not await can_bot_send(cid):
                        await asyncio.sleep(1.0)
                        if not await can_bot_send(cid):
                            return 0

                    message = await context.bot.send_message(chat_id=cid, text=chunk)

                    if message:
                        keep_message = await track_and_verify_message(context, cid, message.message_id)
                        if not keep_message:
                            return 0
                else:
                    await message.edit_text(chunk)
            except Exception as e:
                print(f"Error in speed bot typing: {e}")
                break

        elapsed_time = time.time() - start_time
        # استخدام count_words_for_wpm لحساب الكلمات بعد حذف جميع الرموز
        word_count = count_words_for_wpm(sentence)
        actual_wpm = (word_count / elapsed_time) * 60 + 20

        final_text = f"كفو يا\n\nسرعتك: {actual_wpm:.2f} كلمة/دقيقة\nالوقت : {elapsed_time:.2f} ثانية"
        try:
            if message:
                await message.edit_text(final_text)
        except:
            pass

        return actual_wpm

    except asyncio.CancelledError:
        print(f"Speed bot task cancelled for chat {cid}")
        raise
    except Exception as e:
        print(f"Error in speed_bot_type_sentence: {e}")
        return 0

async def trigger_speed_bot_if_enabled(context, cid, sentence, sentence_type):
    try:
        speed_config = storage.get_speed_bot_config(cid)
        if not speed_config["enabled"]:
            task = speed_bot_tasks.pop(str(cid), None)
            if task and not task.done():
                task.cancel()
            return

        task_key = str(cid)
        old_task = speed_bot_tasks.get(task_key)
        if old_task and not old_task.done():
            old_task.cancel()
            try:
                await old_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"Error cancelling old speed task: {e}")

        speed_bot_tasks.pop(task_key, None)

        converted_sentence = sentence
        if sentence_type == "كرر":
            converted_sentence = convert_repeat_pattern_to_words(sentence)
        elif sentence_type == "دبل":
            converted_sentence = convert_to_double(sentence)
        elif sentence_type == "تر":
            converted_sentence = convert_to_triple(sentence)

        base_wpm = speed_config["base_wpm"]
        wpm = calculate_typing_speed(base_wpm, sentence_type)
        start_time = time.time()

        task = asyncio.create_task(
            speed_bot_type_sentence(context, cid, converted_sentence, wpm, sentence_type, start_time)
        )
        speed_bot_tasks[task_key] = task
        task.add_done_callback(
            lambda t, key=task_key: speed_bot_tasks.pop(key, None) if speed_bot_tasks.get(key) is t else None
        )

    except Exception as e:
        print(f"Error triggering speed bot: {e}")

class Storage:
    def __init__(self):
        self.file = "bot_data.json"
        self.device_types_file = "device_types.json"
        self.device_types_backup_file = "device_types_backup.json"
        self.leaderboard_file = "leaderboard.json"
        self.banned_file = "banned.json"
        self.customizations_file = "customizations.json"
        self.data = self.load()
        self.device_types_data = self.load_device_types()
        self.leaderboard_data = self.load_leaderboard()
        self.banned_data = self.load_banned()
        self.customizations_data = self.load_customizations()
        self.dirty = False
        self._dirty_count = 0

    def load_device_types(self):
        """تحميل device_types من ملف منفصل آمن"""
        try:
            with open(self.device_types_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"[DEVICE_TYPES] Loaded {len(data)} device types from {self.device_types_file}")
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            # محاولة استعادة من النسخة الاحتياطية
            try:
                with open(self.device_types_backup_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"[DEVICE_TYPES] Restored from backup - {len(data)} device types")
                    return data
            except (FileNotFoundError, json.JSONDecodeError):
                print("[DEVICE_TYPES] No device types data found, starting fresh")
                return {}

    def load_leaderboard(self):
        """تحميل الصدارة من ملف منفصل"""
        try:
            with open(self.leaderboard_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"[LEADERBOARD] Loaded leaderboard data from {self.leaderboard_file}")
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            print("[LEADERBOARD] No leaderboard data found, starting fresh")
            return {"scores": {}, "removed_from_leaderboard": {}, "best_scores": {}}

    def save_leaderboard(self):
        """حفظ الصدارة في ملف منفصل"""
        try:
            with open(self.leaderboard_file, 'w', encoding='utf-8') as f:
                json.dump(self.leaderboard_data, f, ensure_ascii=False, indent=2)
            print(f"[LEADERBOARD] Leaderboard saved successfully")
        except Exception as e:
            print(f"[ERROR] Failed to save leaderboard: {e}")

    def load_banned(self):
        """تحميل المحظورين من ملف منفصل"""
        try:
            with open(self.banned_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("banned", [])
                    data.setdefault("info", {})
                    return data
                if isinstance(data, list):
                    # صيغة قديمة: قائمة أيدي فقط
                    return {"banned": data, "info": {}}
                return {"banned": [], "info": {}}
        except (FileNotFoundError, json.JSONDecodeError):
            print("[BANNED] No banned data found, starting fresh")
            return {"banned": [], "info": {}}

    def save_banned(self):
        """حفظ المحظورين في ملف منفصل"""
        try:
            with open(self.banned_file, 'w', encoding='utf-8') as f:
                json.dump(self.banned_data, f, ensure_ascii=False, indent=2)
            print(f"[BANNED] Banned data saved successfully")
        except Exception as e:
            print(f"[ERROR] Failed to save banned: {e}")

    def load_customizations(self):
        """تحميل الكلمات المخصصة من ملف منفصل"""
        try:
            with open(self.customizations_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"[CUSTOMIZATIONS] Loaded customizations data from {self.customizations_file}")
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            print("[CUSTOMIZATIONS] No customizations data found, starting fresh")
            return {"customizations": {}}

    def save_customizations(self):
        """حفظ الكلمات المخصصة في ملف منفصل"""
        try:
            with open(self.customizations_file, 'w', encoding='utf-8') as f:
                json.dump(self.customizations_data, f, ensure_ascii=False, indent=2)
            print(f"[CUSTOMIZATIONS] Customizations saved successfully")
        except Exception as e:
            print(f"[ERROR] Failed to save customizations: {e}")

    def load(self):
        try:
            with open(self.file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "users": {},
                "chats": {},
                "patterns": {},
                "sessions": {},
                "awards": {},
                "weekly_awards": {},
                "stats": {},
                "broadcast_mode": {},
                "rounds": {},
                "round_mode": {},
                "pending_round_setup": {},
                "admins": [],
                "owners": [],
                "preferences": {},
                "auto_mode": {},
                "speed_bot": {},
                "levels": {},
                "leaderboard_backups": {},
                "matchmaking_queue": [],
                "matchmaking_games": {},
                "average_speeds": {},
                "messages_sent": {},
                "shabah": {},
                "chat_members": {},
                "paused_chats": []
            }

    def save(self, force=False):
        global last_save_time
        current_time = time.time()

        if not self.dirty and not force:
            return

        if not force:
            if self._dirty_count < max_dirty_count and (current_time - last_save_time) < save_interval:
                return

        try:
            with open(self.file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            self.save_leaderboard()
            self.save_banned()
            self.save_customizations()
            self.dirty = False
            self._dirty_count = 0
            last_save_time = current_time
            print(f"[STORAGE] Data saved successfully at {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"Error saving data: {e}")

    def mark_dirty(self):
        self.dirty = True
        self._dirty_count += 1

        if self._dirty_count >= max_dirty_count:
            self.save(force=True)

    def add_user(self, uid, usr, name):
        self.data["users"][str(uid)] = {
            "username": usr,
            "first_name": name,
            "created_at": datetime.now().isoformat()
        }
        self.mark_dirty()

    def add_chat(self, cid, title):
        self.data["chats"][str(cid)] = {
            "title": title,
            "created_at": datetime.now().isoformat()
        }
        self.mark_dirty()

    def remove_chat(self, cid):
        if str(cid) in self.data["chats"]:
            del self.data["chats"][str(cid)]
            self.mark_dirty()
            self.save(force=True)

    def record_chat_member(self, cid, uid):
        """تسجيل عضو شافوه البوت داخل القروب (عشان أمر طرد الكل)"""
        members = self.data.setdefault("chat_members", {}).setdefault(str(cid), {})
        uid_str = str(uid)
        now = time.time()
        if members.get(uid_str, 0) < now - 60:
            members[uid_str] = now
            self.mark_dirty()

    def clear_chat_members(self, cid):
        if str(cid) in self.data.get("chat_members", {}):
            del self.data["chat_members"][str(cid)]
            self.mark_dirty()

    # ===== إيقاف البوت في قروب (أمر وقف هنا) =====
    def pause_chat(self, cid):
        key = str(cid)
        lst = self.data.setdefault("paused_chats", [])
        if key not in lst:
            lst.append(key)
            self.mark_dirty()
            self.save(force=True)

    def unpause_chat(self, cid):
        key = str(cid)
        lst = self.data.get("paused_chats", [])
        if key in lst:
            lst.remove(key)
            self.mark_dirty()
            self.save(force=True)

    def is_chat_paused(self, cid):
        return str(cid) in self.data.get("paused_chats", [])

    def save_preference(self, uid, section, word_count):
        uid_str = str(uid)
        if "preferences" not in self.data:
            self.data["preferences"] = {}
        if uid_str not in self.data["preferences"]:
            self.data["preferences"][uid_str] = {}
        self.data["preferences"][uid_str][section] = word_count
        self.mark_dirty()

    def get_preference(self, uid, section):
        uid_str = str(uid)
        if "preferences" not in self.data:
            return None
        if uid_str not in self.data["preferences"]:
            return None
        return self.data["preferences"][uid_str].get(section)

    def clear_preference(self, uid, section):
        uid_str = str(uid)
        if "preferences" not in self.data:
            return False
        if uid_str not in self.data["preferences"]:
            return False
        if section in self.data["preferences"][uid_str]:
            del self.data["preferences"][uid_str][section]
            self.mark_dirty()
            return True
        return False

    def save_number_type(self, uid, number_type):
        uid_str = str(uid)
        if "number_types" not in self.data:
            self.data["number_types"] = {}
        self.data["number_types"][uid_str] = number_type
        self.mark_dirty()

    def get_number_type(self, uid):
        uid_str = str(uid)
        if "number_types" not in self.data:
            return None
        return self.data["number_types"].get(uid_str)

    def clear_number_type(self, uid):
        """مسح نوع الأرقام للمستخدم (إعادة للوضع العشوائي)"""
        uid_str = str(uid)
        if "number_types" not in self.data:
            return False
        if uid_str in self.data["number_types"]:
            del self.data["number_types"][uid_str]
            self.mark_dirty()
            return True
        return False

    def save_device_type(self, uid, device_type):
        """حفظ آمن لـ device_type في ملف منفصل فقط"""
        uid_str = str(uid)

        # حفظ في device_types.json و device_types_backup.json فقط
        if not hasattr(self, 'device_types_data') or self.device_types_data is None:
            self.device_types_data = self.load_device_types()
        self.device_types_data[uid_str] = device_type
        self.save_device_types()  # حفظ فوري في الملف الآمن

        print(f"[DEVICE_TYPE] Saved device_type '{device_type}' for user {uid}")

    def save_device_types(self):
        """حفظ آمن لـ device_types في ملفين منفصلين"""
        try:
            # حفظ في الملف الأساسي
            with open(self.device_types_file, 'w', encoding='utf-8') as f:
                json.dump(self.device_types_data, f, ensure_ascii=False, indent=2)
            
            # حفظ نسخة احتياطية
            with open(self.device_types_backup_file, 'w', encoding='utf-8') as f:
                json.dump(self.device_types_data, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            print(f"[ERROR] Failed to save device types: {e}")

    def get_device_type(self, uid):
        """قراءة device_type من الملف الآمن"""
        uid_str = str(uid)
        if not hasattr(self, 'device_types_data') or self.device_types_data is None:
            self.device_types_data = self.load_device_types()
        device_type = self.device_types_data.get(uid_str)
        # لا نطبع رسالة خطأ - تبقى تعمل في النظام بدون ما تظهر في الـ logs
        return device_type

    def has_device_type(self, uid):
        """التحقق من وجود device_type للمستخدم"""
        uid_str = str(uid)
        if not hasattr(self, 'device_types_data') or self.device_types_data is None:
            self.device_types_data = self.load_device_types()
        return uid_str in self.device_types_data

    def is_banned(self, uid):
        # المالك الأساسي لا يمكن أن يكون محظوراً
        if self.is_main_owner(uid):
            return False

        uid_str = str(uid)

        if uid_str in banned_cache:
            return banned_cache[uid_str]

        is_in_list = uid_str in self.banned_data["banned"]
        banned_cache[uid_str] = is_in_list
        return is_in_list

    def ban_user(self, uid, reason="حظر يدوي", by_uid=None, by_username=None, by_name=None):
        #  المالك الأساسي محمي من الحظر نهائياً
        if self.is_main_owner(uid):
            print(f"[BAN] Cannot ban primary owner {uid}")
            return False

        uid_str = str(uid)
        if uid_str not in self.banned_data["banned"]:
            self.banned_data["banned"].append(uid_str)
            # حفظ معلومات الحظر: السبب ومن حظر
            self.banned_data.setdefault("info", {})[uid_str] = {
                "reason": reason,
                "by_uid": by_uid,
                "by_username": by_username,
                "by_name": by_name,
                "time": datetime.now().isoformat()
            }
            self.save_banned()
            print(f"[BAN] User {uid} has been banned. Updated banned list: {self.banned_data['banned']}")

        sessions_to_remove = []
        for key, session in self.data["sessions"].items():
            if session.get("starter_uid") == uid:
                sessions_to_remove.append(key)

        for key in sessions_to_remove:
            self.data["sessions"].pop(key, None)

        # حذف المستخدم من الصدارة تلقائياً عند الحظر
        self.remove_from_leaderboard(uid)

        banned_cache[uid_str] = True
        self.mark_dirty()
        self.save(force=True)
        return True

    def unban_user(self, uid):
        uid_str = str(uid)
        print(f"[UNBAN] Attempting to unban user {uid}. Current banned list: {self.banned_data['banned']}")

        if uid_str in self.banned_data["banned"]:
            self.banned_data["banned"].remove(uid_str)
            # حذف معلومات الحظر
            self.banned_data.setdefault("info", {}).pop(uid_str, None)
            self.save_banned()
            banned_cache[uid_str] = False

            # استرجاع المستخدم للصدارة عند فك الحظر
            self.restore_from_leaderboard(uid)

            self.mark_dirty()
            self.save(force=True)
            print(f"[UNBAN] User {uid} has been unbanned. Updated banned list: {self.banned_data['banned']}")
            return True
        else:
            print(f"[UNBAN] User {uid} was not in banned list")
            return False

    def is_admin(self, uid):
        cache_key = f"admin_{uid}"
        if cache_key in admin_cache:
            return admin_cache[cache_key]

        result = str(uid) in self.data["admins"]
        admin_cache[cache_key] = result
        return result

    def is_owner(self, uid):
        cache_key = f"owner_{uid}"
        if cache_key in admin_cache:
            return admin_cache[cache_key]

        result = str(uid) in self.data["owners"]
        admin_cache[cache_key] = result
        return result

    def is_main_owner(self, uid):
        return uid == OWNER_ID

    def add_admin(self, uid):
        uid_str = str(uid)
        if uid_str not in self.data["admins"]:
            self.data["admins"].append(uid_str)
            admin_cache.clear()
            self.mark_dirty()
            self.save(force=True)

    def add_owner(self, uid):
        uid_str = str(uid)
        if uid_str not in self.data["owners"]:
            self.data["owners"].append(uid_str)
            admin_cache.clear()
            self.mark_dirty()
            self.save(force=True)

    def remove_admin(self, uid):
        uid_str = str(uid)
        if uid_str in self.data["admins"]:
            self.data["admins"].remove(uid_str)
            admin_cache.clear()
            self.mark_dirty()
            self.save(force=True)

    def remove_owner(self, uid):
        uid_str = str(uid)
        if uid_str in self.data["owners"]:
            self.data["owners"].remove(uid_str)
            admin_cache.clear()
            self.mark_dirty()
            self.save(force=True)

    def get_all_admins(self):
        return self.data["admins"]

    def get_all_owners(self):
        return self.data["owners"]

    def clear_all_admins(self):
        """حذف جميع الإداريين"""
        removed_admins = self.data["admins"].copy()
        self.data["admins"] = []
        admin_cache.clear()
        self.mark_dirty()
        self.save(force=True)
        return removed_admins

    def clear_all_owners(self):
        """حذف جميع الملاك"""
        removed_owners = self.data["owners"].copy()
        self.data["owners"] = []
        admin_cache.clear()
        self.mark_dirty()
        self.save(force=True)
        return removed_owners

    def is_section_enabled(self, uid, section):
        """التحقق من تفعيل القسم - الافتراضي مفعل (True)"""
        uid_str = str(uid)
        if "disabled_sections" not in self.data:
            self.data["disabled_sections"] = {}
        if uid_str not in self.data["disabled_sections"]:
            self.data["disabled_sections"][uid_str] = {}
        # إذا لم يكن في disabled_sections، يعني مفعل (True)
        # إذا كان موجود وقيمته True، يعني معطل
        return not self.data["disabled_sections"][uid_str].get(section, False)

    def disable_section(self, uid, section):
        """تعطيل قسم (عند حفظ تفضيل)"""
        uid_str = str(uid)
        if "disabled_sections" not in self.data:
            self.data["disabled_sections"] = {}
        if uid_str not in self.data["disabled_sections"]:
            self.data["disabled_sections"][uid_str] = {}
        self.data["disabled_sections"][uid_str][section] = True
        self.mark_dirty()

    def enable_section(self, uid, section):
        """تفعيل قسم (عند كتابة ريست)"""
        uid_str = str(uid)
        if "disabled_sections" not in self.data:
            self.data["disabled_sections"] = {}
        if uid_str not in self.data["disabled_sections"]:
            self.data["disabled_sections"][uid_str] = {}
        self.data["disabled_sections"][uid_str][section] = False
        self.mark_dirty()

    def enable_all_sections(self, uid):
        """تفعيل جميع الأقسام (عند كتابة ريست بدون قسم محدد)"""
        uid_str = str(uid)
        all_sections = ["جمم", "ويكي", "مس", "اص", "صج", "شك", "جش", "قص", "نص", "طب", "شرط", "فكك", "دبل", "تر", "عكس", "فر", "E", "رق", "حر", "جب", "كرر"]
        if "disabled_sections" not in self.data:
            self.data["disabled_sections"] = {}
        if uid_str not in self.data["disabled_sections"]:
            self.data["disabled_sections"][uid_str] = {}
        for section in all_sections:
            self.data["disabled_sections"][uid_str][section] = False
        self.mark_dirty()
        self.save(force=True)

    def update_score(self, uid, typ, wpm, device_type=None):
        # التحقق من تفعيل القسم - إذا كان معطل، ما نحفظ النقطة
        if not self.is_section_enabled(uid, typ):
            return

        # قائمة الأقسام المعروضة في الصدارة فقط
        leaderboard_sections = ["كرر", "ويكي", "مس", "شك", "جب", "جش", "جمم"]
        
        # إذا لم يكن القسم في قائمة الصدارة، لا نحفظ النقطة
        if typ not in leaderboard_sections:
            return

        # منع حفظ الصدارة عند تفضيل عدد كلمات منخفض
        uid_str = str(uid)
        pref = None
        if "preferences" in self.data and uid_str in self.data["preferences"]:
            pref = self.data["preferences"][uid_str].get(typ)

        if pref is not None and pref < 10:
            return

        # احصل على device_type إذا لم يُمرر
        if device_type is None:
            device_type = self.device_types_data.get(uid_str, "جوال")  # الجوال افتراضي

        key = f"{uid}_{typ}_{device_type}"
        old_score = self.leaderboard_data["scores"].get(key, 0)
        self.leaderboard_data["scores"][key] = max(old_score, wpm)
        # إزالة save_leaderboard() الفوري - الحفظ يتم عبر النظام العام

        print(f"[SCORE] User {uid} - Section {typ} - WPM: {wpm:.1f} - Old: {old_score:.1f} - Saved: {self.leaderboard_data['scores'][key]:.1f}")

        if "low_word_count_scores" not in self.data:
            self.data["low_word_count_scores"] = {}

        # التحقق من تفضيلات المستخدم
        if pref is not None:
            should_flag = False
            if typ in leaderboard_sections and pref < 10:
                should_flag = True
            elif typ == "كرر" and pref < 3:
                should_flag = True

            if should_flag:
                self.data["low_word_count_scores"][key] = True
            else:
                # أزل الراية إن وجدت
                self.data["low_word_count_scores"].pop(key, None)

        self.mark_dirty()
        # إزالة save(force=True) الفوري - الحفظ يتم عبر النظام العام

    def get_score(self, uid, typ, device_type=None):
        if device_type is None:
            uid_str = str(uid)
            device_type = self.device_types_data.get(uid_str, "جوال")
        return self.leaderboard_data["scores"].get(f"{uid}_{typ}_{device_type}", 0)

    def get_rank_in_leaderboard(self, uid, typ, device_type=None):
        lb = self.get_leaderboard(typ, device_type=device_type)
        if lb is None:
            return None
        for rank, (lb_uid, username, first_name, wpm) in enumerate(lb, 1):
            if lb_uid == str(uid):
                return rank
        return None

    def get_best_score(self, uid, typ):
        """الحصول على أفضل رقم سابق للمستخدم في قسم معين"""
        if "best_scores" not in self.leaderboard_data:
            self.leaderboard_data["best_scores"] = {}
        key = f"{uid}_{typ}"
        return self.leaderboard_data["best_scores"].get(key, 0)

    def update_best_score(self, uid, typ, wpm):
        """تحديث أفضل رقم وإرجاع ما إذا كان رقم جديد"""
        if "best_scores" not in self.leaderboard_data:
            self.leaderboard_data["best_scores"] = {}

        key = f"{uid}_{typ}"
        old_best = self.leaderboard_data["best_scores"].get(key, 0)

        # إذا كان الرقم الجديد أفضل من القديم
        if wpm > old_best:
            self.leaderboard_data["best_scores"][key] = wpm
            self.save_leaderboard()
            self.mark_dirty()
            return True  # رقم جديد كُسر

        return False  # لم يكسر رقم جديد

    def get_leaderboard_record(self, typ, device_type=None):
        """الحصول على أعلى رقم في الصدارة الحالية (الرقم الأول)"""
        lb = self.get_leaderboard(typ, device_type=device_type)
        if lb:
            return lb[0][3]  # إرجاع أعلى رقم WPM
        return 0

    def add_pattern(self, uid, key):
        if str(uid) not in self.data["patterns"]:
            self.data["patterns"][str(uid)] = []
        if key not in self.data["patterns"][str(uid)]:
            self.data["patterns"][str(uid)].append(key)
            self.mark_dirty()

    def is_pattern_used(self, uid, key):
        return key in self.data["patterns"].get(str(uid), [])

    def clear_patterns(self, uid):
        self.data["patterns"][str(uid)] = []
        self.mark_dirty()

    def save_session(self, uid, cid, typ, txt, tm, sent=False, random_mode=True, watermarked_text=None):
        key = f"{cid}_{typ}"
        self.data["sessions"][key] = {
            "type": typ,
            "text": txt,
            "time": tm,
            "starter_uid": uid,
            "sent": sent,
            "random_mode": random_mode,
            "watermarked_text": watermarked_text,
            "last_attempt_time": tm,  # آخر محاولة إجابة
            "attempts_count": 0,  # عدد محاولات الإجابة
            "wrong_attempts": {}  # محاولات خاطئة لكل مستخدم (لنظام التعديل/التصحيح)
        }
        self.mark_dirty()

    def record_wrong_attempt(self, cid, typ, uid, text):
        """تسجيل آخر محاولة خاطئة لمستخدم على جلسة (عشان نظام التعديل)"""
        key = f"{cid}_{typ}"
        if key in self.data["sessions"]:
            session = self.data["sessions"][key]
            if "wrong_attempts" not in session:
                session["wrong_attempts"] = {}
            session["wrong_attempts"][str(uid)] = {"text": text, "time": time.time()}
            self.mark_dirty()

    def save_preference_range(self, uid, section, lo, hi):
        """حفظ نطاق كلمات (من X الى Y) لقسم"""
        self.save_preference(uid, f"{section}__range", [lo, hi])

    def update_session_attempt(self, cid, typ):
        """تحديث معلومات محاولة الإجابة على جلسة"""
        key = f"{cid}_{typ}"
        if key in self.data["sessions"]:
            self.data["sessions"][key]["last_attempt_time"] = time.time()
            self.data["sessions"][key]["attempts_count"] = self.data["sessions"][key].get("attempts_count", 0) + 1
            self.mark_dirty()



    def get_session(self, cid, typ):
        return self.data["sessions"].get(f"{cid}_{typ}")

    def get_all_active_sessions(self, cid):
        expired_keys = []
        active_sessions = []

        for key, session in list(self.data["sessions"].items()):
            if key.startswith(f"{cid}_"):
                elapsed = time.time() - session.get("time", 0)
                session_type = session.get("type", "")
                is_match_session = session_type.startswith("match_")

                # جلسات أون لاين: 3 دقائق | جلسات عادية: دقيقة واحدة
                timeout = 180 if is_match_session else 60

                # للجلسات التي لم تُقبل بدقة 100% (attempts_count > 0)
                # إذا مضى أكثر من 60 ثانية منذ محاولة الإجابة الأخيرة، حذفها
                if session.get("attempts_count", 0) > 0:
                    last_attempt = session.get("last_attempt_time", session.get("time", 0))
                    elapsed_since_attempt = time.time() - last_attempt
                    if elapsed_since_attempt > 60:  # 60 ثانية منذ آخر محاولة
                        expired_keys.append(key)
                        continue

                if elapsed <= timeout:
                    active_sessions.append(session)
                else:
                    expired_keys.append(key)

        for key in expired_keys:
            self.data["sessions"].pop(key, None)
        if expired_keys:
            self.mark_dirty()

        return active_sessions

    def del_session(self, cid, typ):
        self.data["sessions"].pop(f"{cid}_{typ}", None)
        self.mark_dirty()

    def cancel_user_session_in_type(self, uid, cid, typ):
        key = f"{cid}_{typ}"
        session = self.data["sessions"].get(key)
        if session and session.get("starter_uid") == uid:
            self.data["sessions"].pop(key, None)
            self.mark_dirty()
            return True
        return False

    def get_leaderboard(self, typ, device_type=None):
        """الحصول على صدارة القسم - تدعم كلا الصيغ (القديمة والجديدة)"""
        # لا تعرض التخصيصات في الصدارة
        if typ == "خصص":
            return None

        scores = {}  # uid -> (uid, username, first_name, wpm)
        removed_list = self.leaderboard_data.get("removed_from_leaderboard", {})

        for k, v in self.leaderboard_data["scores"].items():
            uid = None
            section = None
            key_device_type = None

            # جرب تفكيك المفتاح
            # الصيغ الممكنة:
            # 1. القديمة: uid_section (مثل: 5562144078_كرر)
            # 2. الجديدة: uid_section_device_type (مثل: 5562144078_كرر_جوال)

            # ابدأ بالفصل من النهاية
            parts = k.split('_')
            if len(parts) < 2:
                continue

            # آخر جزء قد يكون device_type
            last_part = parts[-1]
            is_device_type = last_part in ["جوال", "خارجي"]

            if is_device_type and len(parts) >= 3:
                # صيغة جديدة: uid_section_device_type
                uid = parts[0]
                section = '_'.join(parts[1:-1])  # كل ما بين الأول والأخير
                key_device_type = parts[-1]
            elif not is_device_type and len(parts) >= 2:
                # صيغة قديمة: uid_section
                uid = parts[0]
                section = '_'.join(parts[1:])
                key_device_type = None
            else:
                continue

            # تحقق من تطابق القسم
            if section != typ:
                continue

            # تخطي المستخدمين المحذوفين
            if uid in removed_list:
                continue

            # احصل على device_type الفعلي للمستخدم
            try:
                uid_int = int(uid)
                user_device_type = self.get_device_type(uid_int)
            except (ValueError, TypeError):
                continue

            # إذا لم يكن لديه device_type، استخدم جوال كافتراضي
            if user_device_type is None:
                user_device_type = "جوال"

            # إذا كانت البيانات القديمة بدون device_type في المفتاح، احصل عليها من المستخدم
            if key_device_type is None:
                key_device_type = user_device_type

            # إذا كنا نبحث عن device_type معين، تحقق من التطابق
            if device_type and key_device_type != device_type:
                continue

            # احصل على بيانات المستخدم
            user_data = self.data["users"].get(uid, {})
            username = user_data.get("username")
            first_name = user_data.get("first_name", "مستخدم")

            # خزن أفضل نتيجة لهذا المستخدم
            if uid not in scores or v > scores[uid][3]:
                scores[uid] = (uid, username, first_name, v)

        # حول dict إلى list وصنف
        scores_list = list(scores.values())
        scores_list.sort(key=lambda x: x[3], reverse=True)
        return scores_list

    def add_award(self, uid, name, wpm, typ, position=None, week=None):
        if str(uid) not in self.data["weekly_awards"]:
            self.data["weekly_awards"][str(uid)] = []

        self.data["weekly_awards"][str(uid)].append({
            "name": name,
            "wpm": wpm,
            "type": typ,
            "position": position,
            "week": week,
            "date": datetime.now().isoformat()
        })
        self.mark_dirty()

    def get_awards(self, uid):
        return self.data["weekly_awards"].get(str(uid), [])

    def reset_leaderboard(self):
        """ريست الصدارة وتوزيع الجوائز على الخمسة الأوائل في كل قسم"""
        if "leaderboard_resets" not in self.data:
            self.data["leaderboard_resets"] = 0

        self.data["leaderboard_resets"] += 1
        week = self.data["leaderboard_resets"]

        # جميع الأقسام (محددة للعرض في الصدارة)
        all_sections = ["كرر", "ويكي", "مس", "شك", "جب", "جش", "جمم"]

        # توزيع الجوائز لكلا جهازي: جوال وخارجي
        for device_type in ["جوال", "خارجي"]:
            for section_type in all_sections:
                lb = self.get_leaderboard(section_type, device_type=device_type)
                if lb:
                    for position, (uid_str, username, first_name, wpm) in enumerate(lb[:5], 1):
                        name = f"@{username}" if username else first_name
                        self.add_award(int(uid_str), name, wpm, section_type, position=position, week=week)

        # حذف جميع النتائج (مسح الصدارة)
        self.leaderboard_data["scores"] = {}
        self.leaderboard_data["removed_from_leaderboard"] = {}
        self.leaderboard_data["best_scores"] = {}
        self.save_leaderboard()

        self.mark_dirty()
        self.save(force=True)
        return week

    def remove_from_leaderboard(self, uid):
        """حذف مستخدم من جميع الصدارات بشكل دائم"""
        #  المالك الأساسي محمي من الحذف من الصدارة
        if self.is_main_owner(uid):
            print(f"[LEADERBOARD] Cannot remove primary owner {uid} from leaderboard")
            return []

        uid_str = str(uid)
        removed_types = set()  # استخدم set لتجنب التكرار

        # إضافة المستخدم لقائمة المحذوفين
        if "removed_from_leaderboard" not in self.leaderboard_data:
            self.leaderboard_data["removed_from_leaderboard"] = {}
        self.leaderboard_data["removed_from_leaderboard"][uid_str] = True
        self.save_leaderboard()

        # إنشاء نظيفة backup للأرقام قبل الحذف
        if "leaderboard_backups" not in self.data:
            self.data["leaderboard_backups"] = {}

        backup_data = {}

        # البحث عن جميع مفاتيح الصدارة للمستخدم
        keys_to_remove = []
        for k in self.leaderboard_data["scores"].keys():
            if k.startswith(f"{uid_str}_"):
                keys_to_remove.append(k)
                # حفظ البيانات في backup قبل الحذف
                backup_data[k] = self.leaderboard_data["scores"][k]
                # استخراج نوع القسم من المفتاح
                # الصيغ: uid_section أو uid_section_device_type
                parts = k.split('_')
                if len(parts) >= 2:
                    # أول جزء هو uid
                    # آخر جزء قد يكون device_type
                    if parts[-1] in ["جوال", "خارجي"]:
                        # صيغة جديدة: خذ القسم بدون device_type
                        section_type = '_'.join(parts[1:-1])
                    else:
                        # صيغة قديمة: خذ كل شيء بعد uid
                        section_type = '_'.join(parts[1:])

                    if section_type:
                        removed_types.add(section_type)

        # حفظ البيانات في backup
        if backup_data:
            self.data["leaderboard_backups"][uid_str] = backup_data

        # حذف المفاتيح
        for k in keys_to_remove:
            self.leaderboard_data["scores"].pop(k, None)

        if keys_to_remove:
            self.save_leaderboard()
            self.mark_dirty()
            self.save(force=True)

        return list(removed_types)

    def restore_from_leaderboard(self, uid, restore_scores=False):
        """إرجاع مستخدم للصدارة
        restore_scores: إذا كان True، استعيد الأرقام السابقة أيضاً
        """
        uid_str = str(uid)
        if "removed_from_leaderboard" not in self.leaderboard_data:
            self.leaderboard_data["removed_from_leaderboard"] = {}

        if uid_str in self.leaderboard_data["removed_from_leaderboard"]:
            self.leaderboard_data["removed_from_leaderboard"].pop(uid_str, None)
            self.save_leaderboard()

            # استعادة الأرقام إذا كانت مطلوبة
            if restore_scores:
                if "leaderboard_backups" not in self.data:
                    self.data["leaderboard_backups"] = {}

                if uid_str in self.data["leaderboard_backups"]:
                    # استعيد جميع الأرقام من النسخة الاحتياطية
                    backup_data = self.data["leaderboard_backups"][uid_str]
                    for k, v in backup_data.items():
                        self.leaderboard_data["scores"][k] = v
                    self.save_leaderboard()
                    # حذف النسخة الاحتياطية بعد الاستعادة
                    self.data["leaderboard_backups"].pop(uid_str, None)

            self.mark_dirty()
            return True
        return False

    def is_removed_from_leaderboard(self, uid):
        """التحقق إذا كان المستخدم محذوفاً من الصدارة"""
        #  المالك الأساسي لا يمكن أن يكون محذوفاً من الصدارة
        if self.is_main_owner(uid):
            return False

        if "removed_from_leaderboard" not in self.leaderboard_data:
            self.leaderboard_data["removed_from_leaderboard"] = {}
        return str(uid) in self.leaderboard_data["removed_from_leaderboard"]

    def remove_section_scores(self, uid, section, device_type):
        """حذف أرقام مستخدم من قسم محدد مع الاحتفاظ بظهوره في الصدارة بدون أرقام
        
        Args:
            uid: معرف المستخدم
            section: اسم القسم (مثل: كرر، جوال، الخ)
            device_type: نوع الجهاز (جوال أو خارجي)
        
        Returns:
            True إذا تم حذف الأرقام بنجاح، False إذا لم يتم العثور على أرقام
        """
        if self.is_main_owner(uid):
            print(f"[LEADERBOARD] Cannot remove scores from primary owner {uid}")
            return False
        
        uid_str = str(uid)
        found_and_removed = False
        
        if "section_scores_backup" not in self.data:
            self.data["section_scores_backup"] = {}
        
        if uid_str not in self.data["section_scores_backup"]:
            self.data["section_scores_backup"][uid_str] = {}
        
        keys_to_remove = []
        for k in list(self.data["scores"].keys()):
            if not k.startswith(f"{uid_str}_"):
                continue
            
            parts = k.split('_')
            if len(parts) < 2:
                continue
            
            key_device_type = None
            key_section = None
            
            if parts[-1] in ["جوال", "خارجي"]:
                key_device_type = parts[-1]
                key_section = '_'.join(parts[1:-1])
            else:
                key_section = '_'.join(parts[1:])
                key_device_type = self.device_types_data.get(uid_str, "جوال")
            
            if key_section == section and key_device_type == device_type:
                self.data["section_scores_backup"][uid_str][k] = self.leaderboard_data["scores"][k]
                keys_to_remove.append(k)
                found_and_removed = True
        
        for k in keys_to_remove:
            self.leaderboard_data["scores"].pop(k, None)
        
        if found_and_removed:
            self.save_leaderboard()
            self.mark_dirty()
            self.save(force=True)
        
        return found_and_removed

    def add_to_matchmaking_queue(self, uid, user_data):
        """إضافة مستخدم لقائمة الانتظار"""
        if "matchmaking_queue" not in self.data:
            self.data["matchmaking_queue"] = []

        # تجنب التكرار
        existing = [u for u in self.data["matchmaking_queue"] if u["uid"] == uid]
        if not existing:
            self.data["matchmaking_queue"].append({
                "uid": uid,
                "username": user_data.get("username"),
                "first_name": user_data.get("first_name"),
                "joined_at": time.time()
            })
            self.mark_dirty()
            return True
        return False

    def remove_from_matchmaking_queue(self, uid):
        """إزالة مستخدم من قائمة الانتظار"""
        if "matchmaking_queue" not in self.data:
            return False

        before_len = len(self.data["matchmaking_queue"])
        self.data["matchmaking_queue"] = [u for u in self.data["matchmaking_queue"] if u["uid"] != uid]

        if len(self.data["matchmaking_queue"]) < before_len:
            self.mark_dirty()
            return True
        return False

    def save_speed_for_section(self, uid, section, wpm):
        """حفظ السرعة مع عداد كلي واحد من 12 قسم + كرر منفصل"""
        uid_str = str(uid)

        # الأقسام الـ 13 المسموحة (بدون كرر)
        allowed_sections = ["ويكي", "مس", "جمم", "صج", "نص", "قص", "فكك", "حر", "رق", "عكس", "جش", "شك", "جب"]

        # Fallback إلى JSON (MongoDB معطل في Replit)
        if "average_speeds" not in self.data:
            self.data["average_speeds"] = {}

        if uid_str not in self.data["average_speeds"]:
            self.data["average_speeds"][uid_str] = {
                "combined": {
                    "speeds": [],
                    "correct_count": 0,
                    "finalized": False,
                    "section_averages": {s: None for s in allowed_sections}
                },
                "repeat": {
                    "speeds": [],
                    "correct_count": 0,
                    "finalized": False,
                    "average": None
                }
            }

        # إذا كانت البنية قديمة، أضف repeat
        if "repeat" not in self.data["average_speeds"][uid_str]:
            self.data["average_speeds"][uid_str]["repeat"] = {
                "speeds": [],
                "correct_count": 0,
                "finalized": False,
                "average": None
            }

        # معالجة كرر منفصل
        if section == "كرر":
            repeat_data = self.data["average_speeds"][uid_str]["repeat"]
            if repeat_data["finalized"]:
                return
            repeat_data["speeds"].append(wpm)
            repeat_data["correct_count"] += 1
            if repeat_data["correct_count"] >= 100:
                repeat_data["average"] = sum(repeat_data["speeds"]) / len(repeat_data["speeds"])
                repeat_data["speeds"] = []
                repeat_data["finalized"] = True
                print(f"[SPEED] تم تحديث متوسط كرر {uid_str}: {repeat_data['average']:.1f} WPM")
            self.mark_dirty()
            return

        # معالجة الـ 12 قسم الأخرى
        if section not in allowed_sections:
            return

        combined_data = self.data["average_speeds"][uid_str]["combined"]

        # إذا تم تحقيق 100 جملة صحيحة، لا تحفظ سرعات إضافية
        if combined_data["finalized"]:
            return

        # أضف السرعة مع اسم القسم
        combined_data["speeds"].append({"section": section, "wpm": wpm})
        combined_data["correct_count"] += 1

        # بعد 100 جملة صحيحة: احسب متوسط لكل قسم وحذف السرعات الفردية
        if combined_data["correct_count"] >= 100:
            # احسب متوسط لكل قسم
            section_speeds = {}
            for item in combined_data["speeds"]:
                sec = item["section"]
                speed = item["wpm"]
                if sec not in section_speeds:
                    section_speeds[sec] = []
                section_speeds[sec].append(speed)

            # احسب المتوسط لكل قسم
            for sec in allowed_sections:
                if sec in section_speeds and section_speeds[sec]:
                    avg = sum(section_speeds[sec]) / len(section_speeds[sec])
                    combined_data["section_averages"][sec] = avg
                else:
                    combined_data["section_averages"][sec] = None

            # حذف السرعات الفردية، احفظ المتوسطات فقط
            combined_data["speeds"] = []
            combined_data["finalized"] = True
            print(f"[SPEED] تم تحديث متوسطات سرعة {uid_str} من 12 قسم (100 جملة)")

        self.mark_dirty()

    def get_average_speed(self, uid, section):
        """الحصول على متوسط السرعة للقسم من البنية الجديدة"""
        uid_str = str(uid)

        # Fallback إلى JSON
        if "average_speeds" not in self.data:
            return None

        if uid_str not in self.data["average_speeds"]:
            return None

        # البنية الجديدة: يتم الحفاظ على section_averages
        if "combined" in self.data["average_speeds"][uid_str]:
            combined_data = self.data["average_speeds"][uid_str]["combined"]
            if "section_averages" in combined_data:
                return combined_data["section_averages"].get(section)

        return None

    def get_overall_average_speed(self, uid):
        """الحصول على المتوسط الكلي من 12 قسم"""
        uid_str = str(uid)

        # الأقسام الـ 13
        allowed_sections = ["ويكي", "مس", "جمم", "صج", "نص", "قص", "فكك", "حر", "رق", "عكس", "جش", "شك", "جب"]

        if "average_speeds" not in self.data or uid_str not in self.data["average_speeds"]:
            return 0

        if "combined" not in self.data["average_speeds"][uid_str]:
            return 0

        combined_data = self.data["average_speeds"][uid_str]["combined"]
        if "section_averages" not in combined_data:
            return 0

        # احسب متوسط من جميع الأقسام التي لها متوسط
        averages = []
        for section in allowed_sections:
            avg = combined_data["section_averages"].get(section)
            if avg is not None:
                averages.append(avg)

        if not averages:
            return 0

        return sum(averages) / len(averages)

    def find_match(self, uid, search_start_time=None):
        """البحث عن خصم - مع تطبيق ذكي:
        - أول 20 ثانية: ±20 WPM فقط (من 12 قسم)
        - آخر 10 ثواني (بعد 20): أي خصم متاح
        - إجمالي: 30 ثانية
        - يستخدم متوسط 13 قسم: ويكي, مس, كرر, جمم, صج, نص, قص, فكك, حر, رق, عكس, جش, شك, جب
        """
        if "matchmaking_queue" not in self.data:
            self.data["matchmaking_queue"] = []

        # تحديد ما إذا كان المبحث نطاقياً أم حراً (بناءً على الوقت المنقضي)
        strict_match = True
        if search_start_time:
            elapsed = time.time() - search_start_time
            if elapsed >= 20:  # بعد 20 ثانية، اقبل أي خصم
                strict_match = False

        # الحصول على المتوسط الكلي للاعب الحالي من 12 قسم
        current_avg = self.get_overall_average_speed(uid)

        # البحث عن خصم
        for i, player in enumerate(self.data["matchmaking_queue"]):
            if player["uid"] != uid:
                opponent_uid = player["uid"]

                # إذا لم يكن هناك متوسط للاعب الحالي، خذ أي خصم
                if not current_avg:
                    opponent = self.data["matchmaking_queue"].pop(i)
                    # حذف المستخدم الحالي من القائمة أيضاً
                    self.data["matchmaking_queue"] = [p for p in self.data["matchmaking_queue"] if p["uid"] != uid]
                    self.mark_dirty()
                    self.save(force=True)
                    return opponent

                # الحصول على المتوسط الكلي للخصم من 12 قسم
                opponent_avg = self.get_overall_average_speed(opponent_uid)

                # تحديد معيار المطابقة
                if strict_match:
                    # أول 20 ثانية: ±20 WPM أو بدون متوسط للخصم
                    if not opponent_avg or abs(current_avg - opponent_avg) <= 20:
                        opponent = self.data["matchmaking_queue"].pop(i)
                        # حذف المستخدم الحالي من القائمة أيضاً
                        self.data["matchmaking_queue"] = [p for p in self.data["matchmaking_queue"] if p["uid"] != uid]
                        self.mark_dirty()
                        self.save(force=True)
                        return opponent
                else:
                    # بعد 20 ثانية: أي خصم
                    opponent = self.data["matchmaking_queue"].pop(i)
                    # حذف المستخدم الحالي من القائمة أيضاً
                    self.data["matchmaking_queue"] = [p for p in self.data["matchmaking_queue"] if p["uid"] != uid]
                    self.mark_dirty()
                    self.save(force=True)
                    return opponent

        return None

    def create_matchmaking_game(self, game_id, player1_uid, player2_uid, player1_data, player2_data, encounter_count=1):
        """إنشاء لعبة matchmaking جديدة"""
        if "matchmaking_games" not in self.data:
            self.data["matchmaking_games"] = {}

        self.data["matchmaking_games"][str(game_id)] = {
            "player1": {
                "uid": player1_uid,
                "username": player1_data.get("username"),
                "first_name": player1_data.get("first_name"),
                "wins": 0,
                "ready": False
            },
            "player2": {
                "uid": player2_uid,
                "username": player2_data.get("username"),
                "first_name": player2_data.get("first_name"),
                "wins": 0,
                "ready": False
            },
            "current_round": 0,
            "created_at": time.time(),
            "status": "active",
            "last_section": None,
            "current_sentence": None,
            "encounter_count": encounter_count
        }
        self.mark_dirty()
        self.save(force=True)

    def get_matchmaking_game(self, game_id):
        """الحصول على لعبة matchmaking"""
        if "matchmaking_games" not in self.data:
            return None
        return self.data["matchmaking_games"].get(str(game_id))

    def update_matchmaking_game(self, game_id, player_uid, won=False, ready=None):
        """تحديث نتائج لعبة matchmaking"""
        if "matchmaking_games" not in self.data:
            return False

        game = self.data["matchmaking_games"].get(str(game_id))
        if not game:
            return False

        if game["player1"]["uid"] == player_uid:
            if won:
                game["player1"]["wins"] += 1
            if ready is not None:
                game["player1"]["ready"] = ready
        elif game["player2"]["uid"] == player_uid:
            if won:
                game["player2"]["wins"] += 1
            if ready is not None:
                game["player2"]["ready"] = ready
        else:
            return False

        self.mark_dirty()
        self.save(force=True)
        return True

    def update_game_section(self, game_id, section):
        """تحديث آخر قسم في لعبة matchmaking"""
        if "matchmaking_games" not in self.data:
            return False

        game = self.data["matchmaking_games"].get(str(game_id))
        if not game:
            return False

        game["last_section"] = section
        self.mark_dirty()
        self.save(force=True)
        return True

    def end_matchmaking_game(self, game_id):
        """إنهاء لعبة matchmaking"""
        if "matchmaking_games" not in self.data:
            return False

        if str(game_id) in self.data["matchmaking_games"]:
            self.data["matchmaking_games"][str(game_id)]["status"] = "finished"
            self.mark_dirty()
            self.save(force=True)
            return True
        return False

    def get_online_stats(self, uid):
        """الحصول على إحصائيات لاعب في وضع أون لاين"""
        wins = 0
        losses = 0
        surrenders = 0

        if "matchmaking_games" not in self.data:
            return {"wins": 0, "losses": 0, "surrenders": 0}

        for game_id, game in self.data["matchmaking_games"].items():
            if game.get("status") != "finished":
                continue

            player1 = game.get("player1", {})
            player2 = game.get("player2", {})

            # تحديد من هو اللاعب المطلوب
            if player1.get("uid") == uid:
                player_data = player1
                opponent_data = player2
                opponent_uid = player2.get("uid")
            elif player2.get("uid") == uid:
                player_data = player2
                opponent_data = player1
                opponent_uid = player1.get("uid")
            else:
                continue

            # التحقق من الانسحاب
            if game.get("surrender_by"):
                if game.get("surrender_by") == uid:
                    # هذا اللاعب انسحب
                    surrenders += 1
                else:
                    # الخصم انسحب، هذا اللاعب فاز
                    wins += 1
            else:
                # لا انسحاب - تحديد الفائز بالنقاط
                player_wins = player_data.get("wins", 0)
                opponent_wins = opponent_data.get("wins", 0)

                if player_wins >= 5:
                    # اللاعب فاز (وصل لـ 5 انتصارات)
                    wins += 1
                elif opponent_wins >= 5:
                    # الخصم فاز
                    losses += 1
                else:
                    # حالة نادرة - لا أحد وصل لـ 5 (لا انسحاب)
                    surrenders += 1

        return {"wins": wins, "losses": losses, "surrenders": surrenders}

    def log_cmd(self, cmd):
        dt = datetime.now().strftime("%Y-%m-%d")
        if dt not in self.data["stats"]:
            self.data["stats"][dt] = {}
        if cmd not in self.data["stats"][dt]:
            self.data["stats"][dt][cmd] = 0
        self.data["stats"][dt][cmd] += 1

    def track_message_sent(self):
        dt = datetime.now().strftime("%Y-%m-%d")
        if dt not in self.data["messages_sent"]:
            self.data["messages_sent"][dt] = 0
        self.data["messages_sent"][dt] += 1
        self.mark_dirty()

    def get_level_info(self, uid):
        uid_str = str(uid)
        if "levels" not in self.data:
            self.data["levels"] = {}
        if uid_str not in self.data["levels"]:
            self.data["levels"][uid_str] = {"level": 1, "progress": 0}
        return self.data["levels"][uid_str]

    def get_level_requirement(self, level):
        return 5 * level

    def add_correct_sentence(self, uid):
        uid_str = str(uid)
        if "levels" not in self.data:
            self.data["levels"] = {}
        if uid_str not in self.data["levels"]:
            self.data["levels"][uid_str] = {"level": 1, "progress": 0}

        level_data = self.data["levels"][uid_str]
        current_level = level_data["level"]
        current_progress = level_data["progress"]
        requirement = self.get_level_requirement(current_level)

        current_progress += 1

        if current_progress >= requirement:
            level_data["level"] += 1
            level_data["progress"] = 0
        else:
            level_data["progress"] = current_progress

        self.mark_dirty()
        return level_data

    def set_broadcast_mode(self, uid, status):
        self.data["broadcast_mode"][str(uid)] = status
        self.mark_dirty()
        self.save(force=True)

    def get_broadcast_mode(self, uid):
        return self.data["broadcast_mode"].get(str(uid), False)

    def start_round(self, cid, target, starter_uid=None):
        self.data["rounds"][str(cid)] = {
            "target": target,
            "wins": {},
            "started_at": datetime.now().isoformat(),
            "last_activity": time.time(),
            "starter_uid": starter_uid,
            "starter_actions": {}
        }
        self.mark_dirty()

    def update_round_activity(self, cid):
        if str(cid) in self.data["rounds"]:
            self.data["rounds"][str(cid)]["last_activity"] = time.time()
            self.mark_dirty()

    def get_round(self, cid):
        return self.data["rounds"].get(str(cid))

    def end_round(self, cid):
        # حفظ النتائج والوقت قبل إغلاق الجولة
        if str(cid) in self.data["rounds"]:
            round_data = self.data["rounds"][str(cid)]
            # حفظ النتائج السابقة
            self.data["previous_round_results"] = self.data.get("previous_round_results", {})
            self.data["previous_round_results"][str(cid)] = {
                "wins": round_data.get("wins", {}),
                "target": round_data.get("target", 1),
                "starter_uid": round_data.get("starter_uid")
            }
            # حفظ وقت الانتهاء
            self.data["round_end_times"] = self.data.get("round_end_times", {})
            self.data["round_end_times"][str(cid)] = time.time()
            self.mark_dirty()
        self.data["rounds"].pop(str(cid), None)
        self.mark_dirty()

    def add_win(self, cid, uid):
        if str(cid) not in self.data["rounds"]:
            return False

        if str(uid) not in self.data["rounds"][str(cid)]["wins"]:
            self.data["rounds"][str(cid)]["wins"][str(uid)] = 0

        self.data["rounds"][str(cid)]["wins"][str(uid)] += 1
        # اعتبر أي إضافة نقطة نشاطاً يمدد عمر الجولة
        self.data["rounds"][str(cid)]["last_activity"] = time.time()
        self.mark_dirty()
        return self.data["rounds"][str(cid)]["wins"][str(uid)]

    def reduce_round_points(self, cid, uid, points):
        """تقليل نقاط المستخدم في الجولة"""
        if str(cid) not in self.data["rounds"]:
            return False

        if str(uid) not in self.data["rounds"][str(cid)]["wins"]:
            return False

        current_points = self.data["rounds"][str(cid)]["wins"][str(uid)]
        new_points = max(0, current_points - points)
        self.data["rounds"][str(cid)]["wins"][str(uid)] = new_points
        # اعتبر أي خصم نقطة نشاطاً يمدد عمر الجولة
        self.data["rounds"][str(cid)]["last_activity"] = time.time()
        self.mark_dirty()
        return True

    def set_round_extension_status(self, cid, status):
        """تعيين حالة انتظار التمديد للجولة - الجولة تنتهي لكن تبقى محفوظة"""
        if str(cid) in self.data["rounds"]:
            self.data["rounds"][str(cid)]["is_finished"] = status
            # حفظ وقت البداية للمهلة الزمنية (دقيقتين)
            if status:
                self.data["round_end_times"] = self.data.get("round_end_times", {})
                self.data["round_end_times"][str(cid)] = time.time()
            else:
                self.data.get("round_end_times", {}).pop(str(cid), None)
            self.mark_dirty()
            self.save(force=True)  # حفظ فوري

    def get_round_extension_status(self, cid):
        """الحصول على حالة انتظار التمديد"""
        if str(cid) in self.data["rounds"]:
            return self.data["rounds"][str(cid)].get("is_finished", False)
        return False

    def is_round_finished(self, cid):
        """التحقق من انتهاء الجولة"""
        if str(cid) in self.data["rounds"]:
            return self.data["rounds"][str(cid)].get("is_finished", False)
        return False

    def check_extension_timeout(self, cid):
        """التحقق من انتهاء الحد الزمني للتمديد (دقيقتين)"""
        end_times = self.data.get("round_end_times", {})
        if str(cid) in end_times:
            elapsed = time.time() - end_times[str(cid)]
            if elapsed > 120:  # 2 دقيقة = 120 ثانية
                # حفظ النتائج في ملف قبل حذفها
                round_data = self.data["rounds"].get(str(cid))
                if round_data:
                    self.save_round_to_archive(cid, round_data)

                # حذف من الذاكرة تماماً
                end_times.pop(str(cid), None)
                self.data["rounds"].pop(str(cid), None)
                self.data.get("round_extension_awaiting", {}).pop(str(cid), None)
                self.mark_dirty()
                self.save(force=True)
                return True
        return False

    def save_round_to_archive(self, cid, round_data):
        """حفظ نتائج الجولة في ملف أرشيف"""
        try:
            import json
            archive_file = "archived_rounds.json"

            # قراءة الملف الموجود
            if os.path.exists(archive_file):
                with open(archive_file, 'r', encoding='utf-8') as f:
                    archive = json.load(f)
            else:
                archive = {}

            # حفظ النتائج الجديدة
            archive[str(cid)] = {
                "round_data": round_data,
                "archived_at": datetime.now().isoformat()
            }

            # كتابة الملف
            with open(archive_file, 'w', encoding='utf-8') as f:
                json.dump(archive, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving round to archive: {e}")

    def extend_round(self, cid, new_target):
        """فتح جولة جديدة مع الحفاظ على النتائج القديمة"""
        if str(cid) not in self.data["rounds"]:
            return False

        # الحصول على النتائج والبيانات القديمة
        old_round = self.data["rounds"].get(str(cid), {})
        old_wins = old_round.get("wins", {})
        old_starter_uid = old_round.get("starter_uid")

        # حذف الجولة القديمة
        self.data["rounds"].pop(str(cid), None)

        # إنشاء جولة جديدة بنفس النتائج والهدف الجديد
        self.data["rounds"][str(cid)] = {
            "target": new_target,
            "wins": dict(old_wins),  # نسخ النتائج القديمة
            "started_at": datetime.now().isoformat(),
            "last_activity": time.time(),
            "starter_uid": old_starter_uid,
            "starter_actions": {},
            "is_finished": False
        }

        # مسح وقت المهلة الزمنية والنتائج السابقة
        self.data.get("round_end_times", {}).pop(str(cid), None)
        self.data.get("previous_round_results", {}).pop(str(cid), None)
        self.data.get("round_extension_awaiting", {}).pop(str(cid), None)

        self.mark_dirty()
        self.save(force=True)

        # التحقق النهائي والتأكد من تعيين is_finished إلى False
        self.data["rounds"][str(cid)]["is_finished"] = False
        self.mark_dirty()
        self.save(force=True)

        return True

    def restart_round_with_previous_results(self, cid, new_target):
        """فتح جولة جديدة بنفس النتائج السابقة"""
        # الحصول على النتائج السابقة
        previous_results = self.data.get("previous_round_results", {}).get(str(cid))
        if not previous_results:
            return False

        # فتح جولة جديدة بنفس النتائج
        self.data["rounds"][str(cid)] = {
            "target": new_target,
            "wins": dict(previous_results.get("wins", {})),  # نسخ النتائج السابقة
            "started_at": datetime.now().isoformat(),
            "last_activity": time.time(),
            "starter_uid": previous_results.get("starter_uid"),
            "starter_actions": {}
        }
        # حذف وقت الانتهاء والنتائج السابقة
        self.data.get("round_end_times", {}).pop(str(cid), None)
        self.data.get("previous_round_results", {}).pop(str(cid), None)
        self.mark_dirty()
        return True

    def add_starter_action(self, cid, uid):
        """تسجيل إجراء من مفتاح الجولة"""
        if str(cid) not in self.data["rounds"]:
            return False

        starter_actions = self.data["rounds"][str(cid)].get("starter_actions", {})
        starter_actions[str(uid)] = starter_actions.get(str(uid), 0) + 1
        self.data["rounds"][str(cid)]["starter_actions"] = starter_actions
        self.mark_dirty()
        return starter_actions.get(str(uid), 0)

    def get_starter_action_count(self, cid, uid):
        """الحصول على عدد إجراءات مفتاح الجولة"""
        if str(cid) not in self.data["rounds"]:
            return 0

        starter_actions = self.data["rounds"][str(cid)].get("starter_actions", {})
        return starter_actions.get(str(uid), 0)

    def set_round_mode(self, cid, status):
        self.data["round_mode"][str(cid)] = status
        self.mark_dirty()

    def get_round_mode(self, cid):
        return self.data["round_mode"].get(str(cid), False)

    def cleanup(self):
        now = time.time()
        to_del = []
        for k, v in self.data["sessions"].items():
            if now - v["time"] > 3600:
                to_del.append(k)

        for k in to_del:
            del self.data["sessions"][k]

        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        for dt in list(self.data["stats"].keys()):
            if dt < month_ago:
                del self.data["stats"][dt]

        if to_del:
            self.mark_dirty()

    def cleanup_inactive_rounds(self):
        now = time.time()
        rounds_to_remove = []

        for cid, round_data in list(self.data["rounds"].items()):
            last_activity = round_data.get("last_activity", 0)
            if now - last_activity > 300:
                rounds_to_remove.append(cid)

        for cid in rounds_to_remove:
            self.data["rounds"].pop(cid, None)

        if rounds_to_remove:
            self.mark_dirty()

        return rounds_to_remove

    def set_pending_round_setup(self, cid, uid, status):
        key = str(cid)
        if status:
            self.data["pending_round_setup"][key] = uid
        else:
            self.data["pending_round_setup"].pop(key, None)
        self.mark_dirty()

    def get_pending_round_setup(self, cid):
        return self.data["pending_round_setup"].get(str(cid))

    def get_round_stats(self, cid):
        round_data = self.get_round(cid)
        if not round_data:
            return None

        target = round_data.get("target", 0)
        wins = round_data.get("wins", {})
        started_at = round_data.get("started_at", "")

        if not wins:
            return f"إحصائيات الجولة الحالية:\n\nالهدف: {target} انتصار\nالمشاركون: لا يوجد بعد\nبدأت: {started_at[:16]}"

        sorted_wins = sorted(wins.items(), key=lambda x: x[1], reverse=True)

        stats_msg = f"إحصائيات الجولة الحالية:\n\nالهدف: {target} انتصار\n\nالمشاركون:\n"

        for idx, (uid, count) in enumerate(sorted_wins, 1):
            user_info = self.data["users"].get(str(uid), {})
            name = user_info.get("first_name", "مستخدم")
            username = user_info.get("username", "")
            display_name = f"@{username}" if username else name
            stats_msg += f"{idx}. {display_name}: {count} انتصار\n"

        stats_msg += f"\nبدأت: {started_at[:16]}"

        return stats_msg

    def start_auto_mode(self, cid, uid, message_thread_id=None):
        if "auto_mode" not in self.data:
            self.data["auto_mode"] = {}

        key = str(cid)
        self.data["auto_mode"][key] = {
            "uid": uid,
            "sections": [],
            "collecting": True,
            "active": False,
            "last_used_section": None,
            "last_activity": time.time(),
            "message_thread_id": message_thread_id
        }
        self.mark_dirty()
        self.save(force=True)

    def add_auto_section(self, cid, section):
        if "auto_mode" not in self.data:
            self.data["auto_mode"] = {}

        key = str(cid)
        if key in self.data["auto_mode"]:
            if section not in self.data["auto_mode"][key]["sections"]:
                self.data["auto_mode"][key]["sections"].append(section)
                self.mark_dirty()
                self.save(force=True)
                return True
        return False

    def finish_auto_collection(self, cid):
        key = str(cid)
        if key in self.data.get("auto_mode", {}):
            self.data["auto_mode"][key]["collecting"] = False
            self.data["auto_mode"][key]["active"] = True
            self.mark_dirty()
            self.save(force=True)
            return True
        return False

    def get_auto_mode(self, cid):
        return self.data.get("auto_mode", {}).get(str(cid))

    def update_auto_activity(self, cid):
        key = str(cid)
        if key in self.data.get("auto_mode", {}):
            self.data["auto_mode"][key]["last_activity"] = time.time()
            self.mark_dirty()

    def set_auto_last_section(self, cid, section):
        key = str(cid)
        if key in self.data.get("auto_mode", {}):
            self.data["auto_mode"][key]["last_used_section"] = section
            self.mark_dirty()

    def end_auto_mode(self, cid):
        key = str(cid)
        if "auto_mode" in self.data and key in self.data["auto_mode"]:
            self.data["auto_mode"].pop(key, None)
            self.mark_dirty()
            self.save(force=True)

    def cleanup_inactive_auto_modes(self):
        if "auto_mode" not in self.data:
            return []

        now = time.time()
        to_remove = []

        for cid, auto_data in list(self.data["auto_mode"].items()):
            last_activity = auto_data.get("last_activity", 0)
            if now - last_activity > 180:
                to_remove.append(cid)

        for cid in to_remove:
            self.data["auto_mode"].pop(cid, None)

        if to_remove:
            self.mark_dirty()
            self.save(force=True)

        return to_remove

    def get_speed_bot_config(self, cid):
        if "speed_bot" not in self.data:
            self.data["speed_bot"] = {}
        return self.data["speed_bot"].get(str(cid), {
            "enabled": False,
            "base_wpm": 160
        })

    def set_speed_bot_enabled(self, cid, enabled):
        if "speed_bot" not in self.data:
            self.data["speed_bot"] = {}
        key = str(cid)
        if key not in self.data["speed_bot"]:
            self.data["speed_bot"][key] = {"enabled": enabled, "base_wpm": 160}
        else:
            self.data["speed_bot"][key]["enabled"] = enabled
        self.mark_dirty()
        self.save(force=True)

    def set_speed_bot_wpm(self, cid, wpm):
        if "speed_bot" not in self.data:
            self.data["speed_bot"] = {}
        key = str(cid)
        if key not in self.data["speed_bot"]:
            self.data["speed_bot"][key] = {"enabled": False, "base_wpm": wpm}
        else:
            self.data["speed_bot"][key]["base_wpm"] = wpm
        self.mark_dirty()
        self.save(force=True)

storage = Storage()

class RemoteManager:
    def __init__(self, url, min_words=5, max_words=25, disasm=False, lang="arabic"):
        self.url = url
        self.min_words = min_words
        self.max_words = max_words
        self.disasm = disasm
        self.lang = lang
        self.sentences = []
        self.last_update = 0

        if lang == "english":
            self.clean_func = clean_english
        elif lang == "persian":
            self.clean_func = clean_persian
        else:
            self.clean_func = clean

    def load(self):
        try:
            r = requests.get(self.url, timeout=10)
            if r.status_code == 200:
                if self.url.endswith('.json'):
                    data = r.json()
                    self.sentences = [
                        self.clean_func(s) for s in data
                        if s.strip() and self.min_words <= len(clean_text_for_word_count(self.clean_func(s)).split()) <= self.max_words
                    ]
                else:
                    self.sentences = [
                        self.clean_func(s) for s in r.text.split('\n')
                        if s.strip() and self.min_words <= len(clean_text_for_word_count(self.clean_func(s)).split()) <= self.max_words
                    ]
                self.last_update = time.time()
        except Exception as e:
            print(f"Error loading from {self.url}: {e}")

    def get(self):
        if not self.sentences or time.time() - self.last_update > 3600:
            self.load()
        return random.choice(self.sentences) if self.sentences else "لا توجد جمل حالياً"

    def get_multiple(self, count=2):
        if not self.sentences or time.time() - self.last_update > 3600:
            self.load()
        if self.sentences:
            return random.sample(self.sentences, min(count, len(self.sentences)))
        return []

class CSVQuotesManager:
    def __init__(self, url, min_words=3, max_words=30):
        self.url = url
        self.min_words = min_words
        self.max_words = max_words
        self.quotes = []
        self.last_update = 0

    def load(self):
        try:
            r = requests.get(self.url, timeout=10)
            if r.status_code == 200:
                lines = r.text.strip().split('\n')[1:]
                self.quotes = []
                for line in lines:
                    if '","' in line or ',' in line:
                        parts = line.split('","')
                        if len(parts) >= 1:
                            quote = parts[0].strip('"').strip()
                            quote = clean(quote)
                            cleaned_quote = clean_text_for_word_count(quote)
                            if quote and self.min_words <= len(cleaned_quote.split()) <= self.max_words:
                                self.quotes.append(quote)
                self.last_update = time.time()
        except Exception as e:
            print(f"Error loading quotes: {e}")

    def get(self):
        if not self.quotes or time.time() - self.last_update > 3600:
            self.load()
        return random.choice(self.quotes) if self.quotes else "لا توجد اقتباسات حالياً"

    def get_multiple(self, count=2):
        if not self.quotes or time.time() - self.last_update > 3600:
            self.load()
        if self.quotes:
            return random.sample(self.quotes, min(count, len(self.quotes)))
        return []

class StoriesManager:
    def __init__(self, gdrive_url, min_words=5, max_words=50):
        self.gdrive_url = gdrive_url
        self.min_words = min_words
        self.max_words = max_words
        self.stories = []
        self.used_indices = set()
        self.last_update = 0
        self.update_interval = 5 * 24 * 60 * 60
        self.target_count = 5000
        self.total_chunks = 0

    def _convert_gdrive_url_to_direct(self, url):
        try:
            file_id = url.split('/d/')[1].split('/')[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
        except:
            return url

    def _download_and_parse_chunks(self):
        try:
            print("[STORIES] Downloading stories from Google Drive...")
            direct_url = self._convert_gdrive_url_to_direct(self.gdrive_url)

            response = requests.get(direct_url, timeout=30)
            if response.status_code != 200:
                print(f"[STORIES] Failed to download: HTTP {response.status_code}")
                return []

            text = response.text
            chunks = re.split(r'\n\s*\n', text)

            valid_chunks = []
            for chunk in chunks:
                chunk = chunk.strip()
                if chunk:
                    cleaned_chunk = clean(chunk)
                    word_count = len(clean_text_for_word_count(cleaned_chunk).split())
                    if self.min_words <= word_count <= self.max_words:
                        valid_chunks.append(cleaned_chunk)

            print(f"[STORIES] Found {len(valid_chunks)} valid chunks from file")
            return valid_chunks

        except Exception as e:
            print(f"[STORIES] Error downloading/parsing chunks: {e}")
            return []

    def _select_random_chunks(self, all_chunks, count):
        available_indices = set(range(len(all_chunks))) - self.used_indices

        if len(available_indices) < count:
            print(f"[STORIES] Resetting used indices (only {len(available_indices)} remaining)")
            self.used_indices = set()
            available_indices = set(range(len(all_chunks)))

        selected_indices = random.sample(list(available_indices), min(count, len(available_indices)))
        self.used_indices.update(selected_indices)

        selected_chunks = [all_chunks[i] for i in selected_indices]
        return selected_chunks

    def load(self):
        current_time = time.time()

        if self.stories and (current_time - self.last_update) < self.update_interval:
            return

        print("[STORIES] Starting stories update...")

        all_chunks = self._download_and_parse_chunks()

        if not all_chunks:
            print("[STORIES] No chunks downloaded, keeping existing stories")
            return

        self.total_chunks = len(all_chunks)
        self.stories = self._select_random_chunks(all_chunks, self.target_count)
        self.last_update = current_time

        print(f"[STORIES] Update complete: {len(self.stories)} stories loaded")

    def get(self):
        if not self.stories or time.time() - self.last_update > self.update_interval:
            self.load()
        return random.choice(self.stories) if self.stories else "لا توجد قصص حالياً"

    def get_multiple(self, count=2):
        if not self.stories or time.time() - self.last_update > self.update_interval:
            self.load()
        if self.stories:
            return random.sample(self.stories, min(count, len(self.stories)))
        return []

class NassContentManager:
    def __init__(self, gdrive_urls, min_words=5, max_words=50):
        self.gdrive_urls = gdrive_urls
        self.min_words = min_words
        self.max_words = max_words
        self.sentences = []
        self.data_file = "nass_data.json"
        self.last_update = 0
        self.update_interval = 3 * 24 * 60 * 60
        self.lines_per_url = 500
        self._load_cached_data()

    def _convert_gdrive_url_to_direct(self, url):
        try:
            file_id = url.split('/d/')[1].split('/')[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
        except:
            return url

    def _load_cached_data(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.sentences = data.get('sentences', [])
                    self.last_update = data.get('last_update', 0)
                    print(f"[NASS] Loaded {len(self.sentences)} sentences from cache")
        except Exception as e:
            print(f"[NASS] Error loading cached data: {e}")
            self.sentences = []

    def _save_cached_data(self):
        try:
            data = {
                'sentences': self.sentences,
                'last_update': self.last_update
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[NASS] Saved {len(self.sentences)} sentences to cache")
        except Exception as e:
            print(f"[NASS] Error saving cached data: {e}")

    def _download_from_url(self, url, url_index, total_urls):
        try:
            print(f"[NASS] [{url_index+1}/{total_urls}] Downloading from {url[:50]}...")
            direct_url = self._convert_gdrive_url_to_direct(url)
            response = requests.get(direct_url, timeout=20)

            if response.status_code != 200:
                print(f"[NASS] [{url_index+1}/{total_urls}] Failed: HTTP {response.status_code}")
                return []

            lines = response.text.split('\n')
            valid_lines = []

            for line in lines:
                line = line.strip()
                if line:
                    cleaned_line = clean_nass_text(line)
                    if not cleaned_line:
                        continue
                    word_count = len(clean_text_for_word_count(cleaned_line).split())
                    if self.min_words <= word_count <= self.max_words:
                        valid_lines.append(cleaned_line)
                        if len(valid_lines) >= self.lines_per_url:
                            break

            if len(valid_lines) > self.lines_per_url:
                selected_lines = random.sample(valid_lines, self.lines_per_url)
            else:
                selected_lines = valid_lines

            print(f"[NASS] [{url_index+1}/{total_urls}] Got {len(selected_lines)} lines")
            return selected_lines

        except Exception as e:
            print(f"[NASS] [{url_index+1}/{total_urls}] Error: {e}")
            return []

    def load(self):
        current_time = time.time()

        if self.sentences and (current_time - self.last_update) < self.update_interval:
            print(f"[NASS] Using cached data ({len(self.sentences)} sentences)")
            return

        print(f"[NASS] Starting نص content update from {len(self.gdrive_urls)} sources...")
        print(f"[NASS] This may take a few minutes, please wait...")

        all_sentences = []
        successful_downloads = 0
        total_urls = len(self.gdrive_urls)

        for index, url in enumerate(self.gdrive_urls):
            sentences_from_url = self._download_from_url(url, index, total_urls)
            if sentences_from_url:
                all_sentences.extend(sentences_from_url)
                successful_downloads += 1
                if successful_downloads % 10 == 0:
                    print(f"[NASS] Progress: {successful_downloads}/{total_urls} sources completed, {len(all_sentences)} total sentences")
            time.sleep(0.2)

        if all_sentences:
            self.sentences = all_sentences
            self.last_update = current_time
            self._save_cached_data()
            print(f"[NASS]  Update complete: {len(self.sentences)} total sentences from {successful_downloads}/{total_urls} sources")
        else:
            print("[NASS]  No sentences downloaded, keeping existing cache")

    def get(self):
        return random.choice(self.sentences) if self.sentences else "لا توجد جمل حالياً"

    def get_multiple(self, count=2):
        if self.sentences:
            return random.sample(self.sentences, min(count, len(self.sentences)))
        return []

    def needs_update(self):
        if not self.sentences:
            return True
        return (time.time() - self.last_update) > self.update_interval

# ==========================================================
#            قسم (طب) - إرسال الجمل بالترتيب لكل مستخدم
# ==========================================================
class TibbContentManager:
    """مدير محتوى قسم طب - يرسل الجمل بالترتيب لكل مستخدم بشكل مستقل
    كل مستخدم له تقدمه الخاص ولا يتأثر بالمستخدمين الآخرين
    """
    def __init__(self, gdrive_url, min_words=5, max_words=50):
        self.gdrive_url = gdrive_url
        self.min_words = min_words
        self.max_words = max_words
        self.sentences = []
        self.data_file = "tibb_data.json"
        self.progress_file = "tibb_progress.json"
        self.last_update = 0
        self.update_interval = 3 * 24 * 60 * 60  # 3 أيام
        self.user_progress = {}  # {uid_str: index}
        self._load_cached_data()
        self._load_progress()

    def _convert_gdrive_url_to_direct(self, url):
        try:
            file_id = url.split('/d/')[1].split('/')[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
        except:
            return url

    def _load_cached_data(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.sentences = data.get('sentences', [])
                    self.last_update = data.get('last_update', 0)
                    print(f"[TIBB] Loaded {len(self.sentences)} sentences from cache")
        except Exception as e:
            print(f"[TIBB] Error loading cached data: {e}")
            self.sentences = []

    def _save_cached_data(self):
        try:
            data = {
                'sentences': self.sentences,
                'last_update': self.last_update
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[TIBB] Saved {len(self.sentences)} sentences to cache")
        except Exception as e:
            print(f"[TIBB] Error saving cached data: {e}")

    def _load_progress(self):
        """تحميل تقدم المستخدمين من الملف"""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.user_progress = data.get('user_progress', {})
                    print(f"[TIBB] Loaded progress for {len(self.user_progress)} users")
        except Exception as e:
            print(f"[TIBB] Error loading progress: {e}")
            self.user_progress = {}

    def _save_progress(self):
        """حفظ تقدم المستخدمين في الملف"""
        try:
            data = {
                'user_progress': self.user_progress
            }
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[TIBB] Error saving progress: {e}")

    def load(self):
        current_time = time.time()

        if self.sentences and (current_time - self.last_update) < self.update_interval:
            print(f"[TIBB] Using cached data ({len(self.sentences)} sentences)")
            return

        print("[TIBB] Starting طب content update...")
        try:
            direct_url = self._convert_gdrive_url_to_direct(self.gdrive_url)
            response = requests.get(direct_url, timeout=30)

            if response.status_code != 200:
                print(f"[TIBB] Failed to download: HTTP {response.status_code}")
                return

            lines = response.text.split('\n')
            valid_lines = []

            for line in lines:
                line = line.strip()
                if line:
                    cleaned_line = clean_nass_text(line)
                    if not cleaned_line:
                        continue
                    word_count = len(clean_text_for_word_count(cleaned_line).split())
                    if self.min_words <= word_count <= self.max_words:
                        valid_lines.append(cleaned_line)

            if valid_lines:
                self.sentences = valid_lines
                self.last_update = current_time
                self._save_cached_data()
                print(f"[TIBB] Update complete: {len(self.sentences)} sentences loaded")
            else:
                print("[TIBB] No valid sentences downloaded, keeping existing cache")

        except Exception as e:
            print(f"[TIBB] Error loading content: {e}")

    def get_next(self, uid):
        """إرجاع الجملة التالية للمستخدم المحدد بالترتيب
        كل مستخدم له تقدمه المستقل
        """
        if not self.sentences:
            return "لا توجد جمل حالياً"

        uid_str = str(uid)
        
        # الحصول على الفهرس الحالي للمستخدم (0 إذا لم يكن موجوداً)
        current_index = self.user_progress.get(uid_str, 0)
        
        # التحقق من أن الفهرس ضمن حدود القائمة
        if current_index >= len(self.sentences):
            # إذا انتهى الملف، أعد من البداية
            current_index = 0
        
        # الحصول على الجملة الحالية
        sentence = self.sentences[current_index]
        
        # تحديث الفهرس للجملة التالية
        next_index = current_index + 1
        if next_index >= len(self.sentences):
            next_index = 0  # إعادة من البداية
        
        self.user_progress[uid_str] = next_index
        self._save_progress()
        
        return sentence

    def get(self):
        """للحفاظ على التوافق - يرجع جملة عشوائية (لا يُستخدم في طب)"""
        return random.choice(self.sentences) if self.sentences else "لا توجد جمل حالياً"

    def get_multiple(self, count=2):
        if self.sentences:
            return random.sample(self.sentences, min(count, len(self.sentences)))
        return []

    def needs_update(self):
        if not self.sentences:
            return True
        return (time.time() - self.last_update) > self.update_interval

class LocalJSONManager:
    """مدير محلي يستيرد كل البيانات من رابط واحد ويحفظها في الرام فقط"""
    def __init__(self, section_name, url, min_words=5, max_words=50, lang="arabic"):
        self.section_name = section_name
        self.url = url
        self.min_words = min_words
        self.max_words = max_words
        self.lang = lang
        self.sentences = []
        self.last_update = 0
        
        # تحميل البيانات عند التشغيل إذا لم تكن موجودة أو قديمة (أكثر من ساعة)
        if not self.sentences or (time.time() - self.last_update) > 3600:
            self.load()

    def _convert_gdrive_url_to_direct(self, url):
        try:
            file_id = url.split('/d/')[1].split('/')[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
        except:
            return url

    def load(self):
        try:
            print(f"[{self.section_name}] جاري تحميل البيانات من الرابط...")
            direct_url = self._convert_gdrive_url_to_direct(self.url)
            response = requests.get(direct_url, timeout=30)

            if response.status_code != 200:
                print(f"[{self.section_name}] فشل التحميل: HTTP {response.status_code}")
                return

            lines = response.text.strip().split('\n')
            valid_lines = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # تنظيف حسب نوع اللغة
                if self.lang == "english":
                    cleaned_line = clean_english(line)
                elif self.lang == "persian":
                    cleaned_line = clean_persian(line)
                else:
                    cleaned_line = clean(line)

                if not cleaned_line:
                    continue

                word_count = len(clean_text_for_word_count(cleaned_line).split())
                if self.min_words <= word_count <= self.max_words:
                    valid_lines.append(cleaned_line)

            self.sentences = valid_lines
            self.last_update = time.time()
            print(f"[{self.section_name}] تم تحميل {len(self.sentences)} جملة بنجاح")

        except Exception as e:
            print(f"[{self.section_name}] خطأ في التحميل: {e}")

    def get(self):
        return random.choice(self.sentences) if self.sentences else "لا توجد جمل حالياً"

    def get_multiple(self, count=2):
        if self.sentences:
            return random.sample(self.sentences, min(count, len(self.sentences)))
        return []

class WajabManager:
    def __init__(self, word_list, min_length=7, max_length=20):
        self.word_list = word_list
        self.min_length = min_length
        self.max_length = max_length

    def get(self):
        sentence_length = random.randint(self.min_length, self.max_length)
        selected_words = random.sample(self.word_list, min(sentence_length, len(self.word_list)))
        return ' '.join(selected_words)

    def get_multiple(self, count=2):
        return [self.get() for _ in range(count)]

def generate_random_sentence(uid, word_list, min_length=7, max_length=20, system_type="رق"):
    for attempt in range(100):
        sentence_length = random.randint(min_length, max_length)

        selected_words = []
        available_indices = list(range(len(word_list)))

        for _ in range(sentence_length):
            if not available_indices:
                available_indices = list(range(len(word_list)))

            if selected_words:
                last_index = word_list.index(selected_words[-1])
                valid_indices = [i for i in available_indices if abs(i - last_index) > 1]

                if not valid_indices:
                    valid_indices = available_indices
            else:
                valid_indices = available_indices

            chosen_index = random.choice(valid_indices)
            selected_words.append(word_list[chosen_index])

            if chosen_index in available_indices:
                available_indices.remove(chosen_index)

        sentence = ' '.join(selected_words)
        key = f"{system_type}_{sentence}"

        if not storage.is_pattern_used(uid, key):
            storage.add_pattern(uid, key)
            return sentence

    storage.clear_patterns(uid)
    return generate_random_sentence(uid, word_list, min_length, max_length, system_type)

def clean(txt):
    txt = txt.replace('\u0640', '')
    txt = re.sub(r'[\u064B-\u065F\u0670]', '', txt.replace(' ≈ ', ' ').replace('≈', ' '))
    txt = re.sub(r'\([^)]*[a-zA-Z]+[^)]*\)', '', txt)
    txt = re.sub(r'\[[^\]]*\]', '', txt)
    txt = re.sub(r'\([^)]*\)', '', txt)
    txt = ' '.join([w for w in txt.split() if not re.search(r'[a-zA-Z]', w)])

    def rep_num(m):
        n = m.group()
        return NUM_WORDS.get(n, ' '.join(NUM_WORDS.get(d, d) for d in n) if len(n) > 1 else n)

    txt = re.sub(r'\d+', rep_num, txt)
    # حذف جميع الرموز والعلامات الترقيمية
    symbol_pattern = r'[~=\-_|/\\*#@%$&!+^<>{}[\]()"\'،,:;؛\.\!؟\?\(\)\[\]\{\}""''«»…≈]+'
    txt = re.sub(symbol_pattern, ' ', txt)
    return re.sub(r'\s+', ' ', txt).strip()

def clean_persian(txt):
    txt = txt.replace('\u0640', '')
    txt = re.sub(r'[\u064B-\u065F\u0670]', '', txt)
    txt = re.sub(r'\([^)]*\)', '', txt)
    txt = re.sub(r'\[[^\]]*\]', '', txt)
    # حذف جميع الرموز والعلامات الترقيمية
    symbol_pattern = r'[~=\-_|/\\*#@%$&!+^<>{}[\]()"\'،,:;؛\.\!؟\?\(\)\[\]\{\}""''«»…≈]+'
    txt = re.sub(symbol_pattern, ' ', txt)
    return re.sub(r'\s+', ' ', txt).strip()

def clean_english(txt):
    txt = txt.strip()
    txt = txt.replace('\u0640', '')
    txt = re.sub(r'\([^)]*\)', '', txt)
    txt = re.sub(r'\[[^\]]*\]', '', txt)
    # حذف جميع الرموز والعلامات الترقيمية
    symbol_pattern = r'[~=\-_|/\\*#@%$&!+^<>{}[\]()"\'،,:;؛\.\!؟\?\(\)\[\]\{\}""''«»…≈]+'
    txt = re.sub(symbol_pattern, ' ', txt)
    return re.sub(r'\s+', ' ', txt).strip()

def clean_nass_text(txt):
    txt = txt.replace('\u0640', '')
    txt = re.sub(r'[\u064B-\u065F\u0670]', '', txt.replace(' ≈ ', ' ').replace('≈', ' '))
    txt = re.sub(r'\([^)]*[a-zA-Z]+[^)]*\)', '', txt)
    txt = re.sub(r'\[[^\]]*\]', '', txt)
    txt = re.sub(r'\([^)]*\)', '', txt)
    txt = ' '.join([w for w in txt.split() if not re.search(r'[a-zA-Z]', w)])
    txt = re.sub(r'[0-9٠-٩]', '', txt)
    txt = re.sub(r'[،,:;؛\-–—\.\!؟\?\(\)\[\]\{\}""''«»…@#$%^&*+=<>~/\\|_]', ' ', txt)
    return re.sub(r'\s+', ' ', txt).strip()

def normalize(txt):
    txt = txt.replace('\u0640', '')
    txt = re.sub(r'[\u064B-\u065F\u0670]', '', txt)
    # حذف جميع الرموز والعلامات الترقيمية
    symbol_pattern = r'[~=\-_|/\\*#@%$&!+^<>{}[\]()"\'،,:;؛\.\!؟\?\(\)\[\]\{\}""''«»…≈]+'
    txt = re.sub(symbol_pattern, ' ', txt)
    return re.sub(r'\s+', ' ', ''.join(CHAR_MAP.get(c, c) for c in txt)).strip()

def normalize_persian(txt):
    txt = txt.strip().lower()
    txt = txt.replace('\u0640', '')
    persian_map = {
        'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي', 'ة': 'ه', 'ئ': 'ي', 'ؤ': 'و', 'ٱ': 'ا', 'ٳ': 'ا',
        'گ': 'ك', 'پ': 'ب', 'ژ': 'ز', 'چ': 'ج'
    }
    txt = ''.join(persian_map.get(c, c) for c in txt)
    txt = re.sub(r'[\u064B-\u065F\u0670]', '', txt)
    return re.sub(r'\s+', ' ', txt).strip()

def normalize_english(txt):
    txt = txt.strip().lower()
    txt = txt.replace('\u0640', '')
    txt = re.sub(r'[^\w\s]', '', txt)
    return re.sub(r'\s+', ' ', txt).strip()

# ==========================================================
#            قسم (اص) - الزخرفة الحرفية
# ==========================================================
# يستورد جمل قسم (مس) ثم:
#   1) يصفّي الجملة من كل الرموز والأرقام فما يبقى إلا حروف عربية
#   2) يستبدل حروف معينة بحروف مزخرفة حسب قواعد المستخدم
#   3) يضيف تطويلات (ـ) حسب قواعد كل حرف
# عند التحقق: المستخدم يكتب الجملة الأصلية (قبل الزخرفة) بشكلها العادي.
# إذا كتب أي حرف مزخرف أو تطويل => لا تُحسب السرعة إطلاقاً.

TATWEEL = '\u0640'  # ـ

# الحروف المزخرفة المستخدمة في قسم اص (لا يجوز للمستخدم كتابتها)
AS_FANCY_CHARS = {
    '\u0672',  # ٲ  بديل أ
    '\u0673',  # ٳ  بديل إ
    '\u0695',  # ڕ  بديل ر
    '\u08A5',  # ࢥ  بديل ق
    '\u067D',  # ٽ  بديل ث
    '\u06BA',  # ں  بديل ن (مع ضمة)
    '\u06B6',  # ڶ  بديل ل
    '\u06C2',  # ۂ  بديل ه/ة
    '\u06C6',  # ۆ  بديل و/ؤ
    '\u0684',  # ڄ  بديل ج
    '\u0765',  # ݥ  بديل م (احتياطي)
    '\u08A0',  # ࢠ  بديل ب (احتياطي)
    '\u06AD',  # ڭ  بديل ك (احتياطي)
}

# خريطة الاستبدال الأساسية: أصلي -> مزخرف
AS_REPLACE_MAP = {
    'أ': '\u0672',   # ٲ
    'إ': '\u0673',   # ٳ
    'ر': '\u0695',   # ڕ
    'ق': '\u08A5',   # ࢥ
    'ث': '\u067D',   # ٽ
    'ن': '\u06BA\u064F',  # ںُ  (نون غنة + ضمة)
    'ل': '\u06B6',   # ڶ
    'ه': '\u06C2',   # ۂ
    'ة': '\u06C2',   # ۂ
    'و': '\u06C6',   # ۆ
    'ؤ': '\u06C6',   # ۆ
    'ج': '\u0684',   # ڄ
}

# الحروف التي تأخذ تطويلتين بعدها (إذا لم تكن آخر الكلمة) - قاعدة "القاف"
AS_TATWEEL_AFTER = {'\u08A5', '\u06B6', '\u0684', '\u0765', '\u08A0', '\u06AD'}

# الحروف التي تأخذ تطويلتين قبلها - قاعدة "الواو" (ۆ و ڕ)
AS_TATWEEL_BEFORE = {'\u06C6', '\u0695'}

# حروف لا تقبل الالتصاق بما بعدها (لا يمكن وصلها من اليسار)
AS_NON_CONNECTING = set(
    'ادذرزوؤإأآاٱةءئ'
    '\u0672'  # ٲ
    '\u0673'  # ٳ
    '\u0695'  # ڕ
    '\u06C6'  # ۆ
    '\u06C2'  # ۂ
)

# الحروف التي لا يُمدّ بعدها ما يليها (ٽ ، ںُ ، ٳ ، ٲ) وأصولها العادية (ث ، ن ، إ ، أ)
AS_NO_TATWEEL_AFTER_THESE = {
    '\u067D',  # ٽ
    '\u06BA',  # ں
    '\u0673',  # ٳ
    '\u0672',  # ٲ
    'ث', 'ن', 'إ', 'أ',
}

# الحروف التي تُستبدل فقط في نهاية الكلمة وغير مربوطة بما قبلها: ه/ة و ن و ث
AS_END_ONLY_LETTERS = {'ه', 'ة', 'ن', 'ث'}


def as_strip_to_arabic(txt):
    """تصفية الجملة: حذف كل الرموز والأرقام والحروف اللاتينية، ولا يبقى إلا حروف عربية ومسافات"""
    if not txt:
        return ""
    txt = txt.replace(TATWEEL, '')
    # حذف التشكيل
    txt = re.sub(r'[\u064B-\u065F\u0670]', '', txt)
    # حذف كل ما ليس حرفاً عربياً أو مسافة
    txt = re.sub(r'[^\u0621-\u064A\s]', ' ', txt)
    return re.sub(r'\s+', ' ', txt).strip()


def _as_decorate_word(word):
    """زخرفة كلمة واحدة حسب قواعد قسم اص"""
    if not word:
        return word

    chars = list(word)
    n = len(chars)
    out = []

    def push_tatweel():
        """إضافة تطويلتين مع منع التكرار (لا تتجاوز تطويلتين متتاليتين)"""
        if out and out[-1].endswith(TATWEEL):
            return
        out.append(TATWEEL * 2)

    def prev_emitted_letter():
        """آخر حرف فعلي تمت كتابته في المخرجات (تجاهل التطويل والتشكيل)"""
        for piece in reversed(out):
            for cch in reversed(piece):
                if cch == TATWEEL or '\u064B' <= cch <= '\u0652':
                    continue
                return cch
        return None

    def can_attach_before():
        """هل يمكن مدّ الحرف الحالي؟ يعتمد على الحرف السابق المكتوب فعلاً"""
        pe = prev_emitted_letter()
        if pe is None:
            return False
        if pe in AS_NON_CONNECTING:
            return False           # حرف لا يقبل الالتصاق مثل ر / ة / ز / و
        if pe in AS_NO_TATWEEL_AFTER_THESE:
            return False           # لا تمد بعد ٽ ، ںُ ، ٳ ، ٲ
        return True

    for i, ch in enumerate(chars):
        is_last = (i == n - 1)
        is_first = (i == 0)
        prev_orig = chars[i - 1] if i > 0 else None

        # --- حروف ه/ة و ن و ث: تُستبدل فقط في آخر الكلمة وغير مربوطة بما قبلها ---
        if ch in AS_END_ONLY_LETTERS:
            if is_last and prev_orig is not None and prev_orig in AS_NON_CONNECTING:
                out.append(AS_REPLACE_MAP[ch])
            else:
                out.append(ch)
            continue

        # --- الألف (ا/أ/إ/آ): أول الكلمة أو آخرها فقط، ولا تأتي في الوسط ---
        if ch in ('ا', 'أ', 'إ', 'آ'):
            if is_first:
                # أول الكلمة: أ -> ٲ ، إ -> ٳ ، والألف العادية تبقى ألف
                out.append(AS_REPLACE_MAP.get(ch, ch))
            elif is_last and n > 1:
                # ألف أخيرة (مثل رجالها -> رجالهٲ) مع تمديدين قبلها
                if can_attach_before():
                    push_tatweel()
                out.append(AS_REPLACE_MAP.get(ch, '\u0672'))
            else:
                # وسط الكلمة: تبقى كما هي
                out.append(ch)
            continue

        # --- حرفا و/ؤ و ر: تطويلتان قبلهما بشروط ---
        if ch in ('و', 'ؤ', 'ر'):
            fancy = AS_REPLACE_MAP[ch]
            # لا تمد إذا كانت أول الكلمة، ولا إذا كان ما قبلها لا يقبل الالتصاق،
            # ولا إذا كان قبلها ٽ / ںُ / ٳ / ٲ
            if not is_first and can_attach_before():
                push_tatweel()
            out.append(fancy)
            continue

        # --- بقية الحروف المستبدلة (ق، ل، ج) ---
        if ch in AS_REPLACE_MAP:
            fancy = AS_REPLACE_MAP[ch]
            out.append(fancy)
            # تطويلتان بعد الحرف إذا لم يكن آخر الكلمة
            if fancy in AS_TATWEEL_AFTER and not is_last:
                push_tatweel()
            continue

        # حرف عادي يبقى كما هو
        out.append(ch)

    return ''.join(out)


def as_decorate_sentence(txt):
    """تصفية الجملة ثم زخرفتها بالكامل (قسم اص)"""
    cleaned = as_strip_to_arabic(txt)
    if not cleaned:
        return ""
    return ' '.join(_as_decorate_word(w) for w in cleaned.split())


def as_user_used_fancy(txt):
    """True إذا كتب المستخدم أي حرف مزخرف أو تطويل - عندها لا تُحسب سرعته"""
    if not txt:
        return False
    if TATWEEL in txt:
        return True
    return any(ch in AS_FANCY_CHARS for ch in txt)


def format_display(s):
    s = s.replace('\u0640', '')
    return ' ، '.join(s.split())

def count_words_for_wpm(text):
    # حذف جميع الرموز والعلامات الترقيمية (بدون حذف المسافات)
    cleaned_text = re.sub(r'[~=\-_|/\\*#@%$&!+^<>{}[\]()"\'،,:;؛\.\!؟\?\(\)\[\]\{\}""''«»…≈]+', ' ', text)
    # توحيد المسافات
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    if not cleaned_text:
        return 0
    words = cleaned_text.split()
    return len(words)

def check_answer_validity(orig, usr):
    """فحص الإجابة - ترفض الفواصل فقط"""
    # رفض إذا كانت تحتوي على فواصل (إنجليزية أو عربية)
    if ',' in usr or '،' in usr:
        return False
    return True

def match_numbers(orig, usr):
    """تطابق أرقام مع تجاهل جميع الرموز بين الكلمات وتحويل الأرقام العادية لكلمات عربية"""
    # تنظيف الرموز - استخدام نفس النمط الشامل
    symbol_pattern = r'[~=\-_|/\\*#@%$&!+^<>{}[\]()"\'،,:;؛\.\!؟\?\(\)\[\]\{\}""''«»…≈]+'
    orig_cleaned = re.sub(symbol_pattern, ' ', orig)
    usr_cleaned = re.sub(symbol_pattern, ' ', usr)

    # إذا كان original يحتوي على أرقام عادية، حول الاثنين إلى كلمات عربية
    if re.search(r'\d', orig_cleaned):
        try:
            # تحويل المسافات بين الأرقام إلى فواصل للتعامل مع دالة convert_numbers_to_arabic_words
            orig_for_conversion = orig_cleaned.strip()
            orig_for_conversion = re.sub(r'\s+', ',', orig_for_conversion)

            # تحويل الأرقام العادية من orig إلى كلمات عربية
            expected_words = normalize(normalize_number_text(convert_numbers_to_arabic_words(orig_for_conversion)))
            usr_normalized = normalize(normalize_number_text(usr_cleaned))
            if expected_words == usr_normalized:
                return True

            expected_word_set = set(expected_words.split())
            usr_word_set = set(usr_normalized.split())
            if expected_word_set and expected_word_set == usr_word_set:
                return True
        except:
            pass

    # إذا لم تحتوي على أرقام أو فشل التحويل، قارن النصين المنظفة مباشرة
    orig_normalized = normalize(orig_cleaned)
    usr_normalized = normalize(usr_cleaned)

    if orig_normalized == usr_normalized:
        return True

    orig_word_set = set(orig_normalized.split())
    usr_word_set = set(usr_normalized.split())
    if orig_word_set and orig_word_set == usr_word_set:
        return True

    return False

def match_text(orig, usr, lang="arabic"):
    if lang == "persian":
        orig_normalized = normalize_persian(orig)
        usr_normalized = normalize_persian(usr)
    elif lang == "english":
        orig_normalized = normalize_english(orig)
        usr_normalized = normalize_english(usr)
    else:
        orig_normalized = normalize(orig)
        usr_normalized = normalize(usr)

    if orig_normalized == usr_normalized:
        return True

    # استخدام نفس النمط الشامل لجميع الرموز
    symbol_pattern = r'[~=\-_|/\\*#@%$&!+^<>{}[\]()"\'،,:;؛\.\!؟\?\(\)\[\]\{\}""''«»…≈]+'
    usr_with_spaces = re.sub(symbol_pattern, ' ', usr)
    if lang == "persian":
        usr_with_spaces_normalized = normalize_persian(usr_with_spaces)
    elif lang == "english":
        usr_with_spaces_normalized = normalize_english(usr_with_spaces)
    else:
        usr_with_spaces_normalized = normalize(usr_with_spaces)

    if orig_normalized == usr_with_spaces_normalized:
        return True

    words = usr_with_spaces_normalized.split()
    if len(words) >= 2:
        reversed_text = ' '.join(reversed(words))
        if orig_normalized == reversed_text:
            return True

    orig_words = set(orig_normalized.split())
    usr_words = set(usr_with_spaces_normalized.split())
    if orig_words and orig_words == usr_words:
        return True

    return False


def compute_accuracy(orig, usr, lang="arabic"):
    """
    حساب دقة واقعية بناءً على عدد الأحرف الخاطئة.
    يعيد أرقام بصيغة XX.XX (مثل 96.12، 91.55) عشوائية في كل مرة.
    """
    try:
        if lang == "persian":
            o = normalize_persian(orig)
            u = normalize_persian(usr)
        elif lang == "english":
            o = normalize_english(orig)
            u = normalize_english(usr)
        else:
            o = normalize(orig)
            u = normalize(usr)

        if not o and not u:
            return 100.0
        if o == u:
            return 100.0

        # استخدام SequenceMatcher للمقارنة التفصيلية
        matcher = difflib.SequenceMatcher(None, o, u)
        
        # حساب عدد الأحرف المتطابقة والمختلفة
        matching_blocks = matcher.get_matching_blocks()
        matched_chars = sum(block.size for block in matching_blocks)
        
        # الطول الأساسي للمقارنة (أطول النصين)
        base_length = max(len(o), len(u))
        
        if base_length == 0:
            return 100.0
        
        # حساب النسبة المئوية الأساسية
        accuracy = (matched_chars / base_length) * 100.0
        
        # إضافة تباين عشوائي صغير (+/- 2%) لجعل النتائج متنوعة وواقعية
        variance = random.uniform(-2, 2)
        accuracy = accuracy + variance
        
        # التأكد من أن القيمة بين 0 و 100
        accuracy = max(0.0, min(100.0, accuracy))
        
        # تقريب إلى رقمين عشريين فقط (مثل 96.12، 91.55)
        accuracy = round(accuracy, 2)
        
        return accuracy
    except Exception:
        return 0.0


def compute_word_based_accuracy(orig, usr, lang="arabic"):
    """
    دقة مبنية على الكلمات (ترتيب حر وتكرار مسموح):
    - 100% إذا كتب المستخدم نفس الكلمات الأصلية بترتيب مختلف ومع تكرار صحيح.
    - ينقص فقط عند فقدان كلمة أصلية أو إضافة/تكرار كلمة خاطئة غير موجودة في الأصل.
    """
    try:
        if lang == "persian":
            o = normalize_persian(orig)
            u = normalize_persian(usr)
        elif lang == "english":
            o = normalize_english(orig)
            u = normalize_english(usr)
        else:
            o = normalize(orig)
            u = normalize(usr)

        if not o and not u:
            return 100.0
        if o == u:
            return 100.0

        orig_words = o.split()
        usr_words = u.split()

        if not orig_words or not usr_words:
            return 0.0

        orig_counter = Counter(orig_words)
        usr_counter = Counter(usr_words)

        total_required = sum(orig_counter.values())
        matched = sum(min(orig_counter[w], usr_counter.get(w, 0)) for w in orig_counter)
        missing = total_required - matched
        extra_wrong = sum(count for w, count in usr_counter.items() if w not in orig_counter)

        errors = missing + extra_wrong
        accuracy = ((total_required - errors) / total_required) * 100.0 if total_required else 100.0
        return round(max(0.0, min(100.0, accuracy)), 2)
    except Exception:
        return 0.0


def is_all_words_present(orig, usr, lang="arabic"):
    """
    التحقق من أن جميع كلمات الجملة الأصلية موجودة في إجابة المستخدم (بدون اعتبار الترتيب أو التكرار).
    يعيد: True إذا كانت جميع الكلمات موجودة، False خلاف ذلك
    """
    try:
        if lang == "persian":
            o = normalize_persian(orig)
            u = normalize_persian(usr)
        elif lang == "english":
            o = normalize_english(orig)
            u = normalize_english(usr)
        else:
            o = normalize(orig)
            u = normalize(usr)

        if not o or not u:
            return o == u

        orig_words = set(o.split())
        usr_words = set(u.split())

        return orig_words.issubset(usr_words)
    except Exception:
        return False


def is_accuracy_enabled_for(uid):
    """Return True if the user enabled accuracy, False otherwise."""
    try:
        val = storage.get_preference(uid, "accuracy_enabled")
        # الافتراضية: نظام الدقة معطّل — يجب على المستخدم كتابة 'تفعيل الدقة'
        if val is None:
            return False
        return bool(val)
    except Exception:
        return False


def compute_accuracy_lenient(orig, usr, lang="arabic"):
    """
    حساب دقة متساهلة مع السماح بتبديل الكلمات وتكرارها:
    - إذا كتب المستخدم نفس الكلمات (أي ترتيب/تكرار صحيح) الدقة تبقى 100%.
    - ينقص من الدقة فقط عند فقدان كلمة أصلية أو إضافة كلمة غير موجودة في الأصل أو كتابتها بشكل خاطئ.
    """
    try:
        if lang == "persian":
            o = normalize_persian(orig)
            u = normalize_persian(usr)
        elif lang == "english":
            o = normalize_english(orig)
            u = normalize_english(usr)
        else:
            o = normalize(orig)
            u = normalize(usr)

        if not o and not u:
            return 100.0
        if o == u:
            return 100.0

        # دقة صديقة للترتيب/التكرار: تعتمد على الكلمات لا الحروف
        orig_words = o.split()
        usr_words = u.split()

        if orig_words and usr_words:
            orig_counter = Counter(orig_words)
            usr_counter = Counter(usr_words)

            total_required = sum(orig_counter.values())
            matched = sum(min(orig_counter[w], usr_counter.get(w, 0)) for w in orig_counter)
            missing = total_required - matched
            extra_wrong = sum(count for w, count in usr_counter.items() if w not in orig_counter)

            errors = missing + extra_wrong
            accuracy = ((total_required - errors) / total_required) * 100.0 if total_required else 100.0
            return round(max(0.0, min(100.0, accuracy)), 2)

        # fallback حرفي عند غياب الكلمات
        matcher = difflib.SequenceMatcher(None, o, u)
        matching_blocks = matcher.get_matching_blocks()
        matched_chars = sum(block.size for block in matching_blocks)
        base_length = max(len(o), len(u))
        if base_length == 0:
            return 100.0

        accuracy = (matched_chars / base_length) * 100.0
        accuracy = max(0.0, min(100.0, accuracy))
        return round(accuracy, 2)
    except Exception:
        return 0.0

def generate_realistic_accuracy(base_accuracy):
    """
    تحسين الدقة بإضافة تباين عشوائي صغير جداً للحصول على نتائج واقعية
    مثال: 95% -> 94.23% أو 96.15%
    """
    if base_accuracy == 100.0:
        return 100.0
    
    if base_accuracy <= 0:
        return 0.0
    
    # إضافة تباين دقيق جداً (+/- 0.5%)
    variance = random.uniform(-0.5, 0.5)
    realistic_acc = base_accuracy + variance
    
    # التأكد من أن القيمة بين 0 و 100
    realistic_acc = max(0.0, min(100.0, realistic_acc))
    
    # تقريب إلى 2-3 أرقام عشرية عشوائية
    decimal_places = random.randint(2, 3)
    realistic_acc = round(realistic_acc, decimal_places)
    
    return realistic_acc


def match_with_accuracy(orig, usr, lang="arabic", threshold=80.0):
    """
    حساب الدقة والمطابقة بناءً على دقة حرفية.
    يعيد: (matched: bool, accuracy: float)
    """
    # حساب الدقة الحرفية
    accuracy = compute_accuracy(orig, usr, lang)
    
    # قرار القبول على أساس العتبة فقط
    is_matched = (accuracy >= threshold)
    
    return (is_matched, accuracy)



def norm_spaces(txt):
    return re.sub(r'\s+', ' ', txt).strip()

def disassemble_word(word):
    return ' '.join(list(word))

def assemble_word(disassembled_word):
    return disassembled_word.replace(' ', '')

def disassemble_sentence(sentence):
    words = sentence.split()
    return ' '.join([disassemble_word(word) for word in words])

def assemble_sentence(disassembled_sentence):
    words = disassembled_sentence.split()
    assembled_words = []
    current_word = []

    for char in words:
        if char.strip():
            current_word.append(char)
        if len(current_word) > 0 and (not char.strip() or char == words[-1]):
            assembled_words.append(assemble_word(' '.join(current_word)))
            current_word = []

    return ' '.join(assembled_words)

def is_correct_disassembly(original, user_disassembly):
    expected = disassemble_sentence(original)
    return normalize(user_disassembly) == normalize(expected)

def is_correct_assembly(original_disassembled, user_assembly):
    expected = assemble_sentence(original_disassembled)
    return normalize(user_assembly) == normalize(expected)

def apply_condition(cond, sent):
    words = sent.split()
    if not words:
        return sent

    if cond == "كرر أول كلمة":
        return f"{words[0]} {sent}"

    elif cond == "كرر ثاني كلمة" and len(words) >= 2:
        return f"{words[1]} {sent}"

    elif cond == "كرر آخر كلمة":
        return f"{sent} {words[-1]}"

    elif cond == "كرر أول كلمة وآخر كلمة":
        return f"{words[0]} {sent} {words[-1]}"

    elif cond == "فكك أول كلمة":
        return f"{' '.join(words[0])} {' '.join(words[1:])}" if len(words) > 1 else ' '.join(words[0])

    elif cond == "فكك آخر كلمة":
        return f"{' '.join(words[:-1])} {' '.join(words[-1])}" if len(words) > 1 else ' '.join(words[-1])

    elif cond == "بدل أول كلمتين" and len(words) >= 2:
        words[0], words[1] = words[1], words[0]
        return ' '.join(words)

    elif cond == "بدل آخر كلمتين" and len(words) >= 2:
        words[-1], words[-2] = words[-2], words[-1]
        return ' '.join(words)

    elif cond == "بدل ثاني كلمة والكلمة الأخيرة" and len(words) >= 3:
        words[1], words[-1] = words[-1], words[1]
        return ' '.join(words)

    return sent

def validate_condition(cond, orig, usr):
    expected = apply_condition(cond, orig)
    return normalize(usr) == normalize(expected), expected

def validate_repeat(exp, usr):
    """التحقق من صحة كرر - تقبل الكلمات بأي ترتيب طالما العدد صحيح"""
    matches = re.findall(r'(\S+)\((\d+)\)', exp)
    usr_cleaned = clean_text_for_word_count(usr)
    user_words = usr_cleaned.split()
    total = sum(int(c) for _, c in matches)

    if len(user_words) != total:
        return False, f"عدد الكلمات غير صحيح. المفترض: {total}"

    # بناء قاموس الكلمات المتوقعة مع العدد
    expected_word_count = {}
    for word, count in matches:
        normalized_word = normalize(word)
        expected_word_count[normalized_word] = int(count)

    # بناء قاموس الكلمات المكتوبة مع عددها
    user_word_count = {}
    for word in user_words:
        normalized_word = normalize(word)
        user_word_count[normalized_word] = user_word_count.get(normalized_word, 0) + 1

    # التحقق من التطابق
    if expected_word_count == user_word_count:
        return True, ""

    return False, "الكلمات غير صحيحة"

def validate_double(original_sentence, user_text):
    original_words = original_sentence.split()
    user_text_cleaned = clean_text_for_word_count(user_text)
    user_words = user_text_cleaned.split()

    if len(user_words) != len(original_words) * 2:
        return False, f"عدد الكلمات غير صحيح. المفترض: {len(original_words) * 2}"

    idx = 0
    for word in original_words:
        if normalize(user_words[idx]) != normalize(word):
            return False, f"الكلمة '{user_words[idx]}' يجب أن تكون '{word}'"
        if normalize(user_words[idx + 1]) != normalize(word):
            return False, f"الكلمة '{user_words[idx + 1]}' يجب أن تكون '{word}'"
        idx += 2

    return True, ""

def validate_triple(original_sentence, user_text):
    original_words = original_sentence.split()
    user_text_cleaned = clean_text_for_word_count(user_text)
    user_words = user_text_cleaned.split()

    if len(user_words) != len(original_words) * 3:
        return False, f"عدد الكلمات غير صحيح. المفترض: {len(original_words) * 3}"

    idx = 0
    for word in original_words:
        for i in range(3):
            if normalize(user_words[idx + i]) != normalize(word):
                return False, f"الكلمة '{user_words[idx + i]}' يجب أن تكون '{word}'"
        idx += 3

    return True, ""

def validate_reverse(original_sentence, user_text):
    original_words = original_sentence.split()
    user_text_cleaned = clean_text_for_word_count(user_text)
    user_words = user_text_cleaned.split()

    if len(user_words) != len(original_words):
        return False, f"عدد الكلمات غير صحيح. المفترض: {len(original_words)}"

    reversed_original = list(reversed(original_words))
    for i, word in enumerate(reversed_original):
        if normalize(user_words[i]) != normalize(word):
            return False, f"الكلمة '{user_words[i]}' يجب أن تكون '{word}'"

    return True, ""

def gen_pattern(uid, count=1, exclude_words=None):
    """توليد عدد معين من الكلمات المكررة - كل كلمة لها رقم تكرار خاص بها"""
    if exclude_words is None:
        exclude_words = []

    pattern = []
    used_words_in_pattern = []
    available_words = [w for w in REPEAT_WORDS if w not in exclude_words]

    if not available_words:
        available_words = REPEAT_WORDS

    for _ in range(count):
        w_clean = None
        word_with_count = None
        for attempt in range(100):
            word = random.choice(available_words)
            w_clean = word.replace('\u0640', '')
            c = random.randint(2, 4)
            word_with_count = f"{w_clean}({c})"

            # التحقق من عدم تكرار نفس الكلمة في نفس الرسالة (حتى مع أرقام مختلفة)
            if w_clean not in used_words_in_pattern and word_with_count not in pattern:
                pattern.append(word_with_count)
                used_words_in_pattern.append(w_clean)
                break
        else:
            # إذا فشل البحث عن كلمة جديدة، أضفها على أي حال
            if w_clean is not None and w_clean not in used_words_in_pattern and word_with_count is not None:
                pattern.append(word_with_count)
                used_words_in_pattern.append(w_clean)

    return pattern

def gen_pattern_from_custom_words(words_list, count=None):
    """توليد عدد معين من الكلمات المكررة من قائمة كلمات المستخدم - مثل كرر"""
    if not words_list:
        return []

    # إذا لم يحدد عدد، اختر عشوائياً 3-5 كلمات
    if count is None:
        count = random.randint(3, 5)

    # لا تتجاوز عدد الكلمات المتاحة
    count = min(count, len(words_list))

    pattern = []
    used_words = []

    for _ in range(count):
        w_clean = None
        word_with_count = None
        for attempt in range(100):
            word = random.choice(words_list)
            w_clean = word.replace('\u0640', '')
            c = random.randint(2, 4)
            word_with_count = f"{w_clean}({c})"

            # تحقق من عدم تكرار نفس الكلمة في نفس الرسالة
            if w_clean not in used_words and word_with_count not in pattern:
                pattern.append(word_with_count)
                used_words.append(w_clean)
                break
        else:
            # إذا فشل البحث، أضفها على أي حال
            if w_clean is not None and w_clean not in used_words and word_with_count is not None:
                pattern.append(word_with_count)
                used_words.append(w_clean)

    return pattern

def gen_pattern_with_word_count(uid, total_words):
    if total_words < 4 or total_words > 50:
        return None

    for attempt in range(100):
        num_words = random.randint(2, min(6, total_words))
        words = random.sample(REPEAT_WORDS, num_words)

        remaining = total_words
        counts = []
        for i in range(num_words):
            if i == num_words - 1:
                counts.append(remaining)
            else:
                min_count = 1
                max_count = min(remaining - (num_words - i - 1), 10)
                if max_count < min_count:
                    break
                count = random.randint(min_count, max_count)
                counts.append(count)
                remaining -= count

        if sum(counts) != total_words:
            continue

        pattern = []
        key_parts = []
        for w, c in zip(words, counts):
            w_clean = w.replace('\u0640', '')
            pattern.append(f"{w_clean}({c})")
            key_parts.append(f"{w_clean}_{c}")

        key = '_'.join(key_parts)
        if not storage.is_pattern_used(uid, key):
            storage.add_pattern(uid, key)
            return ' '.join(pattern)

    storage.clear_patterns(uid)
    return gen_pattern_with_word_count(uid, total_words)

def arabic_to_num(txt):
    txt = txt.strip()
    nums = {
        'صفر': 0, 'واحد': 1, 'اثنان': 2, 'اثنين': 2, 'ثلاثة': 3, 'ثلاث': 3, 'أربعة': 4, 'أربع': 4,
        'خمسة': 5, 'خمس': 5, 'ستة': 6, 'ست': 6, 'سبعة': 7, 'سبع': 7, 'ثمانية': 8, 'ثماني': 8, 'ثمان': 8,
        'تسعة': 9, 'تسع': 9, 'عشرة': 10, 'عشر': 10,
        'احدى عشر': 11, 'احد عشر': 11, 'اثنا عشر': 12, 'اثني عشر': 12,
        'ثلاثة عشر': 13, 'ثلاث عشر': 13, 'أربعة عشر': 14, 'أربع عشر': 14,
        'خمسة عشر': 15, 'خمس عشر': 15, 'ستة عشر': 16, 'ست عشر': 16,
        'سبعة عشر': 17, 'سبع عشر': 17, 'ثمانية عشر': 18, 'ثماني عشر': 18, 'ثمان عشر': 18,
        'تسعة عشر': 19, 'تسع عشر': 19, 'عشرون': 20, 'عشرين': 20,
        'ثلاثون': 30, 'ثلاثين': 30, 'أربعون': 40, 'أربعين': 40,
        'خمسون': 50, 'خمسين': 50, 'ستون': 60, 'ستين': 60,
        'سبعون': 70, 'سبعين': 70, 'ثمانون': 80, 'ثمانين': 80,
        'تسعون': 90, 'تسعين': 90, 'مئة': 100, 'مائة': 100, 'مية': 100
    }

    if txt in nums:
        return nums[txt]

    try:
        return int(txt)
    except ValueError:
        return None

def has_permission(uid, level):
    if storage.is_main_owner(uid):
        return True
    if level == "admin":
        return storage.is_admin(uid) or storage.is_owner(uid)
    if level == "owner":
        return storage.is_owner(uid)
    return False

def get_user_id_by_username(username):
    """البحث عن ID المستخدم من اليوزرنيم"""
    if not username:
        return None
    username = username.lower().strip()
    for uid_str, user_data in storage.data.get("users", {}).items():
        stored_username = user_data.get("username")
        if stored_username and stored_username.lower().strip() == username:
            return int(uid_str)
    return None

async def check_and_ban_cheater(
    u: Update,
    c: ContextTypes.DEFAULT_TYPE,
    wpm: float,
    section_type: str,
    accuracy: float | None = None,
):
    """Check if user is cheating (WPM >= 290 with 100% accuracy in non-repeat sections) and ban them
    
    Auto-ban ONLY applies when ALL these conditions are met:
    1. WPM >= 290
    2. Accuracy is exactly 100%
    
    The auto-ban applies regardless of whether accuracy mode is enabled or disabled.
    Manual/admin bans are NOT affected by this function.
    """
    # الأقسام المستثناة من نظام مكافحة الغش
    EXEMPT_SECTIONS = ["كرر", "دبل", "تر", "خصص"]

    if not u.effective_user or u.message is None:
        return False
    
    uid = u.effective_user.id
    cid = u.message.chat_id

    #  المالك الأساسي محمي من الحظر حتى في نظام مكافحة الغش
    if storage.is_main_owner(uid):
        return False

    # الحظر التلقائي يتطلب شرطين معاً:
    # 1. سرعة >= 290
    # 2. دقة = 100% بالضبط
    # يُطبق في كلا الوضعين (تفعيل الدقة وتعطيل الدقة)
    if (wpm >= 290 and 
        section_type not in EXEMPT_SECTIONS and 
        accuracy is not None and 
        accuracy == 100.0):
        
        # حظر المستخدم وحذفه من الصدارة تلقائياً (سبب: تجاوز حد السرعة)
        storage.ban_user(uid, reason="تجاوز حد السرعة")

        # إرسال رسالة الحظر للمستخدم
        await u.message.reply_text("ارسل تصويرك في الخاص @iv511vi ولا راح يستمر الباند او اثبت انك مب نسوخي")

        return True  # تم حظره

    return False  # لم يتم حظره

managers = {
    "جمم": LocalJSONManager("جمم", URLS["جمم"]),
    "ويكي": LocalJSONManager("ويكي", URLS["ويكي"]),
    "مس": LocalJSONManager("مس", URLS["مس"]),
    "شرط": LocalJSONManager("شرط", URLS["شرط"]),
    "فكك": LocalJSONManager("فكك", URLS["فكك"]),
    "صج": LocalJSONManager("صج", URLS["صج"]),
    "شك": LocalJSONManager("شك", URLS["شك"]),
    "جش": LocalJSONManager("جش", URLS["جش"]),
    "دبل": LocalJSONManager("دبل", URLS["دبل"]),
    "تر": LocalJSONManager("تر", URLS["تر"]),
    "عكس": LocalJSONManager("عكس", URLS["عكس"]),
    "فر": LocalJSONManager("فر", URLS["فر"], lang="persian"),
    "E": LocalJSONManager("E", URLS["E"], lang="english"),
    "قص": StoriesManager(URLS["قص"], min_words=5, max_words=50),
    "نص": NassContentManager(NASS_DRIVE_URLS, min_words=5, max_words=50),
    "طب": TibbContentManager(URLS.get("طب", ""), min_words=5, max_words=50),
    "جب": WajabManager(JAB_WORDS, min_length=7, max_length=20)
}


class AsManager:
    """مدير قسم (اص) - يستورد الجمل من قسم (مس) ويصفّيها من الرموز والأرقام

    الجملة المخزنة (المرجعية) تكون نظيفة بدون زخرفة، والمعروضة للمستخدم مزخرفة.
    """
    def __init__(self, source_manager):
        self.source = source_manager
        self.section_name = "اص"

    def get(self):
        """يرجع الجملة الأصلية النظيفة (بدون زخرفة) - وهي المرجع لحساب الدقة"""
        for _ in range(20):
            raw = self.source.get()
            cleaned = as_strip_to_arabic(raw)
            if cleaned and len(cleaned.split()) >= 2:
                return cleaned
        return as_strip_to_arabic(self.source.get()) or "لا توجد جمل حالياً"

    def get_multiple(self, count=2):
        results = []
        for raw in self.source.get_multiple(count * 2):
            cleaned = as_strip_to_arabic(raw)
            if cleaned:
                results.append(cleaned)
            if len(results) >= count:
                break
        return results


managers["اص"] = AsManager(managers["مس"])

async def require_channel_membership(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """يضمن أن المستخدم مشترك في القناة المطلوبة قبل استخدام البوت"""
    if not u.effective_user:
        return True

    uid = u.effective_user.id
    try:
        member = await c.bot.get_chat_member(REQUIRED_CHANNEL, uid)
        status = getattr(member, "status", None)
        if status in {"member", "administrator", "creator"}:
            return True
    except Exception as e:
        print(f"[SUBSCRIPTION] فشل التحقق من اشتراك المستخدم {uid}: {e}")

    if u.message:
        await u.message.reply_text(
            f"عشان تقدر تستخدم البوت لازم تشترك أولاً في القناة:\n{REQUIRED_CHANNEL_LINK}\n\nبعد الاشتراك أعد تشغيل /start"
        )
    elif u.callback_query:
        await u.callback_query.answer(
            f"اشترك في القناة أولاً: {REQUIRED_CHANNEL_LINK}",
            show_alert=True
        )
    return False

def is_bot_command_text(text: str) -> bool:
    """يرجع True إذا كان النص رسالة أمر معروف للبوت"""
    cleaned = text.strip()
    if not cleaned:
        return False
    if cleaned.startswith('/'):
        return True
    if cleaned.startswith('تغيير') or cleaned.startswith('تسجيل'):
        return True
    return cleaned in BOT_COMMAND_TEXTS

async def cmd_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.message or not u.message.from_user:
        return
    uid = u.message.from_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not await require_channel_membership(u, c):
        return

    # ملاحظة: أوامر تفعيل/تعطيل الدقة تُعالَج داخل معالج الرسائل العام

    # للمستخدمين الجدد: لا نعرض الرسالة الترحيبة هنا
    # الرسالة ستظهر عند أول طلب أمر
    await show_bot_sections(u, c)

async def show_device_type_selection(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """عرض اختيار نوع الجهاز للمستخدم الجديد"""
    if not u.message or not u.message.from_user:
        return
    uid = u.message.from_user.id

    msg = (
        "ارحب اول شي انت جوال ولا خارجي اختر من الازرار\n\n"
        "انتبه اذا اخترت انت جوال ولا خارجي ترا بيثبت ولا يمديك تغير\n\n"
        "في صدارة الجوال لو نلقى خارجي او العكس راح يتبند من البوت تماما\n\n"
        "موفق"
    )

    keyboard = [
        [InlineKeyboardButton("جوال", callback_data="device_type_جوال")],
        [InlineKeyboardButton("خارجي", callback_data="device_type_خارجي")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await u.message.reply_text(msg, reply_markup=reply_markup)

async def show_bot_sections(u: Update, c: ContextTypes.DEFAULT_TYPE, is_callback=False, message_thread_id=None):
    if is_callback and u.callback_query:
        uid = u.callback_query.from_user.id
    elif u.effective_user:
        uid = u.effective_user.id
    else:
        return

    if storage.is_banned(uid):
        if is_callback and u.callback_query:
            await u.callback_query.answer("انت محظور تواصل مع @iv511vi")
        elif u.message:
            await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    msg = (
        "الأقسام المتاحة:\n\n"
        "- (عشوائي) - خليط كل الأقسام في قسم واحد كل شوي قسم بشكل عشوائي\n"
        "- (نص) - 25 مليون مقاله عشوائية من مصادر مختلفة\n"
        "- (طب) - مقالات متواصله مكمله لبعض\n"
        "- (جمم) - مقالات عادية\n"
        "- (ويكي) - مقالات ويكيبيديا\n"
        "- (مس) - مقالات ويكيبيديا كلمات سهله\n"
        "- (اص) - مقالات مزخرفة ضد النسخ\n"
        "- (صج) - كلمات عشوائية صعبة\n"
        "- (جب) - كلمات عشوائية سهله\n"
        "- (شك) - مقالات عامية\n"
        "- (جش) - مقالات الاقتباسات\n"
        "- (قص) - قصص وأجزاء أدبية\n"
        "- (كرر) - تكرار الكلمات\n"
        "- (شرط) - مقالات شروط\n"
        "- (فكك) - فك كلمات\n"
        "- (دبل) - تكرار كل كلمة مرتين\n"
        "- (تر) - تكرار كل كلمة ثلاث مرات\n"
        "- (عكس) - كتابة الجملة بالعكس\n"
        "- (فر) - مقالات باللغة الفارسية\n"
        "- (E) - مقالات باللغة الإنجليزية\n"
        "- (رق) - مقالات أرقام\n"
        "- (حر) - مقالات أحرف\n"
        "- (خصص) - اختر الكلمات اللي تبيها والعب فيها\n"
        "- (كشف) - كشف كل أنواع الغش - اكتب (غير الكشف) - للتغيير حسب نوع الغش المستعمل\n\n"
        "مميزات البوت وأوامره في زر أوامر البوت\n"
    )

    keyboard = [
        [InlineKeyboardButton("أوامر البوت", callback_data="show_commands")],
        [InlineKeyboardButton("أقسام البوت", callback_data="show_sections")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_callback:
        if u.callback_query:
            try:
                await u.callback_query.edit_message_text(msg, reply_markup=reply_markup)
            except BadRequest:
                pass
    else:
        if u.message:
            await u.message.reply_text(msg, reply_markup=reply_markup)

async def show_bot_commands(u: Update, c: ContextTypes.DEFAULT_TYPE, is_callback=False):
    if is_callback and u.callback_query:
        uid = u.callback_query.from_user.id
    elif u.effective_user:
        uid = u.effective_user.id
    else:
        return

    if storage.is_banned(uid):
        if is_callback and u.callback_query:
            await u.callback_query.answer("انت محظور تواصل مع @iv511vi")
        elif u.message:
            await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    msg = (
        "https://t.me/dzatttt\n"
        "كل ما يخص البوت راح تلقاه هنا بأذن الله\n"
        "-----------------------------\n"
        "أوامر البوت:\n"
        "-----------------------------\n"
        "(تفعيل الدقة) عشان تخلي البوت يطلع دقتك في الرسايل ويحسب لك حتى لو غلطت بحرف او حرفين\n\n"
        "(تعطيل الدقة) عشان ترجع البوت بشكل طبيعي بدون دقة\n"
        "-----------------------------\n"
        "- (أون لاين) - لعب مباريات 1v1\n"
        "- (سجلي) - عرض إحصائيات أون لاين\n"
        "-----------------------------\n"
        "- (الصدارة) - المتصدرين\n"
        "- (صدارة الاون لاين) - صدارة الانتصارات في 1v1\n"
        "- (جوائزي) - عرض جوائزك\n"
        "- (تقدمي) - عرض لفلك والتقدم نحو اللفل التالي\n"
        "-----------------------------\n"
        "- (فتح جولة) - فتح جولة جديدة\n"
        "- (جولة) - عرض إحصائيات الجولة\n"
        "- (قفل جولة) - إنهاء الجولة الحالية\n"
        "-----------------------------\n"
        "- (تلقائي) - وضع الجمل التلقائية المتتالية\n"
        "-----------------------------\n"
        "- (غير الرق) - عشان تغيير نظام رق\n"
        "- (غير الكشف) - عشان تغير نظام الكشف\n"
        "-----------------------------\n"
        "- (صنفي) - عرض صنفك الحالي (جوال / خارجي)\n"
        "-----------------------------\n"
        "(حذف تخصيص {اختصار التخصيص}) عشان تحذف تخصيص معين \n\n"
        "(كلمات تخصيص {اختصار التخصيص}) عشان تعرف كلمات التخصيص\n\n"
        "(تعديل تخصيص {اختصار التخصيص}) عشان تعدل التخصيص\n\n"
        "- (المحفوظ) - عرض التخصيصات المحفوظة\n"
        "-----------------------------\n"
        "(جب حرفين) يخلي جب ينزل كلمات من حرفين \n"
        "(جب ثلاث حروف) يخلي جب ينزل كلمات من ثلاث حروف\n"
        "(جب اربع حروف) يخلي جب ينزل كلمات من أربع حروف \n"
        "(جب خمسه حروف) يخلي جب ينزل كلمات من خمس حروف \n"
        "(جب مختلط) من كل الأقسام كلمات \n"
        "(جب قديم) نفس الجب القديم \n"
        "-----------------------------\n"
        "(اص) جمل قسم مس بحروف مزخرفة - اكتبها بحروفها العادية بدون زخرفة ولا تطويل\n"
        "-----------------------------\n"
        "اكتب اسم قسم بعده رقم يحدد عدد كلمات المقالة - (*اي قسم* 40)\n\n"
        "((ريست) - يرجع كل الأقسام زي ما كانت)\n"
    )
    
    keyboard = [
        [InlineKeyboardButton("أوامر البوت", callback_data="show_commands")],
        [InlineKeyboardButton("أقسام البوت", callback_data="show_sections")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_callback:
        if u.callback_query:
            try:
                await u.callback_query.edit_message_text(msg, reply_markup=reply_markup)
            except BadRequest:
                pass
    else:
        if u.message:
            await u.message.reply_text(msg, reply_markup=reply_markup)

async def show_all_bot_commands(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not (storage.is_main_owner(uid) or storage.is_owner(uid)):
        await u.message.reply_text("هذا الأمر خاص بالمالك والمالك الرئيسي فقط")
        return

    msg = (

        "جميع أوامر البوت - نسخة كاملة\n"
        "-----------------------------------\n\n"

        "أوامر أون لاين (المباريات):\n"

        "- (أون لاين) أو (اون لاين) - البحث عن خصم ولعب مباراة 1v1\n"
        "- (سجلي) - عرض إحصائياتك الشخصية في أون لاين (فوز، خسارة، انسحاب، معدل الفوز)\n"
        "- (انسحب) - الاستسلام من المباراة الحالية (سيُسجل انسحاب)\n"
        "- (شطب) - طلب تجاوز الجملة الحالية (يحتاج موافقة الخصم)\n"
        "- (الغاء) - إلغاء البحث عن خصم أثناء المطابقة\n\n"

        "أوامر الجولات العادية:\n"

        "- (فتح جولة) - فتح جولة جديدة في المجموعة\n"
        "- (جولة) - عرض معلومات الجولة الحالية والإحصائيات\n"
        "- (قفل جولة) أو (قفل جوله) - إنهاء الجولة الحالية\n"
        "- (مدد) - مد الجولة بعد الفوز (للعب جولات إضافية)\n"
        "- (ة) - مسح أو حذف الإجابة الأخيرة\n"
        "- (ق) - إلغاء الجولة الحالية\n"
        "- (قف) - التوقف عن الكتابة في الجولة\n"
        "- (منظم) - عرض معلومات منظم الجولة الحالية\n\n"

        "أوامر الصدارة والإحصائيات:\n"

        "- (الصدارة) أو (توب) - عرض الصدارة في جميع الأقسام\n"
        "- (صدارة الاون لاين) - عرض صدارة الاون لاين (الانتصارات في 1v1)\n"
        "- (جوائزي) - عرض الجوائز التي حصلت عليها\n"
        "- (تقدمي) - عرض مستواك والتقدم نحو المستوى التالي\n"
        "- (المزالين) - عرض الأشخاص المزالين من الصدارة\n\n"

        "أوامر السرعة والتدريب:\n"

        "- (سبيد) - عرض سرعتك الحالية\n"
        "- (سبيد وقف) - إيقاف مراقبة السرعة\n"
        "- (تلقائي) - تفعيل وضع الجمل التلقائية المتتالية\n\n"
        "- (تفعيل الدقة) - تفعيل نظام الدقة لرسائلك\n"
        "- (تعطيل الدقة) - تعطيل نظام الدقة لرسائلك (تقبل الإجابة فقط لو 100%)\n\n"

        "أوامر الأقسام والتخصيص:\n"

        "- (غير الرق) - تغيير طريقة عرض الأرقام\n"
        "- (ريست رق) - إعادة تعيين نظام الأرقام\n"
        "- (ريست) - إعادة تعيين جميع الأقسام والتفضيلات\n"
        "- (خصص) - إنشاء مجموعات كلمات مخصصة (حد أقصى 5 مجموعات، 200 كلمة لكل واحدة)\n"
        "- (المحفوظ) - عرض المجموعات المخصصة المحفوظة لديك\n"
        "- اكتب اسم القسم + رقم: مثال (جمم 40) = اطلب 40 كلمة من قسم جمم\n\n"

        "أقسام البوت المتاحة:\n"

        "- (عشوائي) - خليط كل الأقسام في قسم واحد كل شوي قسم بشكل عشوائي\n"

        "- (نص) - 25 مليون جملة من مصادر متنوعة\n"
    "- (طب) - جمل بالترتيب لكل مستخدم (تقدم مستقل)\n"
        "- (جمم) - جمل عادية وعشوائية\n"
        "- (ويكي) - جمل من ويكيبيديا\n"
        "- (مس) - جمل مس\n"
        "- (صج) - كلمات صعبة\n"
        "- (جب) - كلمات سهلة\n"
        "- (شك) - جمل عامية/دارجة\n"
        "- (جش) - اقتباسات وحكم\n"
        "- (قص) - قصص وأجزاء أدبية\n"
        "- (كرر) - تكرار الكلمات\n"
        "- (خصص) - اختر الكلمات اللي تبيها والعب\n"
        "- (شرط) - جمل بالشروط والتركيبات المعقدة\n"
        "- (فكك) - فك وتحليل الكلمات\n"
        "- (دبل) - تكرار كل كلمة مرتين\n"
        "- (تر) - تكرار كل كلمة ثلاث مرات\n"
        "- (عكس) - كتابة الجملة بالعكس\n"
        "- (فر) - جمل باللغة الفارسية\n"
        "- (E) - جمل باللغة الإنجليزية\n"
        "- (رق) - جمل أرقام\n"
        "- (حر) - جمل أحرف\n\n"

        "أوامر إدارية (للملاك والمالك الرئيسي):\n"

        "- (إدارة) أو (اداره) أو (ادارة) - قائمة الأوامر الإدارية الكاملة\n"
        "- (رفع ادمن) - ترقية مستخدم لمشرف (للمالك الرئيسي فقط)\n"
        "- (رفع مالك) - ترقية مستخدم لمالك\n"
        "- (إزالة ادمن) أو (ازاله ادمن) - إزالة صلاحيات مشرف (للمالك الرئيسي فقط)\n"
        "- (إزالة مالك) أو (ازالة مالك) - إزالة صلاحيات مالك (للمالك الرئيسي فقط)\n"
        "- (تنزيل ادمن) أو (تنزيل أدمن) - تنزيل الأدمن إلى عضو عادي (للمالك الرئيسي فقط)\n"
        "- (تنزيل مالك) - تنزيل المالك إلى عضو عادي (للمالك الرئيسي فقط)\n"
        "- (باند) - حظر مستخدم من البوت\n"
        "- (الغاء باند) أو (فك باند) - إلغاء الحظر عن مستخدم\n"
        "- (حظر) - حظر مستخدم من البوت باستخدام الرد على الرسالة\n"
        "- (الغاء حظر) - إلغاء حظر مستخدم\n"
        "- (ريست ادمن) - مسح جميع المشرفين (للمالك الرئيسي فقط)\n"
        "- (ريست المالك) أو (ريست ملاك) - مسح جميع الملاك (للمالك الرئيسي فقط)\n"
        "- (ريست صدارة) - إعادة تعيين الصدارة وتوزيع الجوائز\n"
        "- (إذاعة) - بث رسالة لجميع المستخدمين\n"
        "- (الإشراف) - قائمة الإشراف والمراقبة\n"
        "- (احصاء) - إحصائيات عامة للبوت\n"
        "- (تفاعل البوت) - عدد الأوامر المستدعاة اليوم وأمس\n"
        "- (المستخدمين) - عدد المستخدمين الكلي\n"
        "- (عرض الكل) - عرض جميع المستخدمين\n"
        "- (المحظورين) - عرض قائمة المستخدمين المحظورين\n"
        "- (ايديه) - الرد على رسالة مستخدم لمعرفة ID الخاص به\n"
        "- (شطب [رقم]) - خصم نقاط من مستخدم برد على رسالته\n\n"

        "أوامر أخرى:\n"

        "- (عرض) أو (مقالات) أو (بوت) - عرض الأقسام المتاحة\n"
        "- (عرض جميع الاوامر) أو (جميع الاوامر) أو (الاوامر كاملة) - عرض جميع الأوامر (للملاك فقط)\n"
        "- (صنفي) - عرض صنفك الحالي (جوال / خارجي)\n\n"

    )

    await u.message.reply_text(msg)

async def cmd_leaderboard(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    # فحص إذا كان المستخدم اختار device_type
    if not storage.has_device_type(uid):
        # تسجيل أن هذا المستخدم طلب الصدارة
        leaderboard_state[uid] = True
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("جوال", callback_data="device_type_جوال_leaderboard"),
                InlineKeyboardButton("خارجي", callback_data="device_type_خارجي_leaderboard")
            ]
        ])
        msg = (
            "ارحب اول شي انت جوال ولا خارجي اختر من الازرار\n\n"
            "انتبه اذا اخترت انت جوال ولا خارجي ترا بيثبت ولا يمديك تغير\n\n"
            "في صدارة الجوال لو نلقى خارجي او العكس راح يتبند من البوت تماما\n\n"
            "موفق"
        )
        await u.message.reply_text(msg, reply_markup=keyboard)
        return

    # عرض رسالة اختيار نوع الصدارة
    keyboard = [
        [InlineKeyboardButton("صدارة الخارجي", callback_data="leaderboard_خارجي")],
        [InlineKeyboardButton("صدارة الجوال", callback_data="leaderboard_جوال")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await u.message.reply_text(
        "ارحب اختر من الازرار وش تبي صدارة الخارجي ولا الجوال؟\n\n"
        "اتمنى اي رقم راح يجيبه شخص يكون مصور واي رقم عالي بدون تصوير او اثبات بينشال من التوب",
        reply_markup=reply_markup
    )

async def cmd_awards(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    awards = storage.get_awards(uid)
    if not awards:
        await u.message.reply_text("لا توجد جوائز لديك بعد")
        return

    msg = "جوائزك:\n\n"
    positions = {1: "المركز الأول", 2: "المركز الثاني", 3: "المركز الثالث"}

    for aw in awards:
        dt = datetime.fromisoformat(aw['date']).strftime('%Y-%m-%d')
        position = positions.get(aw.get('position'), "")
        week = aw.get('week', "")
        section = aw.get('type', "")
        wpm = aw.get('wpm', 0)

        week_text = f"الأسبوع {week}" if week else ""
        msg += f"{position} - {section}\n"
        msg += f"السرعة: {wpm:.2f} WPM\n"
        msg += f"{week_text} ({dt})\n\n"

    await u.message.reply_text(msg)

async def cmd_round(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.effective_user or not u.effective_chat or not u.message:
        return
    uid = u.effective_user.id
    cid = u.effective_chat.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    existing_round = storage.get_round(cid)
    if existing_round:
        await u.message.reply_text("فيه جوله شغالة اكتب قفل جوله عشان تتقفل")
        return

    storage.set_pending_round_setup(cid, uid, True)
    await u.message.reply_text("من كم تبي الجولة تكون؟")

    await asyncio.sleep(20)

    if storage.get_pending_round_setup(cid) == uid:
        storage.set_pending_round_setup(cid, uid, False)
        await c.bot.send_message(chat_id=cid, text="لم يختر منشئ الجولة اي عدد لذا افتحوا جولة جديدة")

async def cmd_show_round(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.effective_user or not u.effective_chat or not u.message:
        return
    uid = u.effective_user.id
    cid = u.effective_chat.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    existing_round = storage.get_round(cid)
    if not existing_round:
        await u.message.reply_text("لا توجد جولة مفتوحة حالياً")
        return

    stats = storage.get_round_stats(cid)
    if stats:
        await u.message.reply_text(stats)

async def cmd_show_organizer(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.effective_user or not u.effective_chat or not u.message:
        return
    uid = u.effective_user.id
    cid = u.effective_chat.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    existing_round = storage.get_round(cid)
    if not existing_round:
        await u.message.reply_text("لا توجد جولة مفتوحة حالياً")
        return

    starter_uid = existing_round.get("starter_uid")
    if not starter_uid:
        await u.message.reply_text("لا يوجد منظم للجولة الحالية")
        return

    organizer_data = storage.data.get("users", {}).get(str(starter_uid), {})
    organizer_name = organizer_data.get("first_name", "غير معروف")
    organizer_username = organizer_data.get("username")

    level_info = storage.get_level_info(starter_uid)
    level = level_info["level"]

    awards = storage.get_awards(starter_uid)
    awards_count = len(awards) if awards else 0

    mention = f"@{organizer_username}" if organizer_username else organizer_name

    msg = f"خصائص المنظم\n\n"
    msg += f"الشطب : تشطب بهذه الطريقة\n~شطب 1 من@iv511vi ~\n\n"
    msg += f"عشان تعطي احد نقطه ~لو بتلعب ببوت ثاني~ اكتب نقطه بالرد على رسالته\n\n"
    msg += f"منظم الجولة الحالي ~البوت و {mention}~"

    await u.message.reply_text(msg)

async def cmd_end_round(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.effective_user or not u.effective_chat or not u.message:
        return
    uid = u.effective_user.id
    cid = u.effective_chat.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    round_data = storage.get_round(cid)
    if not round_data:
        await u.message.reply_text("لا توجد جولة مفتوحة حالياً")
        return

    starter_uid = round_data.get("starter_uid")
    is_starter = (starter_uid == uid)

    is_admin = False
    try:
        chat_member = await c.bot.get_chat_member(cid, uid)
        is_admin = chat_member.status in ['creator', 'administrator']
    except:
        pass

    if not is_starter and not is_admin:
        await u.message.reply_text("منشئ الجولة ينهي الجولة فقط او مشرفين المجموعة")
        return

    storage.end_round(cid)
    await u.message.reply_text("تم إنهاء الجولة")

async def cmd_ban(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not has_permission(uid, "admin"):
        await u.message.reply_text("هذا الأمر للمشرفين فقط")
        return

    if u.message.reply_to_message and u.message.reply_to_message.from_user:
        target_uid = u.message.reply_to_message.from_user.id

        if storage.is_main_owner(target_uid):
            await u.message.reply_text("لا يمكنك حظر المالك الأساسي")
            return

        # الأدمن ما يقدر يحظر مالك أو أدمن ثاني
        if not (storage.is_main_owner(uid) or storage.is_owner(uid)):
            if storage.is_owner(target_uid) or storage.is_admin(target_uid):
                await u.message.reply_text("ما تقدر تحظر مالك أو مشرف")
                return

        storage.ban_user(
            target_uid, reason="حظر يدوي من مشرف",
            by_uid=uid,
            by_username=u.effective_user.username,
            by_name=u.effective_user.first_name
        )
        if storage.is_main_owner(uid):
            await u.message.reply_text("سمعً وطاعة سيدي")
        else:
            await u.message.reply_text(f"تم حظر المستخدم")
    else:
        await u.message.reply_text("رد على رسالة المستخدم لحظره")

async def cmd_ban_by_id(u: Update, c: ContextTypes.DEFAULT_TYPE, target_uid: int):
    """حظر مستخدم برقم ID مباشرة"""
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not has_permission(uid, "admin"):
        await u.message.reply_text("هذا الأمر للمشرفين فقط")
        return

    if storage.is_main_owner(target_uid):
        await u.message.reply_text("لا يمكنك حظر المالك الأساسي")
        return

    # الأدمن ما يقدر يحظر مالك أو أدمن ثاني
    if not (storage.is_main_owner(uid) or storage.is_owner(uid)):
        if storage.is_owner(target_uid) or storage.is_admin(target_uid):
            await u.message.reply_text("ما تقدر تحظر مالك أو مشرف")
            return

    storage.ban_user(
        target_uid, reason="حظر يدوي من مشرف",
        by_uid=uid,
        by_username=u.effective_user.username,
        by_name=u.effective_user.first_name
    )
    if storage.is_main_owner(uid):
        await u.message.reply_text("سمعً وطاعة سيدي")
    else:
        await u.message.reply_text(f"تم حظر المستخدم")

async def cmd_unban(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not has_permission(uid, "admin"):
        await u.message.reply_text("هذا الأمر للمشرفين فقط")
        return

    if u.message.reply_to_message and u.message.reply_to_message.from_user:
        target_uid = u.message.reply_to_message.from_user.id
        success = storage.unban_user(target_uid)
        if success:
            await u.message.reply_text(f"تم إلغاء حظر المستخدم")
        else:
            await u.message.reply_text(f"المستخدم غير محظور")
    else:
        await u.message.reply_text("رد على رسالة المستخدم لإلغاء حظره")

async def cmd_unban_by_id(u: Update, c: ContextTypes.DEFAULT_TYPE, target_uid: int):
    """إزالة حظر مستخدم برقم ID مباشرة"""
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not has_permission(uid, "admin"):
        await u.message.reply_text("هذا الأمر للمشرفين فقط")
        return

    success = storage.unban_user(target_uid)
    if success:
        await u.message.reply_text(f"تم إلغاء حظر المستخدم")
    else:
        await u.message.reply_text(f"المستخدم غير محظور")

async def cmd_restore(u: Update, c: ContextTypes.DEFAULT_TYPE, show_buttons=True):
    """استعادة مستخدم للصدارة
    show_buttons: إذا كان True، عرض الزرين للاختيار. إذا كان False، استعادة مباشرة
    """
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not has_permission(uid, "admin"):
        await u.message.reply_text("هذا الأمر للمشرفين فقط")
        return

    # الحصول على target_uid من الرد أو من الأمر
    target_uid = None
    if u.message.reply_to_message and u.message.reply_to_message.from_user:
        target_uid = u.message.reply_to_message.from_user.id
    else:
        # محاولة الحصول عليه من نص الأمر
        if u.message.text:
            args = u.message.text.split()
        else:
            args = []
        if len(args) > 1:
            try:
                target_uid = int(args[1])
            except ValueError:
                # قد يكون اسم مستخدم - البحث عنه
                search_name = args[1].lstrip("@").lower()
                for uid_str, user_data in storage.data["users"].items():
                    user_username = user_data.get("username", "").lower()
                    if user_username and user_username == search_name:
                        target_uid = int(uid_str)
                        print(f"[RESTORE] Found user by username: {search_name} -> {target_uid}")
                        break

                if not target_uid:
                    # لم نعثر على المستخدم
                    print(f"[RESTORE] Username not found: {search_name}")
                    # حاول البحث عن جميع المستخدمين المتاحين
                    available = []
                    for uid_str, user_data in storage.data["users"].items():
                        if user_data.get("username"):
                            available.append(f"@{user_data.get('username')}")

                    available_str = ", ".join(available[:5]) if available else "لا توجد مستخدمات"
                    await u.message.reply_text(
                        f" لم أجد المستخدم: @{search_name}\n\n"
                        f" أمثلة على مستخدمات موجودة: {available_str}\n\n"
                        f"استخدم:\n"
                        f"/restore <ID أو @اسم>\n"
                        f"أو رد على رسالة المستخدم واستخدم /restore"
                    )
                    return

    if not target_uid:
        await u.message.reply_text(" حدث خطأ. حاول:\n/restore <ID>\nأو رد على رسالة المستخدم واستخدم /restore")
        return

    # التحقق من أن المستخدم محذوف من الصدارة فعلاً
    if not storage.is_removed_from_leaderboard(target_uid):
        await u.message.reply_text("هذا المستخدم غير محذوف من الصدارة")
        return

    target_user = storage.data["users"].get(str(target_uid), {})
    target_name = f"@{target_user.get('username')}" if target_user.get('username') else target_user.get('first_name', 'المستخدم')

    if show_buttons:
        # عرض أزرار الاستعادة
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(" استعادة مع الأرقام السابقة", callback_data=f"restore_with_scores_{target_uid}"),
                InlineKeyboardButton(" استعادة بدون أرقام", callback_data=f"restore_without_scores_{target_uid}")
            ]
        ])

        await u.message.reply_text(
            f"اختر طريقة الاستعادة للمستخدم {target_name}:\n\n"
            f" <b>مع الأرقام السابقة:</b> سيتم استعادة جميع أرقامه السابقة\n"
            f" <b>بدون أرقام:</b> سيتم تفعيل الصدارة له فقط بدون الأرقام القديمة",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        # استعادة مباشرة بدون الأرقام (بدون أزرار) - صدارة نظيفة
        success = storage.restore_from_leaderboard(target_uid, restore_scores=False)
        if success:
            await u.message.reply_text(f" تم استعادة {target_name} في الصدارة (بدون أرقام سابقة)!")
            storage.save(force=True)
        else:
            await u.message.reply_text(" لم يتمكن من استعادة المستخدم")

async def cmd_broadcast_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not has_permission(uid, "owner"):
        await u.message.reply_text("هذا الأمر للمالكين فقط")
        return

    storage.set_broadcast_mode(uid, True)
    await u.message.reply_text("تم تفعيل وضع الإذاعة. أرسل الرسالة التي تريد إذاعتها الآن.")

async def cmd_private_broadcast_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """أمر إذاعة الخاص - للمالكين فقط"""
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not has_permission(uid, "owner"):
        await u.message.reply_text("هذا الأمر للمالكين فقط")
        return

    private_broadcast_mode[uid] = True
    await u.message.reply_text("تم تفعيل وضع إذاعة الخاص. أرسل الرسالة التي تريد إذاعتها للمستخدمين الآن.")

async def cmd_groups_broadcast_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """أمر إذاعة القروبات - للمالكين فقط"""
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not has_permission(uid, "owner"):
        await u.message.reply_text("هذا الأمر للمالكين فقط")
        return

    groups_broadcast_mode[uid] = True
    await u.message.reply_text("تم تفعيل وضع إذاعة القروبات. أرسل الرسالة التي تريد إذاعتها للمجموعات الآن.")

async def cmd_fast_ban_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """أمر الباند السريع - للمالك الأساسي فقط"""
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not storage.is_main_owner(uid):
        await u.message.reply_text("هذا الأمر للمالك الأساسي فقط")
        return

    fast_ban_mode[uid] = True
    await u.message.reply_text("حلو ارسل لي يزعيم")

async def cmd_stats(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not storage.is_main_owner(uid):
        await u.message.reply_text("هذا الأمر للمالك الأساسي فقط")
        return

    total_users = len(storage.data["users"])
    total_chats = len(storage.data["chats"])
    banned_count = len(storage.banned_data["banned"])

    stats_details = "\n\nإحصائيات الأقسام:\n"
    types = ["جمم", "ويكي", "مس", "اص", "صج", "شك", "جش", "قص", "نص", "طب", "جب", "كرر", "شرط", "فكك", "دبل", "تر", "عكس", "فر", "E", "رق", "حر"]

    total_usage = {}
    for date, commands in storage.data["stats"].items():
        for cmd, count in commands.items():
            if cmd in types:
                total_usage[cmd] = total_usage.get(cmd, 0) + count

    for typ in types:
        usage = total_usage.get(typ, 0)
        stats_details += f"- {typ}: {usage} مرة\n"

    msg = (
        f"إحصائيات البوت:\n\n"
        f"المستخدمين: {total_users}\n"
        f"المجموعات: {total_chats}\n"
        f"المحظورين: {banned_count}"
        f"{stats_details}"
    )

    await u.message.reply_text(msg)

async def cmd_banned_list(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المحظورين مع أسمائهم وايدياتهم وسبب الحظر"""
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not storage.is_main_owner(uid):
        await u.message.reply_text("هذا الأمر للمالك الأساسي فقط")
        return

    banned_ids = storage.banned_data["banned"]

    if not banned_ids:
        await u.message.reply_text("لا يوجد مستخدمين محظورين حالياً")
        return

    msg = f"قائمة المحظورين ({len(banned_ids)}):\n\n"

    for idx, uid_str in enumerate(banned_ids, 1):
        user_data = storage.data["users"].get(uid_str, {})
        username = user_data.get("username")
        first_name = user_data.get("first_name", "مستخدم")

        if username:
            display = f"@{username}"
        else:
            display = first_name

        msg += f"{idx}. {display} (ID: {uid_str})\n"

        # معلومات الحظر: السبب ومن حظر
        info = storage.banned_data.get("info", {}).get(uid_str, {})
        reason = info.get("reason") or "بدون سبب مسجل"
        by_uid = info.get("by_uid")
        by_username = info.get("by_username")
        by_name = info.get("by_name")

        if reason == "تجاوز حد السرعة":
            msg += f"   السبب: متجاوز حد السرعة الموضوع في الكود\n"
        elif by_uid:
            by_display = by_name or "مشرف"
            if by_username:
                by_display = f"{by_display} (@{by_username})"
            msg += f"   انحظر بواسطة المشرف {by_display} (ID: {by_uid}) — {reason}\n"
        else:
            msg += f"   السبب: {reason}\n"
        msg += "\n"

        # تقسيم الرسالة إذا تجاوزت الحد المسموح
        if len(msg) > 3500:
            await u.message.reply_text(msg)
            msg = ""

    if msg:
        await u.message.reply_text(msg)

async def cmd_show_all_users(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """عرض جميع المستخدمين الذين لعبوا في البوت"""
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not storage.is_main_owner(uid):
        await u.message.reply_text("هذا الأمر للمالك الأساسي فقط")
        return

    users = storage.data.get("users", {})

    if not users:
        await u.message.reply_text("لا يوجد مستخدمين حتى الآن")
        return

    msg = f"قائمة جميع المستخدمين ({len(users)}):\n\n"

    for uid_str, user_data in sorted(users.items()):
        username = user_data.get("username")
        first_name = user_data.get("first_name", "مستخدم")

        if username:
            display = f"@{username}"
        else:
            display = first_name

        msg += f"{display} : {uid_str}\n"

        # تقسيم الرسالة إذا تجاوزت 4096 حرف
        if len(msg) > 3500:
            await u.message.reply_text(msg)
            msg = ""

    if msg:
        await u.message.reply_text(msg)

async def cmd_admin_menu(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة الأوامر الإدارية"""
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    if not has_permission(uid, "admin"):
        await u.message.reply_text("انت لست مشرف")
        return

    msg = (
        "قائمة الأوامر الإدارية:\n\n"
        "عرض البيانات:\n"
        "- احصاء - إحصائيات البوت (للمالك الأساسي فقط)\n"
        "- المحظورين - قائمة المحظورين\n"
        "- الإشراف - قائمة المشرفين والملاك\n\n"
        "إدارة الحظر:\n"
        "- حظر [ID] - حظر مستخدم برقم ID\n"
        "- إزالة حظر [ID] - إزالة الحظر\n"
        "- ازالة حظر [ID] - إزالة الحظر (بدون همزة)\n"
        "- باند - حظر برد على الرسالة\n"
        "- الغاء باند - إزالة الحظر برد على الرسالة\n\n"
        "أوامر أخرى:\n"
        "- إذاعة - بث رسالة للجميع (للمالكين فقط)\n"
        "- ايديه - عرض ID المستخدم (للمالك الأساسي فقط)\n"
    )

    keyboard = [[InlineKeyboardButton("إخفاء", callback_data="hide_message")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await u.message.reply_text(msg, reply_markup=reply_markup)

async def cmd_supervision(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not u.effective_user or not u.message:
        return
    uid = u.effective_user.id

    if storage.is_banned(uid):
        await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    msg = "قائمة الإشراف:\n\n"

    msg += "المالك الأساسي:\n"
    owner_data = storage.data["users"].get(str(OWNER_ID), {})
    owner_username = owner_data.get("username")
    if owner_username:
        msg += f"- @{owner_username}\n"
    else:
        msg += f"- {owner_data.get('first_name', 'المالك الأساسي')}\n"

    owners = storage.get_all_owners()
    if owners:
        msg += "\nالملاك:\n"
        for owner_id in owners:
            user_data = storage.data["users"].get(str(owner_id), {})
            username = user_data.get("username")
            if username:
                msg += f"- @{username}\n"
            else:
                msg += f"- {user_data.get('first_name', 'مالك')}\n"

    admins = storage.get_all_admins()
    if admins:
        msg += "\nالادمنز:\n"
        for admin_id in admins:
            user_data = storage.data["users"].get(str(admin_id), {})
            username = user_data.get("username")
            if username:
                msg += f"- @{username}\n"
            else:
                msg += f"- {user_data.get('first_name', 'ادمن')}\n"

    if not owners and not admins:
        msg += "\nلا يوجد ملاك أو ادمنز حالياً."

    await u.message.reply_text(msg)

async def send_auto_sentence(c: ContextTypes.DEFAULT_TYPE, cid, auto_data):
    sections = auto_data["sections"]
    last_section = auto_data.get("last_used_section")
    message_thread_id = auto_data.get("message_thread_id")

    available_sections = [s for s in sections if s != last_section] if len(sections) > 1 and last_section else sections
    if not available_sections:
        available_sections = sections

    selected_section = random.choice(available_sections)
    storage.set_auto_last_section(cid, selected_section)

    if selected_section in ["جمم", "ويكي", "مس", "صج", "شك", "جش", "قص", "نص", "طب", "فر", "E"]:
        sent = managers[selected_section].get()
        storage.save_session(auto_data["uid"], cid, f"تلقائي_{selected_section}", sent, time.time(), sent=True)
        display = format_display(sent)
        await c.bot.send_message(chat_id=cid, text=display, message_thread_id=message_thread_id)
    elif selected_section == "شرط":
        sent = managers["شرط"].get()
        cond = random.choice(CONDITIONS)
        full = f"{sent}||{cond}"
        storage.save_session(auto_data["uid"], cid, f"تلقائي_{selected_section}", full, time.time(), sent=True)
        await c.bot.send_message(chat_id=cid, text=cond, message_thread_id=message_thread_id)
        await asyncio.sleep(2)
        await c.bot.send_message(chat_id=cid, text=format_display(sent), message_thread_id=message_thread_id)
    elif selected_section == "فكك":
        sent = managers["فكك"].get()
        storage.save_session(auto_data["uid"], cid, f"تلقائي_{selected_section}", sent, time.time(), sent=True)
        await c.bot.send_message(chat_id=cid, text=format_display(sent), message_thread_id=message_thread_id)
    elif selected_section in ["دبل", "تر", "عكس"]:
        sent = managers[selected_section].get()
        storage.save_session(auto_data["uid"], cid, f"تلقائي_{selected_section}", sent, time.time(), sent=True)
        display = format_display(sent)
        await c.bot.send_message(chat_id=cid, text=display, message_thread_id=message_thread_id)
    elif selected_section == "كرر":
        pref_count = storage.get_preference(auto_data["uid"], "كرر")
        if pref_count is None or pref_count < 3:
            pref_count = random.randint(3, 5)
        patterns = gen_pattern(auto_data["uid"], pref_count)
        pattern = " ".join(patterns)
        storage.save_session(auto_data["uid"], cid, f"تلقائي_{selected_section}", pattern, time.time(), sent=True)
        await c.bot.send_message(chat_id=cid, text=pattern, message_thread_id=message_thread_id)
    elif selected_section == "رق":
        sent = generate_random_sentence(auto_data["uid"], NUMBER_WORDS, 7, 20, "رق")
        storage.save_session(auto_data["uid"], cid, f"تلقائي_{selected_section}", sent, time.time(), sent=True)
        display = format_display(sent)
        await c.bot.send_message(chat_id=cid, text=display, message_thread_id=message_thread_id)
    elif selected_section == "حر":
        sent = generate_random_sentence(auto_data["uid"], LETTER_WORDS, 7, 20, "حر")
        storage.save_session(auto_data["uid"], cid, f"تلقائي_{selected_section}", sent, time.time(), sent=True)
        display = format_display(sent)
        await c.bot.send_message(chat_id=cid, text=display, message_thread_id=message_thread_id)
    elif selected_section == "جب":
        sent = managers["جب"].get()
        storage.save_session(auto_data["uid"], cid, f"تلقائي_{selected_section}", sent, time.time(), sent=True)
        display = format_display(sent)
        await c.bot.send_message(chat_id=cid, text=display, message_thread_id=message_thread_id)

async def kick_all_chat_members(bot, cid, skip_ids=None):
    """يطرد كل الأعضاء المسجلين عند البوت في قروب معين (باند + فك باند = طرد)"""
    if skip_ids is None:
        skip_ids = set()
    skip_ids = set(skip_ids)
    skip_ids.add(bot.id)
    skip_ids.add(OWNER_ID)

    # نتخطى ملاك ومشرفين البوت
    for o in storage.data.get("owners", []):
        try:
            skip_ids.add(int(o))
        except (ValueError, TypeError):
            pass
    for a in storage.data.get("admins", []):
        try:
            skip_ids.add(int(a))
        except (ValueError, TypeError):
            pass

    # مشرفين القروب ما يمدينا نطردهم
    try:
        admins = await bot.get_chat_administrators(cid)
        for adm in admins:
            skip_ids.add(adm.user.id)
    except Exception:
        pass

    members = list(storage.data.get("chat_members", {}).get(str(cid), {}).keys())
    targets = []
    for m in members:
        try:
            mid = int(m)
            if mid not in skip_ids:
                targets.append(mid)
        except (ValueError, TypeError):
            continue

    kicked = 0
    failed = 0
    sem = asyncio.Semaphore(8)

    async def kick_one(mid):
        nonlocal kicked, failed
        async with sem:
            try:
                await bot.ban_chat_member(cid, mid)
                await bot.unban_chat_member(cid, mid)
                kicked += 1
            except Exception:
                failed += 1

    if targets:
        await asyncio.gather(*(kick_one(mid) for mid in targets))
    return kicked, failed, len(targets)

async def resolve_group_from_link(bot, link):
    """يحول رابط قروب (عام أو خاص) إلى chat_id"""
    link = link.strip()
    if not link:
        return None
    if 't.me/' not in link and not link.startswith('@'):
        return None

    path = link.split('t.me/')[-1].split('?')[0].rstrip('/').strip()

    # رابط خاص: https://t.me/+abc123
    if path.startswith('+'):
        target_hash = path[1:]
        for cid_str in storage.data.get("chats", {}):
            try:
                cid = int(cid_str)
            except (ValueError, TypeError):
                continue
            try:
                exported = await bot.export_chat_invite_link(cid)
                exported_hash = exported.rstrip('/').split('/')[-1].lstrip('+')
                if exported_hash == target_hash:
                    return cid
            except Exception:
                continue
        return None

    # رابط خاص قديم: https://t.me/joinchat/abc123
    if path.startswith('joinchat/'):
        target_hash = path.split('/', 1)[1].lstrip('+')
        for cid_str in storage.data.get("chats", {}):
            try:
                cid = int(cid_str)
            except (ValueError, TypeError):
                continue
            try:
                exported = await bot.export_chat_invite_link(cid)
                exported_hash = exported.rstrip('/').split('/')[-1].lstrip('+')
                if exported_hash == target_hash:
                    return cid
            except Exception:
                continue
        return None

    # رابط عام: https://t.me/username أو @username
    username = path.lstrip('@')
    if not username:
        return None
    try:
        chat = await bot.get_chat(f"@{username}")
        return chat.id
    except Exception:
        return None

# ===== حدود سرعة الصدارة (التوب) =====
# كل الأقسام حدها 190 ما عدا مس وجب حدهم 210
# ===== نظام التعديل/التصحيح (يكتب كلمة ناقصة بعد إجابة خاطئة) =====
# الأقسام اللي يدعمها نظام التعديل (أقسام كلمات عادية)
CORRECTION_SECTIONS = ["جمم", "ويكي", "مس", "صج", "شك", "جش", "قص", "نص", "طب", "حر", "جب", "فر", "E"]

def clean_correction_text(text):
    """ينظف رسالة التعديل من أي رموز (مثل *بك) ويخليها كلمة واحدة"""
    t = text.strip()
    # إزالة كل الرموز والمسافات والشرطات - يبقى الحروف والأرقام فقط
    t = re.sub(r'[^\u0600-\u06FFa-zA-Z0-9]+', '', t)
    return t

def word_overlap_ratio(orig, text):
    """نسبة الكلمات المشتركة بين الجملة الأصلية ومحاولة المستخدم"""
    try:
        o = set(normalize(orig).split())
        t = set(normalize(text).split())
    except Exception:
        return 0.0
    if not o:
        return 0.0
    return len(o & t) / len(o)

def find_missing_words(orig, attempt):
    """يرجع الكلمات الناقصة في محاولة المستخدم مقارنة بالجملة الأصلية"""
    if not attempt:
        return []
    try:
        orig_words = normalize(orig).split()
        attempt_words = normalize(attempt).split()
    except Exception:
        return []
    from collections import Counter
    oc = Counter(orig_words)
    ac = Counter(attempt_words)
    missing = []
    for w, cnt in oc.items():
        have = ac.get(w, 0)
        if have < cnt:
            missing.extend([w] * (cnt - have))
    return missing

# ===== نظام نطاق الكلمات (ويكي من 10 الى 20) =====
# الأقسام اللي تدعم تحديد عدد الكلمات
RANGE_SECTIONS = ["جمم", "ويكي", "مس", "صج", "شك", "جش", "قص", "نص", "طب", "حر", "جب", "فر", "E", "اص", "عكس"]

def get_random_word_count(uid, section):
    """يرجع عدد كلمات عشوائي داخل نطاق (من X الى Y) إذا المستخدم سواه"""
    r = storage.get_preference(uid, f"{section}__range")
    if isinstance(r, (list, tuple)) and len(r) == 2:
        try:
            lo, hi = int(r[0]), int(r[1])
        except (ValueError, TypeError):
            return None
        if 1 <= lo <= hi <= 60:
            return random.randint(lo, hi)
    return None

def build_sentence_for_section(uid, section, count):
    """يبني جملة لعدد كلمات محدد - يدعم جب (أنواعه) وباقي الأقسام"""
    if section == "جب":
        jab_type = user_jab_type.get(uid, "قديم")
        if jab_type == "حرفين":
            words = JAB_2_LETTERS
        elif jab_type == "ثلاث":
            words = JAB_3_LETTERS
        elif jab_type == "اربع":
            words = JAB_4_LETTERS
        elif jab_type == "خمس":
            words = JAB_5_LETTERS
        elif jab_type == "مختلط":
            words = JAB_2_LETTERS + JAB_3_LETTERS + JAB_4_LETTERS + JAB_5_LETTERS
        else:
            words = JAB_WORDS
        return generate_random_sentence(uid, words, count, count, "جب")
    sent = get_text_with_word_count(managers[section], count)
    if not sent:
        sent = managers[section].get()
    return sent

# ===== إذاعة سريعة وكفؤة (إرسال متوازي مع معالجة Rate Limit) =====
async def broadcast_send_many(bot, targets, text, pin=False, concurrency=20):
    """إرسال رسالة لعدد كبير من المستخدمين/القروبات بسرعة:
    - إرسال متوازي (20 رسالة بنفس الوقت)
    - معالجة RetryAfter من تلجرام (429) تلقائياً
    - إرسال على دفعات حتى لا يضغط على الذاكرة
    - يوصل للكل مهما كان العدد كبير
    """
    sent = 0
    failed = 0
    sem = asyncio.Semaphore(concurrency)

    async def send_one(target):
        nonlocal sent, failed
        async with sem:
            for attempt in range(3):
                try:
                    msg = await bot.send_message(chat_id=target, text=text)
                    sent += 1
                    if pin:
                        try:
                            await bot.pin_chat_message(chat_id=target, message_id=msg.message_id, disable_notification=True)
                        except Exception:
                            pass
                    return
                except RetryAfter as e:
                    # تلجرام طلب ننتظر - ننتظر المدة المحددة ونعيد
                    wait = getattr(e, "retry_after", 1)
                    await asyncio.sleep(min(wait, 30))
                except Exception:
                    # فشل نهائي (محظور من الخاص أو مشرف في القروب...) نكمل
                    break
            failed += 1

    # نرسل على دفعات (50 بالدفعة) - كل دفعة متوازية داخلياً
    BATCH = 50
    for i in range(0, len(targets), BATCH):
        chunk = targets[i:i + BATCH]
        await asyncio.gather(*(send_one(t) for t in chunk))
        await asyncio.sleep(0.05)

    return sent, failed

async def handle_msg(u: Update, c: ContextTypes.DEFAULT_TYPE):
    global processed_updates, last_processed_update_cleanup

    if not u.message or not u.message.text:
        return

    update_id = u.update_id

    if update_id in processed_updates:
        return

    processed_updates.add(update_id)

    current_time = time.time()
    if len(processed_updates) >= MAX_PROCESSED_UPDATES or (current_time - last_processed_update_cleanup > 300):
        processed_updates.clear()
        last_processed_update_cleanup = current_time

    uid = u.effective_user.id
    cid = u.effective_chat.id
    text = u.message.text.strip()

    # إذا القروب موقوف بأمر (وقف هنا) البوت ما يشتغل فيه نهائياً إلا مع المالك الأساسي
    if u.effective_chat and u.effective_chat.type in ("group", "supergroup") and storage.is_chat_paused(cid) and not storage.is_main_owner(uid):
        return

    # تسجيل العضو داخل القروب (عشان أمر طرد الكل)
    if u.effective_chat and u.effective_chat.type in ("group", "supergroup"):
        storage.record_chat_member(cid, uid)

    # فحص الاشتراك فقط عند كتابة أوامر البوت المعروفة، وليس عند أي رسالة عادية
    # استثناء: أوامر المالك الرئيسي (اطلع من هنا / طرد الكل / روابط القروبات / وقف هنا...) ما تحتاج اشتراك بالقناة
    owner_commands = ("اطلع من هنا", "طرد الكل", "اطرد الكل", "روابط القروبات", "وقف هنا", "شغل هنا", "نزل مالك")
    cmd_without_slash = text.strip().lstrip('/').strip()
    is_owner_cmd = any(cmd_without_slash == x or cmd_without_slash.startswith(x + " ") for x in owner_commands)
    if is_bot_command_text(text) and not is_owner_cmd:
        if not await require_channel_membership(u, c):
            return

    # إزالة "/" من البداية إذا كانت موجودة (لتفعيل الأوامر بدون /)
    if text.startswith('/'):
        text = text[1:]

    # أمر (اطلع من هنا) - يخلي البوت يخرج من المجموعة بشكل كامل
    if text == "اطلع من هنا":
        if u.effective_chat.type in ("group", "supergroup"):
            # الصلاحية: المالك الأساسي فقط
            if storage.is_main_owner(uid):
                try:
                    await u.message.reply_text("سمعً وطاعه يا سيدي")
                    storage.remove_chat(cid)
                    await u.effective_chat.leave()
                except Exception as e:
                    print(f"[LEAVE] فشل خروج البوت من المجموعة {cid}: {e}")
                    await u.message.reply_text("ما قدرت اطلع من المجموعة، تأكد ان عندي صلاحية الخروج")
            else:
                await u.message.reply_text("ما تقدر تامرني اطلع، هذا الأمر للمالك الرئيسي فقط")
        else:
            await u.message.reply_text("هذا الأمر يشتغل فقط داخل المجموعات")
        return

    # أمر (وقف هنا) - المالك الأساسي يوقف البوت في القروب نهائياً
    if text == "وقف هنا":
        if u.effective_chat.type in ("group", "supergroup"):
            if storage.is_main_owner(uid):
                storage.pause_chat(cid)
                await u.message.reply_text("تم، البوت وقف شغله في هذي المجموعة ✋")
            else:
                await u.message.reply_text("هذا الأمر للمالك الرئيسي فقط")
        else:
            await u.message.reply_text("هذا الأمر يشتغل فقط داخل المجموعات")
        return

    # أمر (شغل هنا) - المالك الأساسي يرجع البوت يشتغل في القروب
    if text == "شغل هنا":
        if u.effective_chat.type in ("group", "supergroup"):
            if storage.is_main_owner(uid):
                storage.unpause_chat(cid)
                await u.message.reply_text("تم، البوت رجع يشتغل في هذي المجموعة ✅")
            else:
                await u.message.reply_text("هذا الأمر للمالك الرئيسي فقط")
        else:
            await u.message.reply_text("هذا الأمر يشتغل فقط داخل المجموعات")
        return

    # أمر (أيدي الإشراف) - يعرض ايديات المشرفين مع يوزراتهم
    if text == "أيدي الإشراف":
        msg = "أيدي الإشراف:\n\n"

        msg += "المالك الأساسي:\n"
        owner_data = storage.data["users"].get(str(OWNER_ID), {})
        owner_username = owner_data.get("username")
        owner_name = owner_data.get("first_name", "المالك الأساسي")
        msg += f"- {('@' + owner_username) if owner_username else owner_name} (ID: {OWNER_ID})\n"

        owners = storage.get_all_owners()
        if owners:
            msg += "\nالملاك:\n"
            for owner_id in owners:
                user_data = storage.data["users"].get(str(owner_id), {})
                username = user_data.get("username")
                name = user_data.get("first_name", "مالك")
                msg += f"- {('@' + username) if username else name} (ID: {owner_id})\n"

        admins = storage.get_all_admins()
        if admins:
            msg += "\nالادمنز:\n"
            for admin_id in admins:
                user_data = storage.data["users"].get(str(admin_id), {})
                username = user_data.get("username")
                name = user_data.get("first_name", "ادمن")
                msg += f"- {('@' + username) if username else name} (ID: {admin_id})\n"

        if not owners and not admins:
            msg += "\nلا يوجد ملاك أو ادمنز حالياً.\n"

        await u.message.reply_text(msg)
        return

    # أمر (طرد الكل / اطرد الكل) - للمالك الرئيسي فقط، يطرد كل أعضاء القروب
    if text == "طرد الكل" or text == "اطرد الكل" or text.startswith("طرد الكل ") or text.startswith("اطرد الكل "):
        if not storage.is_main_owner(uid):
            await u.message.reply_text("هذا الأمر للمالك الرئيسي فقط")
            return

        target_cid = None
        link = None
        if " " in text:
            link = text.split(" ", 1)[1].strip()

        if link:
            target_cid = await resolve_group_from_link(c.bot, link)
            if target_cid is None:
                await u.message.reply_text("ما لقيت المجموعة من الرابط، تأكد ان البوت موجود فيها واني مشرف بصلاحية سحب الرابط")
                return
        else:
            if u.effective_chat.type not in ("group", "supergroup"):
                await u.message.reply_text("اكتبه داخل المجموعه او ارفق رابط المجموعه زي كذا:\n(اطرد الكل https://t.me/.....)")
                return
            target_cid = cid

        # نتأكد ان البوت مشرف في المجموعة المستهدفة
        try:
            me = await c.bot.get_chat_member(target_cid, c.bot.id)
            if me.status not in ("administrator", "creator"):
                await u.message.reply_text("تحتاج ترفعني مشرف في المجموعة (مع صلاحية حظر المستخدمين) عشان اقدر اطرد الكل")
                return
        except Exception:
            await u.message.reply_text("ما قدرت اوصل للمجموعة، تأكد ان البوت موجود فيها")
            return

        await u.message.reply_text("سمعً وطاعة سيدي")
        kicked, failed, total = await kick_all_chat_members(c.bot, target_cid, skip_ids={uid})
        storage.clear_chat_members(target_cid)

        if total == 0:
            await u.message.reply_text("ما فيه اعضاء مسجلين عندي في المجموعة، اللي يرسلون بينسجلون تلقائياً ويمديك تكرر الأمر بعدين")
            return

        result = f"تم طرد {kicked} عضو من المجموعة 🚪"
        if failed:
            result += f"\nفشل طرد {failed} (مشرفين او ما عندي صلاحية عليهم)"
        await u.message.reply_text(result)
        return

    # أمر (روابط القروبات) - للمالك الرئيسي فقط، يرسل روابط كل القروبات اللي البوت فيها
    if text == "روابط القروبات":
        if not storage.is_main_owner(uid):
            await u.message.reply_text("هذا الأمر للمالك الرئيسي فقط")
            return

        chats = storage.data.get("chats", {})
        if not chats:
            await u.message.reply_text("ما فيه قروبات مسجله عندي حالياً")
            return

        await u.message.reply_text("جاري تجميع الروابط...")
        lines = []
        for cid_str, info in chats.items():
            try:
                chat_id = int(cid_str)
            except (ValueError, TypeError):
                continue
            title = (info or {}).get("title", "بدون اسم")
            link = None
            try:
                chat = await c.bot.get_chat(chat_id)
                if getattr(chat, "username", None):
                    link = f"https://t.me/{chat.username}"
            except Exception:
                pass
            if not link:
                try:
                    link = await c.bot.export_chat_invite_link(chat_id)
                except Exception:
                    pass
            if not link:
                try:
                    link = await c.bot.create_chat_invite_link(chat_id)
                except Exception:
                    pass
            if link:
                lines.append(f"🏘 {title}\n{link}")

        if not lines:
            await u.message.reply_text("ما قدرت اجيب الروابط، تأكد اني مشرف في القروبات بصلاحية دعوة المستخدمين")
            return

        # نرسل الروابط على دفعات حتى لو كانت كثيرة
        for i in range(0, len(lines), 10):
            chunk = lines[i:i + 10]
            msg = "روابط القروبات:\n\n" + "\n\n".join(chunk)
            await u.message.reply_text(msg)
        return

    # أمر (نزل مالك [أيدي أو يوزر]) - المالك الأساسي ينزل مالك من الإشراف
    if (text == "نزل مالك" or text.startswith("نزل مالك ")) and storage.is_main_owner(uid):
        target_input = text.replace("نزل مالك", "").strip().lstrip('@').strip()
        if not target_input:
            await u.message.reply_text("استخدم: نزل مالك [أيدي أو يوزر]\nمثل: نزل مالك @username أو نزل مالك 123456789")
            return

        target_uid = None
        if target_input.isdigit():
            target_uid = int(target_input)
        else:
            target_uid = get_user_id_by_username(target_input)
            if target_uid is None:
                try:
                    chat = await c.bot.get_chat(f"@{target_input}")
                    target_uid = chat.id
                except Exception:
                    target_uid = None

        if target_uid is None:
            await u.message.reply_text("ما حصلت المستخدم. تأكد انه مسجل عندي أو استخدم الأيدي الرقمي.")
            return

        if target_uid == OWNER_ID:
            await u.message.reply_text("ما تقدر تنزل نفسك يا المالك الأساسي")
            return

        if not storage.is_owner(target_uid):
            await u.message.reply_text(f"❌ `{target_input}` ليس مالك")
            return

        storage.remove_owner(target_uid)
        user_data = storage.data["users"].get(str(target_uid), {})
        username = user_data.get("username")
        name = user_data.get("first_name", "مستخدم")
        display = f"@{username}" if username else name
        await u.message.reply_text(f"✅ تم تنزيل {display} (`{target_uid}`) من الملاك إلى عضو عادي")
        storage.log_cmd("نزل مالك")
        return

    # رد تلقائي لمن تم تسجيله في خاصية (نشبه) داخل القروبات
    if u.effective_chat and u.effective_chat.type in ("group", "supergroup"):
        shabah_entry = storage.data.get("shabah", {}).get(str(uid))
        if shabah_entry and shabah_entry.get("messages"):
            await u.message.reply_text(random.choice(shabah_entry["messages"]))
            return

    # أوامر تفعيل/تعطيل الدقة للمستخدم (متاحة لأي عضو)
    if text == "تفعيل الدقة":
        # التحقق من وجود جولة نشطة
        round_data = storage.get_round(cid)
        if round_data and not storage.is_round_finished(cid):
            await u.message.reply_text("تنبيه: ما يمديك تفعل وضع الدقة وفيه جوله فاتحة\n\nاكتب (قفل جوله) عشان تقفل الجولة وتقدر تفعل الميزه")
            return
        
        # التحقق إذا كانت الدقة مفعلة بالفعل
        is_already_enabled = is_accuracy_enabled_for(uid)
        if is_already_enabled:
            await u.message.reply_text("تراه شغال اذا ما تبيه اكتب تعطيل الدقة")
            return
        
        storage.save_preference(uid, "accuracy_enabled", True)
        await u.message.reply_text("تم: حلوين فعلت خيار الدقة\n\nالبوت بيسحب لك سرعتك حتى لو تغلط بحرفين او ثلاث")
        return

    if text == "تعطيل الدقة":
        # التحقق من وجود جولة نشطة
        round_data = storage.get_round(cid)
        if round_data and not storage.is_round_finished(cid):
            await u.message.reply_text("تنبيه: ما يمديك تعطل وضع الدقة وفيه جوله فاتحة\n\nاكتب (قفل جوله) عشان تقفل الجولة وتقدر تعدل الإعدادات")
            return
        
        # التحقق إذا كانت الدقة معطلة بالفعل
        is_currently_enabled = is_accuracy_enabled_for(uid)
        if not is_currently_enabled:
            await u.message.reply_text("تراها طافية اذا تبي تشغلها اكتب تفعيل الدقة")
            return
        
        storage.save_preference(uid, "accuracy_enabled", False)
        await u.message.reply_text("تم: تم تعطيل وضع الدقة\n\nالحين البوت ما يحسب لك سرعتك الا اذا كانت الجمله صح مره")
        return

    # معالجة أوامر حذف من الصدارة
    if text.startswith("حذف") and "من صدارة" in text and "قسم" in text:
        await handle_delete_leaderboard(u, c)
        return

    # معالجة أوامر تسجيل المستخدمين (للمالك الأساسي فقط)
    if text.startswith("تسجيل") and len(text) > 5:
        await handle_register_device(u, c)
        return

    # معالجة أوامر تغيير نوع الجهاز مباشرة
    if text.startswith("تغيير") and len(text) > 5:
        await handle_device_type_change(u, c)
        return

    # معالجة أمر نشبه/نشبة للمالك الأساسي
    if text in ["نشبه", "نشبة"] and storage.is_main_owner(uid):
        nshabeh_state[uid] = {
            "stage": "awaiting_target",
            "messages": []
        }
        await u.message.reply_text("حلو، ارسل لي اليوزر أو الايدي للمستخدم اللي تبي تنشب له.")
        return

    # معالجة أمر وقف النشبه للمالك الأساسي
    if text.startswith("وقف النشبه") and storage.is_main_owner(uid):
        target_text = text.replace("وقف النشبه", "").strip().lstrip('@').strip()
        if not target_text:
            await u.message.reply_text("استخدم: وقف النشبه [يوزر أو أيدي]")
            return

        target_uid = None
        if target_text.isdigit():
            target_uid = int(target_text)
        else:
            target_uid = get_user_id_by_username(target_text)

        if target_uid is None:
            await u.message.reply_text("ما حصلت المستخدم. ارسل لي رقم الايدي او يوزر معروف عندي.")
            return

        shabah_key = str(target_uid)
        if shabah_key in storage.data.get("shabah", {}):
            del storage.data["shabah"][shabah_key]
            storage.mark_dirty()
            storage.save(force=True)
            await u.message.reply_text("تم وقف النشبه عن المستخدم.")
        else:
            await u.message.reply_text("ما كان نشبه مفعل لهذا المستخدم.")
        return

    if uid in nshabeh_state:
        state = nshabeh_state[uid]
        stage = state.get("stage")

        if stage == "awaiting_target":
            target_text = text.lstrip('@').strip()
            target_uid = None
            if target_text.isdigit():
                target_uid = int(target_text)
            else:
                target_uid = get_user_id_by_username(target_text)

            if target_uid is None:
                await u.message.reply_text("ما حصلت المستخدم. ارسل لي رقم الايدي او يوزر معروف عندي.")
                return

            state["stage"] = "awaiting_messages"
            state["target_uid"] = target_uid
            state["target_input"] = target_text
            await u.message.reply_text(
                "تم الحين حددت لك اللي تبي تنشب له. ارسل لي الرسائل اللي تبيها تنرسل له واحدة واحدة، ولما تخلص اكتب 'خلاص'."
            )
            return

        if stage == "awaiting_messages":
            if text == "خلاص":
                if not state["messages"]:
                    await u.message.reply_text("ما أضفت أي رسالة بعد. أرسل رسالة أو اكتب 'خلاص' بعد ما تضيف.")
                    return

                target_uid = state["target_uid"]
                storage.data.setdefault("shabah", {})[str(target_uid)] = {
                    "messages": state["messages"],
                    "owner_uid": uid,
                    "created_at": datetime.now().isoformat()
                }
                storage.mark_dirty()
                storage.save(force=True)
                del nshabeh_state[uid]
                await u.message.reply_text(
                    "تم! الحين ثبتت الايدي مع الرسائل. البوت راح يرد للمستخدم برسالة عشوائية من الرسائل اللي عطيتها في أي قروب يرسل فيه."
                )
                return

            state["messages"].append(text)
            await u.message.reply_text(
                "تم حفظ الرسالة. بقي شي؟ إذا تبي تزيد رسالة ثانية ارسلها، وإذا خلصت اكتب 'خلاص'."
            )
            return

    # معالجة أمر "ارجع" أو "رجع" العربي
    if text.startswith("ارجع"):
        # استعادة مباشرة بدون أزرار (ارجع يرجع الأرقام القديمة مباشرة)
        await cmd_restore(u, c, show_buttons=False)
        return

    if text.startswith("رجع"):
        # عرض أزرار الاختيار (رجع يعرض الخيارات)
        await cmd_restore(u, c, show_buttons=True)
        return

    # معالجة حالات التخصيص (customization_state)
    if uid in customization_state:
        state = customization_state[uid]
        stage = state.get("stage")

        # المرحلة: انتظار الكلمات
        if stage == "waiting_words":
            words = text.split()

            # فحص عدد الكلمات (حد أقصى 200)
            if len(words) > 200:
                await u.message.reply_text(f"عدد الكلمات كثير! ({len(words)} كلمة)\nالحد الأقصى 200 كلمة\n\nأعطيني كلمات أقل:")
                return

            state["data"]["words"] = text

            # إذا كان تعديل موجود - انتقل مباشرة للحفظ
            if state["data"].get("edit_shortcut"):
                edit_shortcut = state["data"]["edit_shortcut"]
                uid_str = str(uid)
                storage.customizations_data["customizations"][uid_str][edit_shortcut]["words"] = text
                storage.save_customizations()
                storage.mark_dirty()
                storage.save(force=True)
                del customization_state[uid]
                await u.message.reply_text(f" تم تحديث التخصيص '{edit_shortcut}' بنجاح")
                return

            # إذا كان جديد - انتقل لمرحلة الاختصار
            state["stage"] = "waiting_shortcut"
            await u.message.reply_text("حلو الحين وش تبي الاختصار ؟")
            return

        # المرحلة: انتظار الاختصار
        elif stage == "waiting_shortcut":
            shortcut = text.strip()

            # قائمة أقسام البوت الأساسية
            bot_sections = ["جمم", "ويكي", "مس", "اص", "شرط", "فكك", "صج", "شك", "جش", "دبل", "تر", "عكس", "فر", "E", "قص", "نص", "طب", "جب", "كرر", "رق", "حر"]

            # التحقق من أن الاختصار ليس اسم قسم موجود
            if shortcut in bot_sections:
                await u.message.reply_text(f"ما يمدي أقسام البوت الأساسية فيها ذي الاوامر دور غيرها")
                state["stage"] = "waiting_shortcut"
                return

            # التحقق من أن الاختصار لم يكن مستخدم بالفعل
            uid_str = str(uid)
            customizations = storage.customizations_data.get("customizations", {}).get(uid_str, {})

            if shortcut in customizations:
                await u.message.reply_text(f"الاختصار '{shortcut}' مستخدم بالفعل! اختر واحد ثاني:")
                state["stage"] = "waiting_shortcut"
                return

            # التحقق من عدد التخصيصات (حد أقصى 5)
            if len(customizations) >= 5:
                await u.message.reply_text(f"وصلت للحد الأقصى (خمسة تخصيصات)! احذف واحد عشان تضيف تخصيص جديد")
                del customization_state[uid]
                return

            # حفظ التخصيص الجديد
            if "customizations" not in storage.customizations_data:
                storage.customizations_data["customizations"] = {}
            if uid_str not in storage.customizations_data["customizations"]:
                storage.customizations_data["customizations"][uid_str] = {}

            storage.customizations_data["customizations"][uid_str][shortcut] = {
                "words": state["data"]["words"],
                "type": state["data"].get("type", "normal")
            }
            storage.save_customizations()
            storage.mark_dirty()
            storage.save(force=True)

            del customization_state[uid]

            await u.message.reply_text("خلاص تم اكتب الاختصار اللي انت حطيته وبتنزل لك مقالة\n\nالقسم للمتعه بس ما يحسب في الصدارة شي.")
            return

    usr = u.effective_user.username
    name = u.effective_user.first_name

    # تسجيل المستخدم فقط عند استخدام أمر فعلي أو تفاعل مهم مع البوت
    if is_bot_command_text(text):
        storage.add_user(uid, usr, name)

    # تحديد نوع الدردشة
    is_forum = u.effective_chat.is_forum
    message_thread_id = u.message.message_thread_id if is_forum else None
    in_general_chat = is_forum and message_thread_id is None

    #  فحص device_type في البداية - فقط لـ "الصدارة" و "توب" و "أيدي الصدارة"
    leaderboard_commands = ["الصدارة", "توب", "أيدي الصدارة", "ايدي الصدارة", "أيدي صدارة الجوال", "ايدي صدارة الجوال", "أيدي صدارة خارجي", "ايدي صدارة خارجي"]

    if not storage.has_device_type(uid) and text in leaderboard_commands:
        # تسجيل أن هذا المستخدم طلب الصدارة
        leaderboard_state[uid] = True
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("جوال", callback_data="device_type_جوال_leaderboard"),
                InlineKeyboardButton("خارجي", callback_data="device_type_خارجي_leaderboard")
            ]
        ])
        msg = (
            "ارحب اول شي انت جوال ولا خارجي اختر من الازرار\n\n"
            "انتبه اذا اخترت انت جوال ولا خارجي ترا بيثبت ولا يمديك تغير\n\n"
            "في صدارة الجوال لو نلقى خارجي او العكس راح يتبند من البوت تماما\n\n"
            "موفق"
        )
        await u.message.reply_text(msg, reply_markup=keyboard)
        return

    if u.effective_chat.type in ['group', 'supergroup']:
        chat_title = u.effective_chat.title
        storage.add_chat(cid, chat_title)
    elif is_forum and not in_general_chat:
        chat_title = u.effective_chat.title
        storage.add_chat(cid, chat_title)

    if u.message.reply_to_message and (storage.is_main_owner(uid) or storage.is_owner(uid) or storage.is_admin(uid)):
        # المحظور ما يقدر يستخدم أوامر الرد الإدارية
        if storage.is_banned(uid):
            await u.message.reply_text("انت محظور تواصل مع @iv511vi")
            return

        replied_user = u.message.reply_to_message.from_user
        replied_uid = replied_user.id
        replied_username = replied_user.username
        replied_name = replied_user.first_name

        auto_reply_commands = ["باند", "تقييد", "كتم", "الغاء تقييد", "الغاء باند", "فك باند", "طرد", "الغاء كتم"]

        if text == "باند":
            if storage.is_main_owner(uid) or storage.is_owner(uid) or storage.is_admin(uid):
                if storage.is_main_owner(replied_uid):
                    await u.message.reply_text("لا يمكنك حظر المالك الأساسي")
                    return
                # الأدمن ما يقدر يحظر مالك أو أدمن ثاني
                if not (storage.is_main_owner(uid) or storage.is_owner(uid)):
                    if storage.is_owner(replied_uid) or storage.is_admin(replied_uid):
                        await u.message.reply_text("ما تقدر تحظر مالك أو مشرف")
                        return
                storage.ban_user(
                    replied_uid, reason="حظر يدوي من مشرف",
                    by_uid=uid,
                    by_username=u.effective_user.username,
                    by_name=u.effective_user.first_name
                )
                if storage.is_main_owner(uid):
                    await u.message.reply_to_message.reply_text("سمعً وطاعة سيدي")
                else:
                    await u.message.reply_to_message.reply_text("تم ودن طار يا الامير من البوت")
                return
        elif text in ["الغاء باند", "فك باند"]:
            if storage.is_main_owner(uid) or storage.is_owner(uid) or storage.is_admin(uid):
                storage.unban_user(replied_uid)
                await u.message.reply_to_message.reply_text("عتقناه لوجه الله ، الله يستر عليه")
                return
        elif text in auto_reply_commands:
            await u.message.reply_to_message.reply_text(text)
            return

        if text == "رفع ادمن" and storage.is_main_owner(uid):
            # منع المالك من التأثير على مالك آخر
            if storage.is_owner(replied_uid):
                await u.message.reply_text("اذا بترفع او تنزل تواصل مع @iv511vi")
                return
            
            storage.add_admin(replied_uid)
            mention = f"@{replied_username}" if replied_username else replied_name
            await u.message.reply_text(f"تم رفع {mention} إلى رتبة ادمن")
            await u.message.reply_text(f"{mention} ارحب")
            return

        if text == "رفع مالك":
            # منع المالك من رفع مالك آخر - فقط المالك الأساسي يقدر
            if not storage.is_main_owner(uid):
                await u.message.reply_text("اذا بترفع او تنزل تواصل مع @iv511vi")
                return
            
            # منع المالك الأساسي من رفع مالك على مالك
            if storage.is_owner(replied_uid):
                await u.message.reply_text("اذا بترفع او تنزل تواصل مع @iv511vi")
                return
            
            storage.add_owner(replied_uid)
            mention = f"@{replied_username}" if replied_username else replied_name
            await u.message.reply_text(f"تم رفع {mention} إلى رتبة مالك")
            await u.message.reply_text(f"{mention} ارحب")
            return

        if text in ["إزالة ادمن", "ازاله ادمن"] and storage.is_main_owner(uid):
            # منع المالك من التأثير على مالك آخر
            if storage.is_owner(replied_uid):
                await u.message.reply_text("اذا بترفع او تنزل تواصل مع @iv511vi")
                return
            
            storage.remove_admin(replied_uid)
            await u.message.reply_text("تم طار من الإشراف")
            return

        if text in ["إزالة مالك", "ازالة مالك"] and storage.is_main_owner(uid):
            # منع المالك الأساسي من حذف مالك آخر
            if storage.is_owner(replied_uid):
                await u.message.reply_text("اذا بترفع او تنزل تواصل مع @iv511vi")
                return
            
            storage.remove_owner(replied_uid)
            await u.message.reply_text("تم طار من الإشراف")
            return

        if text in ["تنزيل ادمن", "تنزيل أدمن"] and storage.is_main_owner(uid):
            # منع المالك من التأثير على مالك آخر
            if storage.is_owner(replied_uid):
                await u.message.reply_text("اذا بترفع او تنزل تواصل مع @iv511vi")
                return
            
            if storage.is_admin(replied_uid):
                storage.remove_admin(replied_uid)
                mention = f"@{replied_username}" if replied_username else replied_name
                await u.message.reply_text(f"تم تنزيل {mention} إلى عضو عادي")
            else:
                await u.message.reply_text("هذا الشخص ليس ادمن")
            return

        if text in ["تنزيل مالك"] and storage.is_main_owner(uid):
            if replied_uid == OWNER_ID:
                await u.message.reply_text("ما تقدر تنزل نفسك يا المالك الأساسي")
                return
            
            if storage.is_owner(replied_uid):
                storage.remove_owner(replied_uid)
                mention = f"@{replied_username}" if replied_username else replied_name
                await u.message.reply_text(f"تم تنزيل {mention} إلى عضو عادي")
            else:
                await u.message.reply_text("هذا الشخص ليس مالك")
            return

    # أوامر الترقية بالأيدي المباشر (بدون الرد على الرسالة)
    
    # ترقية ادمن [أيدي أو يوزر]
    if text.startswith("ترقية ادمن ") and storage.is_main_owner(uid):
        target_input = text.replace("ترقية ادمن ", "").strip().lstrip('@')
        
        if not target_input:
            await u.message.reply_text("الرجاء أدخل الأيدي أو اليوزر: `ترقية ادمن 123456789`", parse_mode="Markdown")
            return
        
        try:
            target_uid = int(target_input)
        except ValueError:
            await u.message.reply_text("الرجاء استخدم الأيدي الرقمي: `ترقية ادمن 123456789`", parse_mode="Markdown")
            return
        
        # منع رفع مالك
        if storage.is_owner(target_uid):
            await u.message.reply_text("اذا بترفع او تنزل تواصل مع @iv511vi")
            return
        
        if storage.is_admin(target_uid):
            await u.message.reply_text(f"❌ الأيدي `{target_uid}` بالفعل ادمن", parse_mode="Markdown")
            return
        
        storage.add_admin(target_uid)
        await u.message.reply_text(f"✅ تم رفع الأيدي `{target_uid}` إلى رتبة ادمن", parse_mode="Markdown")
        storage.log_cmd("ترقية ادمن")
        return

    # ترقية مالك [أيدي أو يوزر]
    if text.startswith("ترقية مالك ") and storage.is_main_owner(uid):
        target_input = text.replace("ترقية مالك ", "").strip().lstrip('@')
        
        if not target_input:
            await u.message.reply_text("الرجاء أدخل الأيدي أو اليوزر: `ترقية مالك 123456789`", parse_mode="Markdown")
            return
        
        try:
            target_uid = int(target_input)
        except ValueError:
            await u.message.reply_text("الرجاء استخدم الأيدي الرقمي: `ترقية مالك 123456789`", parse_mode="Markdown")
            return
        
        # منع رفع مالك على مالك
        if storage.is_owner(target_uid):
            await u.message.reply_text("اذا بترفع او تنزل تواصل مع @iv511vi")
            return
        
        storage.add_owner(target_uid)
        await u.message.reply_text(f"✅ تم رفع الأيدي `{target_uid}` إلى رتبة مالك", parse_mode="Markdown")
        storage.log_cmd("ترقية مالك")
        return

    # تنزيل ادمن [أيدي أو يوزر]
    if text.startswith("تنزيل ادمن ") and storage.is_main_owner(uid):
        target_input = text.replace("تنزيل ادمن ", "").strip().lstrip('@')
        
        if not target_input:
            await u.message.reply_text("الرجاء أدخل الأيدي أو اليوزر: `تنزيل ادمن 123456789`", parse_mode="Markdown")
            return
        
        try:
            target_uid = int(target_input)
        except ValueError:
            await u.message.reply_text("الرجاء استخدم الأيدي الرقمي: `تنزيل ادمن 123456789`", parse_mode="Markdown")
            return
        
        # منع تنزيل مالك
        if storage.is_owner(target_uid):
            await u.message.reply_text("اذا بترفع او تنزل تواصل مع @iv511vi")
            return
        
        if storage.is_admin(target_uid):
            storage.remove_admin(target_uid)
            await u.message.reply_text(f"✅ تم تنزيل الأيدي `{target_uid}` إلى عضو عادي", parse_mode="Markdown")
        else:
            await u.message.reply_text(f"❌ الأيدي `{target_uid}` ليس ادمن", parse_mode="Markdown")
        
        storage.log_cmd("تنزيل ادمن")
        return

    # تنزيل مالك [أيدي أو يوزر] - نفس أمر (نزل مالك)
    if text.startswith("تنزيل مالك ") and storage.is_main_owner(uid):
        target_input = text.replace("تنزيل مالك ", "").strip().lstrip('@')
        
        if not target_input:
            await u.message.reply_text("الرجاء أدخل الأيدي أو اليوزر: `تنزيل مالك 123456789`", parse_mode="Markdown")
            return
        
        target_uid = None
        if target_input.isdigit():
            target_uid = int(target_input)
        else:
            target_uid = get_user_id_by_username(target_input)
            if target_uid is None:
                try:
                    chat = await c.bot.get_chat(f"@{target_input}")
                    target_uid = chat.id
                except Exception:
                    target_uid = None
        
        if target_uid is None:
            await u.message.reply_text("ما حصلت المستخدم. تأكد انه مسجل عندي أو استخدم الأيدي الرقمي.")
            return
        
        if target_uid == OWNER_ID:
            await u.message.reply_text("ما تقدر تنزل نفسك يا المالك الأساسي")
            return
        
        if not storage.is_owner(target_uid):
            await u.message.reply_text(f"❌ الأيدي `{target_uid}` ليس مالك", parse_mode="Markdown")
            storage.log_cmd("تنزيل مالك")
            return
        
        storage.remove_owner(target_uid)
        user_data = storage.data["users"].get(str(target_uid), {})
        username = user_data.get("username")
        name = user_data.get("first_name", "مستخدم")
        display = f"@{username}" if username else name
        await u.message.reply_text(f"✅ تم تنزيل {display} (`{target_uid}`) من الملاك إلى عضو عادي")
        storage.log_cmd("تنزيل مالك")
        return

    # نظام شطب برد (للمالك الأساسي والملاك فقط)
    if u.message.reply_to_message and text.startswith("شطب ") and text[4:].isdigit():
        if not (storage.is_main_owner(uid) or storage.is_owner(uid)):
            await u.message.reply_text("هذا الأمر للمالك الأساسي والملاك فقط")
            return

        # التحقق من وجود جولة مفتوحة
        existing_round = storage.get_round(cid)
        if not existing_round:
            await u.message.reply_text("لا توجد جولة مفتوحة حالياً")
            return

        try:
            points = int(text[4:])
            if points < 1:
                await u.message.reply_text("أدخل رقم موجب")
                return

            replied_user = u.message.reply_to_message.from_user
            replied_uid = replied_user.id
            replied_username = replied_user.username
            replied_name = replied_user.first_name

            # خصم النقاط
            if storage.reduce_round_points(cid, replied_uid, points):
                current_round = storage.get_round(cid)
                current_points = current_round.get("wins", {}).get(str(replied_uid), 0)
                target = current_round.get('target', 0)
                mention = f"@{replied_username}" if replied_username else replied_name
                msg = f"تم خصم {points} نقطة من {mention}\n"
                msg += f"النقاط الحالية: {current_points}/{target}"
                await u.message.reply_text(msg)

                # فحص الفوز بعد خصم النقاط
                if current_points >= target:
                    await u.message.reply_text(f"مبروك يا {mention} - أنت الفائز في الجولة!")
                    celebration_message = f"حيك يا {mention}، {mention} هو الفائز بالجولة\nمبروك!"
                    for _ in range(5):
                        await u.message.reply_text(celebration_message)
                        await asyncio.sleep(0.1)
                    storage.set_round_extension_status(cid, True)
                    await u.message.reply_text("الجوله ذي انتهت لكن إذا ودك تكمل على نفس النتيجة اكتب: مدد \n\nاذا ما تبي اكتب : قفل جوله")
            else:
                await u.message.reply_text("المستخدم ليس لديه نقاط في هذه الجولة")
        except Exception as e:
            await u.message.reply_text(f"حدث خطأ: {str(e)}")
        return

    # نظام زيد برد (للمالك الأساسي والملاك فقط)
    if u.message.reply_to_message and text.startswith("زيد ") and text[4:].isdigit():
        if not (storage.is_main_owner(uid) or storage.is_owner(uid)):
            await u.message.reply_text("هذا الأمر للمالك الأساسي والملاك فقط")
            return

        # التحقق من وجود جولة مفتوحة
        existing_round = storage.get_round(cid)
        if not existing_round:
            await u.message.reply_text("لا توجد جولة مفتوحة حالياً")
            return

        try:
            points = int(text[4:])
            if points < 1:
                await u.message.reply_text("أدخل رقم موجب")
                return

            replied_user = u.message.reply_to_message.from_user
            replied_uid = replied_user.id
            replied_username = replied_user.username
            replied_name = replied_user.first_name

            # إضافة النقاط
            for _ in range(points):
                storage.add_win(cid, replied_uid)

            current_round = storage.get_round(cid)
            current_points = current_round.get("wins", {}).get(str(replied_uid), 0)
            target = current_round.get('target', 0)
            mention = f"@{replied_username}" if replied_username else replied_name
            msg = f"تم إضافة {points} نقطة إلى {mention}\n"
            msg += f"النقاط الحالية: {current_points}/{target}"
            await u.message.reply_text(msg)

            # فحص الفوز بعد إضافة النقاط
            if current_points >= target:
                await u.message.reply_text(f"مبروك يا {mention} - أنت الفائز في الجولة!")
                celebration_message = f"حيك يا {mention}، {mention} هو الفائز بالجولة\nمبروك!"
                for _ in range(5):
                    await u.message.reply_text(celebration_message)
                    await asyncio.sleep(0.1)
                storage.set_round_extension_status(cid, True)
                await u.message.reply_text("الجوله ذي انتهت لكن إذا ودك تكمل على نفس النتيجة اكتب: مدد \n\nاذا ما تبي اكتب : قفل جوله")
        except Exception as e:
            await u.message.reply_text(f"حدث خطأ: {str(e)}")
        return

    # نظام إضافة النقاط بالرد برسالة "نقطه" أو "رقم نقطه" (للمالك الأساسي والملاك والمفتاح فقط)
    if u.message.reply_to_message and text.endswith(("نقطه", "نقطة")):
        is_main_owner = storage.is_main_owner(uid)
        is_owner = storage.is_owner(uid)

        # التحقق من وجود جولة مفتوحة
        existing_round = storage.get_round(cid)
        if not existing_round:
            await u.message.reply_text("لا توجد جولة مفتوحة حالياً")
            return

        starter_uid = existing_round.get("starter_uid")
        is_starter = starter_uid and starter_uid == uid

        if not (is_main_owner or is_owner or is_starter):
            await u.message.reply_text("هذا الأمر للمالك الأساسي والملاك والمفتاح فقط")
            return

        # إذا كان المفتاح، تحقق من حد الاستخدام
        if is_starter and not (is_main_owner or is_owner):
            action_count = storage.get_starter_action_count(cid, uid)
            if action_count >= 2:
                await u.message.reply_text("وين يبوي وقف جالس توزع وتشطب على كيفك؟")
                return
            storage.add_starter_action(cid, uid)

        replied_user = u.message.reply_to_message.from_user
        replied_uid = replied_user.id
        replied_username = replied_user.username
        replied_name = replied_user.first_name

        # استخراج الرقم من النص (مثل "5 نقطه")
        points_to_add = 1
        if text not in ["نقطه", "نقطة"]:
            # إزالة "نقطه" أو "نقطة" من آخر النص
            number_part = text.replace("نقطه", "").replace("نقطة", "").strip()
            if number_part:
                try:
                    points_to_add = arabic_to_num(number_part)
                    if points_to_add is None:
                        points_to_add = int(number_part)
                except (ValueError, TypeError):
                    await u.message.reply_text("أدخل رقم صحيح مثل (5 نقطه)")
                    return

                if points_to_add < 1:
                    await u.message.reply_text("أدخل رقم موجب")
                    return

        # إضافة النقاط للمستخدم
        for _ in range(points_to_add):
            storage.add_win(cid, replied_uid)

        current_round = storage.get_round(cid)
        current_points = current_round.get("wins", {}).get(str(replied_uid), 0)
        target = current_round.get('target', 0)

        mention = f"@{replied_username}" if replied_username else replied_name
        msg = f"تم إضافة {points_to_add} نقطة إلى {mention}\n"
        msg += f"النقاط الحالية: {current_points}/{target}"
        await u.message.reply_text(msg)

        # فحص الفوز بعد إضافة النقاط
        if current_points >= target:
            await u.message.reply_text(f"مبروك يا {mention} - أنت الفائز في الجولة!")
            celebration_message = f"حيك يا {mention}، {mention} هو الفائز بالجولة\nمبروك!"
            for _ in range(5):
                await u.message.reply_text(celebration_message)
                await asyncio.sleep(0.1)
            storage.set_round_extension_status(cid, True)
            await u.message.reply_text("الجوله ذي انتهت لكن إذا ودك تكمل على نفس النتيجة اكتب: مدد \n\nاذا ما تبي اكتب : قفل جوله")
        return

    is_broadcast_mode = storage.get_broadcast_mode(uid)

    if storage.is_banned(uid):
        commands = ["الصدارة", "جوائزي", "جولة", "فتح جولة", "باند", "الغاء باند", "إذاعة", "اذاعة الخاص", "اذاعة القروبات", "باند سريع", "احصاء", "الإشراف",
                   "جمم", "ويكي", "مس", "صج", "شك", "جش", "كرر", "شرط", "فكك", "دبل", "تر", "عكس", "عرض", "مقالات", "فر", "E", "e", "رق", "حر", "ريست", "تلقائي"]
        is_command = any(text.startswith(cmd) for cmd in commands)

        if is_command:
            await u.message.reply_text("انت محظور تواصل مع @iv511vi")
        return

    # فحص أوامر الإذاعة والباند السريع قبل معالجة الأوضاع
    if text == "إذاعة":
        await cmd_broadcast_start(u, c)
        storage.log_cmd("إذاعة")
        return

    if text == "اذاعة الخاص":
        await cmd_private_broadcast_start(u, c)
        storage.log_cmd("اذاعة الخاص")
        return

    if text == "اذاعة القروبات":
        await cmd_groups_broadcast_start(u, c)
        storage.log_cmd("اذاعة القروبات")
        return

    if text == "باند سريع":
        await cmd_fast_ban_start(u, c)
        storage.log_cmd("باند سريع")
        return

    if storage.get_broadcast_mode(uid):
        storage.set_broadcast_mode(uid, False)

        # رسالة البداية
        await u.message.reply_text("جارٍ إرسال الإذاعة...")

        user_ids = [int(x) for x in storage.data["users"].keys() if str(x).lstrip('-').isdigit()]
        chat_ids = [int(x) for x in storage.data["chats"].keys() if str(x).lstrip('-').isdigit()]

        # إرسال متوازي سريع للمستخدمين + المجموعات (مع التثبيت)
        s_u, f_u = await broadcast_send_many(c.bot, user_ids, text, pin=True)
        s_c, f_c = await broadcast_send_many(c.bot, chat_ids, text, pin=True)

        # الإحصائيات النهائية
        msg = f"تمت الإذاعة:\n\n"
        msg += f"المستخدمين: {s_u} نجح"
        if f_u > 0:
            msg += f"، {f_u} فشل"
        msg += f"\nالمجموعات: {s_c} نجح"
        if f_c > 0:
            msg += f"، {f_c} فشل"
        await u.message.reply_text(msg)
        return

    # معالجة إذاعة الخاص
    if uid in private_broadcast_mode and private_broadcast_mode[uid]:
        private_broadcast_mode[uid] = False

        # رسالة البداية
        await u.message.reply_text("جارٍ إرسال الإذاعة للمستخدمين...")

        user_ids = [int(x) for x in storage.data["users"].keys() if str(x).lstrip('-').isdigit()]
        sent_users, failed_users = await broadcast_send_many(c.bot, user_ids, text, pin=True)

        # الإحصائيات النهائية
        msg = f"تمت إذاعة الخاص:\n\n"
        msg += f"المستخدمين: {sent_users} نجح"
        if failed_users > 0:
            msg += f"، {failed_users} فشل"
        await u.message.reply_text(msg)
        return

    # معالجة إذاعة القروبات
    if uid in groups_broadcast_mode and groups_broadcast_mode[uid]:
        groups_broadcast_mode[uid] = False

        # رسالة البداية
        await u.message.reply_text("جارٍ إرسال الإذاعة للمجموعات...")

        chat_ids = [int(x) for x in storage.data["chats"].keys() if str(x).lstrip('-').isdigit()]
        sent_chats, failed_chats = await broadcast_send_many(c.bot, chat_ids, text, pin=True)

        # الإحصائيات النهائية
        msg = f"تمت إذاعة القروبات:\n\n"
        msg += f"المجموعات: {sent_chats} نجح"
        if failed_chats > 0:
            msg += f"، {failed_chats} فشل"
        await u.message.reply_text(msg)
        return

    # معالجة الباند السريع
    if uid in fast_ban_mode and fast_ban_mode[uid]:
        # التحقق من أمر القفل
        if text == "قفل الباند السريع":
            fast_ban_mode[uid] = False
            await u.message.reply_text("تم قفل الباند السريع")
            return

        # حظر الأيدي المرسل
        try:
            ban_uid = int(text.strip())
            
            # التحقق من عدم حظر المالك الأساسي نفسه
            if ban_uid == OWNER_ID:
                await u.message.reply_text("ما تقدر تحظر نفسك يا المالك الأساسي!")
                return
            
            # حظر المستخدم
            storage.ban_user(
                ban_uid, reason="حظر يدوي (باند سريع)",
                by_uid=uid,
                by_username=u.effective_user.username,
                by_name=u.effective_user.first_name
            )
            await u.message.reply_text("بقي احد؟")
            
        except ValueError:
            await u.message.reply_text("أرسل رقم أيدي صحيح أو اكتب (قفل الباند السريع) لإنهاء العملية")
        
        return

    if text == "سبيد":
        task_key = str(cid)
        existing_task = speed_bot_tasks.get(task_key)
        if existing_task:
            if not existing_task.done():
                existing_task.cancel()
                try:
                    await existing_task
                except asyncio.CancelledError:
                    pass
            speed_bot_tasks.pop(task_key, None)
        storage.set_speed_bot_enabled(cid, True)
        await u.message.reply_text("سبيد الحين بيكسر راسك تجهز للطحن")
        return

    if text == "سبيد وقف":
        task_key = str(cid)
        task = speed_bot_tasks.pop(task_key, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        storage.set_speed_bot_enabled(cid, False)
        await u.message.reply_text("تم إيقاف سبيد بوت")
        return

    if text.startswith("سبيد "):
        if storage.is_main_owner(uid):
            try:
                parts = text.split()
                if len(parts) == 2:
                    wpm = int(parts[1])
                    if 50 <= wpm <= 5000:
                        storage.set_speed_bot_wpm(cid, wpm)
                        await u.message.reply_text(f"تم تعيين سرعة سبيد إلى {wpm} كلمة/دقيقة")
                    else:
                        await u.message.reply_text("السرعة يجب أن تكون بين 5000 و 50")
                else:
                    await u.message.reply_text("الاستخدام: سبيد [رقم بين 50-5000]")
            except ValueError:
                await u.message.reply_text("الرجاء إدخال رقم صحيح")
        else:
            await u.message.reply_text("هذا الأمر للمالك الأساسي فقط")
        return

    if uid in spam_states and spam_states[uid].get("waiting"):
        spam_states[uid]["waiting"] = False
        spam_states[uid]["message"] = text
        spam_states[uid]["chat_id"] = cid
        spam_running[uid] = True
        
        spam_msg = "تم\n\nذا الأمر ما يتفعل الا اذا فيه شي ماهو كويس\n\nاتمنى محد يزعل\n\nما يمدي يقفل السبام الا مالك البوت او المالك الأساسي للمجموعة بأمر - قفل سبام -"
        sent_msg = await u.message.reply_text(spam_msg)
        try:
            await c.bot.pin_chat_message(chat_id=cid, message_id=sent_msg.message_id, disable_notification=True)
        except:
            pass
        
        async def spam_loop(uid, cid, message, bot):
            count = 0
            while spam_running.get(uid, False):
                try:
                    await bot.send_message(chat_id=cid, text=message)
                    count += 1
                    if count >= 10:
                        await asyncio.sleep(2)
                        count = 0
                except Exception as e:
                    print(f"[SPAM ERROR] {e}")
                    if "flood" in str(e).lower():
                        await asyncio.sleep(5)
                    else:
                        break
        
        task = asyncio.create_task(spam_loop(uid, cid, text, c.bot))
        spam_tasks[uid] = task
        return

    pending_setup = storage.get_pending_round_setup(cid)
    if pending_setup == uid:
        target = arabic_to_num(text)
        if target is None:
            try:
                target = int(text)
            except ValueError:
                await u.message.reply_text("الرجاء إدخال رقم صحيح من 1 إلى 100")
                return

        if target < 1 or target > 100:
            await u.message.reply_text("الرجاء إدخال رقم من 1 إلى 100")
            return

        storage.set_pending_round_setup(cid, uid, False)
        storage.start_round(cid, target, uid)
        storage.set_round_mode(cid, True)
        await u.message.reply_text(f"تم الجولة من {target}\n\nعشان تشوف خصائص المنظم اكتب \"منظم\"")
        return

    auto_mode = storage.get_auto_mode(cid)
    if auto_mode:
        if text == "قف":
            storage.end_auto_mode(cid)
            await u.message.reply_text("تم إيقاف نظام تلقائي")
            storage.log_cmd("قف")
            return

        if text == "ة" and auto_mode["active"]:
            storage.update_auto_activity(cid)
            await send_auto_sentence(c, cid, auto_mode)
            return

        if text == "ق":
            storage.end_auto_mode(cid)
            storage.start_auto_mode(cid, uid, message_thread_id)
            await u.message.reply_text("اختار أقسام جديدة ترا القديمة انحذفت اذا تبيها حطها من جديد\nاكتب الأقسام اللي تبيها وحين تنتهي اكتب انهاء")
            storage.log_cmd("ق")
            return

        if auto_mode["collecting"]:
            valid_sections = ["جمم", "ويكي", "مس", "صج", "شك", "جش", "قص", "نص", "طب", "كرر", "شرط", "فكك", "دبل", "تر", "عكس", "فر", "E", "رق", "حر", "جب"]

            if text in valid_sections:
                if storage.add_auto_section(cid, text):
                    await u.message.reply_text(f"الحين انت أضفت قسم {text} تبي تضيف زيادة او تبي تكتب انهاء؟")
                    return
            elif text == "انهاء":
                if auto_mode["sections"]:
                    storage.finish_auto_collection(cid)
                    await u.message.reply_text("3")
                    await asyncio.sleep(1)
                    await u.message.reply_text("2")
                    await asyncio.sleep(1)
                    await u.message.reply_text("1")
                    await asyncio.sleep(1)

                    updated_auto_mode = storage.get_auto_mode(cid)
                    await send_auto_sentence(c, cid, updated_auto_mode)
                    storage.update_auto_activity(cid)
                else:
                    await u.message.reply_text("لم تختر أي قسم. اكتب اسم قسم أو أكثر ثم اكتب انهاء")
                return
        elif auto_mode["active"]:
            auto_sessions = {}
            for section in auto_mode["sections"]:
                session_key = f"تلقائي_{section}"
                session = storage.get_session(cid, session_key)
                if session:
                    auto_sessions[section] = session

            matched = False
            for section, session in auto_sessions.items():
                typ = session.get("type")
                orig = session.get("text")
                start_time = session.get("time")
                elapsed = time.time() - start_time

                if elapsed > 180:
                    continue

                section_type = typ.replace("تلقائي_", "")

                # حساب الدقة والمطابقة مع دعم الأخطاء البسيطة
                accuracy = None
                user_accuracy_on = is_accuracy_enabled_for(uid)  # ✅ استدعاء واحد فقط
                
                # فحص صحة الإجابة أولاً قبل الحسابات الثقيلة ✅
                if not check_answer_validity(orig, text):
                    continue
                
                # للأقسام النصية: نقبل أي ترتيب أو تكرار للكلمات إذا كانت كل كلمات الأصل موجودة
                if section_type in ["جمم", "ويكي", "مس", "صج", "شك", "جش", "قص", "نص", "طب", "جب", "حر"]:
                    base_accuracy = compute_word_based_accuracy(orig, text, "arabic")
                    all_words_present = base_accuracy == 100.0
                    if user_accuracy_on:
                        # مع تفعيل الدقة: حساب الدقة الفعلية (تسمح بالترتيب/التكرار) + قبول دائماً
                        accuracy = base_accuracy
                        matched = True
                    else:
                        # مع تعطيل الدقة: قبول فقط عند 100%
                        accuracy = base_accuracy
                        matched = all_words_present
                elif section_type == "فر":
                    base_accuracy = compute_word_based_accuracy(orig, text, "persian")
                    all_words_present = base_accuracy == 100.0
                    if user_accuracy_on:
                        # مع تفعيل الدقة: حساب الدقة الفعلية (تسمح بالترتيب/التكرار) + قبول دائماً
                        accuracy = base_accuracy
                        matched = True
                    else:
                        # مع تعطيل الدقة: قبول فقط عند 100%
                        accuracy = base_accuracy
                        matched = all_words_present
                elif section_type == "E":
                    base_accuracy = compute_word_based_accuracy(orig, text, "english")
                    all_words_present = base_accuracy == 100.0
                    if user_accuracy_on:
                        # مع تفعيل الدقة: حساب الدقة الفعلية (تسمح بالترتيب/التكرار) + قبول دائماً
                        accuracy = base_accuracy
                        matched = True
                    else:
                        # مع تعطيل الدقة: قبول فقط عند 100%
                        accuracy = base_accuracy
                        matched = all_words_present
                elif section_type == "رق":
                    if match_numbers(orig, text):
                        matched = True
                        accuracy = compute_accuracy(orig, text, "arabic")
                    else:
                        matched = False
                elif section_type == "كرر":
                    valid, err = validate_repeat(orig, text)
                    matched = bool(valid)
                    if matched:
                        accuracy = compute_accuracy(orig, text, "arabic")
                elif section_type == "شرط":
                    orig_s, cond = orig.split('||')
                    valid, exp = validate_condition(cond, orig_s, text)
                    matched = bool(valid)
                    if matched:
                        accuracy = compute_accuracy(orig, text, "arabic")
                elif section_type == "فكك":
                    if is_correct_disassembly(orig, text):
                        matched = True
                        accuracy = compute_accuracy(orig, text, "arabic")
                    else:
                        matched = False
                elif section_type == "دبل":
                    valid, err = validate_double(orig, text)
                    matched = bool(valid)
                    if matched:
                        accuracy = compute_accuracy(orig, text, "arabic")
                elif section_type == "تر":
                    valid, err = validate_triple(orig, text)
                    matched = bool(valid)
                    if matched:
                        accuracy = compute_accuracy(orig, text, "arabic")
                elif section_type == "عكس":
                    valid, err = validate_reverse(orig, text)
                    matched = bool(valid)
                    if matched:
                        accuracy = compute_accuracy(orig, text, "arabic")

                if matched:
                    # استثناء "كرر" و "دبل وتر" - استخدام كلمات المستخدم
                    # للأقسام الأخرى - استخدام كلمات الجملة الأصلية فقط
                    if section_type in ["كرر", "دبل"]:
                        word_count = count_words_for_wpm(text)
                    else:
                        word_count = count_words_for_wpm(orig)
                    wpm = (word_count / max(elapsed, 0.01)) * 60 + 10

                    # فحص مكافحة الغش
                    if await check_and_ban_cheater(u, c, wpm, section_type, accuracy):
                        storage.del_session(cid, typ)
                        return

                    # حفظ السرعة والقيم: 
                    # - عند تعطيل الدقة: احفظ فقط عند دقة 100%
                    # - عند تفعيل الدقة: احفظ عند دقة >= 80%
                    user_accuracy_on_local = user_accuracy_on  # ✅ استخدام المتغير المحفوظ
                    device_type = storage.get_device_type(uid)
                    
                    # تحديد ما إذا كان يجب حفظ السرعة
                    should_save_speed = False
                    if user_accuracy_on_local:
                        # عند تفعيل الدقة: احفظ السرعة إذا دقة >= 80%، لكن الصدارة فقط عند 100%
                        should_save_speed = (accuracy is not None and accuracy >= 80.0)
                    else:
                        # عند تعطيل الدقة: احفظ إذا دقة 100%
                        should_save_speed = (accuracy is not None and accuracy == 100.0)
                    
                    if should_save_speed:
                        storage.save_speed_for_section(uid, section_type, wpm)
                        # حفظ الصدارة: للأقسام الستة احفظ فقط عند دقة 100% (بغض النظر عن وضع الدقة)
                        # استثناء: جب حرفين لا يحسب في الصدارة
                        leaderboard_sections = ["كرر", "ويكي", "مس", "شك", "جب", "جش", "جمم"]
                        if section_type in leaderboard_sections and accuracy == 100.0:
                            # التحقق من أن جب حرفين لا يدخل الصدارة
                            if section_type == "جب" and user_jab_type.get(uid) == "حرفين":
                                pass  # لا تحفظ جب حرفين في الصدارة
                            else:
                                storage.update_score(uid, section_type, wpm, device_type)
                    
                    storage.add_correct_sentence(uid)

                    # حذف الجلسة وتحديث النشاط دائمًا
                    storage.del_session(cid, typ)
                    storage.update_auto_activity(cid)

                    username = u.effective_user.username or u.effective_user.first_name or "مستخدم"

                    # بناء نص الرد وإضافة الدقة إن وُجدت ومفعّلة (فقط إذا كان يجب حفظ السرعة)
                    if should_save_speed:
                        reply_txt = f"كفو يا {username}\n\nسرعتك: {wpm:.1f} كلمة/دقيقة\nالوقت : {elapsed:.2f} ثانية"
                        if accuracy is not None and user_accuracy_on_local:  # ✅ استخدام المتغير المحفوظ
                            reply_txt += f"\nالدقة : {accuracy}%"
                        await u.message.reply_text(reply_txt)
                    else:
                        # الإجابة صحيحة لكن لا تستحق حفظ سرعة
                        reply_txt = f"صحيح يا {username}"
                        await u.message.reply_text(reply_txt)

                    await asyncio.sleep(1.5)
                    await send_auto_sentence(c, cid, auto_mode)
                    return

    current_time = time.time()
    if current_time - last_command_time[cid][text] < 1:
        return
    last_command_time[cid][text] = current_time

    if text == "تلقائي":
        storage.start_auto_mode(cid, uid, message_thread_id)
        await u.message.reply_text("اختر انواع الأقسام اللتي تريدها حين الإنتهاء اكتب انهاء\n\nعشان تغير الجملة اكتب [ة] وعشان تغير أقسام اكتب [ق] وعشان توقف البوت اكتب قف وبيوقف")
        storage.log_cmd("تلقائي")
        return

    if text == "الصدارة":
        await cmd_leaderboard(u, c)
        storage.log_cmd("الصدارة")
        return

    if text == "صدارة الاون لاين":
        if storage.is_banned(uid):
            await u.message.reply_text("انت محظور تواصل مع @iv511vi")
            return

        msg = await display_online_leaderboard_merged()
        await u.message.reply_text(msg, parse_mode="HTML")
        storage.log_cmd("صدارة الاون لاين")
        return

    # عرض أيديات الإشراف
    if text == "أيدي الإشراف":
        if not (storage.is_main_owner(uid) or storage.is_owner(uid) or storage.is_admin(uid)):
            await u.message.reply_text("هذا الأمر للمشرفين فقط")
            return
        
        admins = storage.get_all_admins()
        owners = storage.get_all_owners()
        
        if not admins and not owners:
            await u.message.reply_text("لا يوجد مشرفون أو ملاك مسجلون حالياً")
            return
        
        msg = "📋 **قائمة الإشراف:**\n\n"
        
        if owners:
            msg += "👑 **الملاك:**\n"
            for owner_id in owners:
                msg += f"• `{owner_id}`\n"
            msg += "\n"
        
        if admins:
            msg += "🔨 **المشرفون:**\n"
            for admin_id in admins:
                msg += f"• `{admin_id}`\n"
        
        await u.message.reply_text(msg, parse_mode="Markdown")
        storage.log_cmd("أيدي الإشراف")
        return

    # حذف مشرف أو مالك من الإشراف
    if text.startswith("حذف ") and "من الإشراف" in text:
        if not storage.is_main_owner(uid):
            await u.message.reply_text("هذا الأمر للمالك الأساسي فقط")
            return
        
        # استخراج الأيدي أو اليوزر
        part = text.replace("حذف ", "").replace("من الإشراف", "").strip()
        
        if not part:
            await u.message.reply_text("الرجاء أدخل الأيدي أو اليوزر: `حذف 123456789 من الإشراف`", parse_mode="Markdown")
            return
        
        # تنسيق الأيدي أو اليوزر
        target_id = part.lstrip('@').strip()
        
        # التحقق إذا كان رقم أو يوزر
        is_numeric = target_id.isdigit()
        
        if not is_numeric:
            # إذا كان يوزر، ابحث عنه في قاعدة البيانات
            # للآن سنفترض أنه أيدي مباشر
            await u.message.reply_text("الرجاء استخدم الأيدي الرقمي: `حذف 123456789 من الإشراف`", parse_mode="Markdown")
            return
        
        try:
            target_uid = int(target_id)
        except ValueError:
            await u.message.reply_text("أيدي غير صحيح")
            return
        
        # حذف من المشرفين أو الملاك
        is_admin = storage.is_admin(target_uid)
        is_owner = storage.is_owner(target_uid)
        
        if is_owner:
            storage.remove_owner(target_uid)
            await u.message.reply_text(f"✅ تم حذف المالك `{target_uid}` من الإشراف", parse_mode="Markdown")
        elif is_admin:
            storage.remove_admin(target_uid)
            await u.message.reply_text(f"✅ تم حذف المشرف `{target_uid}` من الإشراف", parse_mode="Markdown")
        else:
            await u.message.reply_text(f"❌ الأيدي `{target_uid}` ليس مشرفاً أو مالكاً", parse_mode="Markdown")
        
        storage.log_cmd("حذف من الإشراف")
        return

    if text == "سبام متواصل":
        is_group_creator = False
        if cid < 0:
            try:
                chat_member = await c.bot.get_chat_member(cid, uid)
                is_group_creator = chat_member.status == 'creator'
            except:
                pass
        
        if not storage.is_main_owner(uid) and not is_group_creator:
            await u.message.reply_text("هذا الأمر للمالك الأساسي أو مالك المجموعة فقط")
            return
        
        spam_states[uid] = {"waiting": True, "chat_id": cid}
        await u.message.reply_text("وش اللي تبي يسوي له سبام ؟")
        storage.log_cmd("سبام متواصل")
        return

    if text == "قفل سبام":
        is_group_creator = False
        if cid < 0:
            try:
                chat_member = await c.bot.get_chat_member(cid, uid)
                is_group_creator = chat_member.status == 'creator'
            except:
                pass
        
        if not storage.is_main_owner(uid) and not is_group_creator:
            await u.message.reply_text("هذا الأمر للمالك الأساسي أو مالك المجموعة فقط")
            return
        
        stopped = False
        for spam_uid, state in list(spam_states.items()):
            if state.get("chat_id") == cid:
                if spam_uid in spam_running:
                    spam_running[spam_uid] = False
                if spam_uid in spam_tasks:
                    task = spam_tasks.pop(spam_uid, None)
                    if task and not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                del spam_states[spam_uid]
                stopped = True
        
        if stopped:
            await u.message.reply_text("تم إيقاف السبام المتواصل")
        else:
            await u.message.reply_text("لا يوجد سبام نشط حالياً")
        storage.log_cmd("قفل سبام")
        return

    if text == "صنف":
        if not storage.is_main_owner(uid):
            await u.message.reply_text("هذا الأمر للمالك الأساسي فقط")
            return

        current_device_type = storage.get_device_type(uid)
        keyboard = [
            [InlineKeyboardButton("جوال", callback_data="change_device_type_جوال")],
            [InlineKeyboardButton("خارجي", callback_data="change_device_type_خارجي")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        msg = f"اختر الصنف:\n\nالصنف الحالي: {current_device_type if current_device_type else 'لم يتم التحديد'}"
        await u.message.reply_text(msg, reply_markup=reply_markup)
        storage.log_cmd("صنف")
        return

    if text == "صنفي":
        if storage.is_banned(uid):
            await u.message.reply_text("انت محظور تواصل مع @iv511vi")
            return

        device_type = storage.get_device_type(uid)
        if not device_type:
            await u.message.reply_text("لم تختر صنفك بعد! اختر الآن:\n- جوال (موبايل)\n- خارجي (ديسك توب / لاب توب)")
            return

        emoji = "" if device_type == "جوال" else ""
        msg = f"{emoji} صنفك الحالي: {device_type}"
        await u.message.reply_text(msg)
        storage.log_cmd("صنفي")
        return

    if text == "جوائزي":
        await cmd_awards(u, c)
        storage.log_cmd("جوائزي")
        return

    if text == "تقدمي":
        level_info = storage.get_level_info(uid)
        level = level_info["level"]
        progress = level_info["progress"]
        requirement = storage.get_level_requirement(level)
        percentage = (progress / requirement) * 100

        next_level_cost = storage.get_level_requirement(level + 1)

        uid_str = str(uid)
        sections = ["ويكي", "مس", "كرر", "جمم", "صج", "نص", "طب", "قص", "فكك", "حر", "رق", "عكس", "جش", "شك", "جب"]

        # الحصول على متوسط السرعة من 13 قسم
        allowed_sections = ["ويكي", "مس", "جمم", "صج", "نص", "قص", "فكك", "حر", "رق", "عكس", "جش", "شك", "جب"]
        section_averages = []
        for section in allowed_sections:
            avg = storage.get_average_speed(uid, section)
            if avg:
                section_averages.append((section, avg))

        # بناء رسالة السرعة أو التقدم نحو المتوسط
        speed_section = ""

        if section_averages:
            # إذا كان عنده متوسط سرعة من أي قسم
            speed_msg = ""
            for section, avg in section_averages:
                speed_msg += f"- {section}: {avg:.1f} WPM\n"
            overall_avg = storage.get_overall_average_speed(uid)
            speed_section = f"\nمتوسط سرعتك من 12 قسم:\n{speed_msg}\nالمتوسط الكلي: {overall_avg:.1f} WPM"
        else:
            # إذا ما عنده متوسط، عرض التقدم نحو حساب المتوسط
            current_count = 0
            progress_repeat = 0

            if "average_speeds" in storage.data and uid_str in storage.data["average_speeds"]:
                if "combined" in storage.data["average_speeds"][uid_str]:
                    current_count = storage.data["average_speeds"][uid_str]["combined"].get("correct_count", 0)
                if "repeat" in storage.data["average_speeds"][uid_str]:
                    progress_repeat = storage.data["average_speeds"][uid_str]["repeat"].get("correct_count", 0)

            remaining = max(0, 100 - current_count)
            remaining_repeat = max(0, 100 - progress_repeat)

            speed_section = f"\nالتقدم:\n"
            if current_count > 0 or progress_repeat > 0:
                if current_count > 0:
                    speed_section += f"- المجموع الكلي: {current_count}/100 جملة ({remaining} باقي)\n"
                if progress_repeat > 0:
                    speed_section += f"- كرر: {progress_repeat}/100 جملة ({remaining_repeat} باقي)"
            else:
                speed_section += "- ابدأ بكتابة جمل لحساب متوسط سرعتك"

        await u.message.reply_text(
            f"لفلك الحالي\n\n"
            f"اللفل: {level}\n"
            f"التقدم: {progress}/{requirement} جملة\n\n"
            f"النسبة: {percentage:.0f}%"
            f"{speed_section}\n"
            f"إلى اللفل التالي: {next_level_cost} جملة"
        )
        storage.log_cmd("تقدمي")
        return

    if text == "المزالين":
        if storage.is_banned(uid):
            await u.message.reply_text("انت محظور تواصل مع @iv511vi")
            return

        removed_list = storage.data.get("removed_from_leaderboard", {})

        if not removed_list:
            await u.message.reply_text("لا يوجد مستخدمين محذوفين من الصدارة حالياً")
            return

        msg = "الأشخاص المزالين من الصدارة:\n\n"

        for idx, uid_str in enumerate(removed_list.keys(), 1):
            try:
                user_data = storage.data["users"].get(uid_str, {})
                username = user_data.get("username")
                first_name = user_data.get("first_name", "مستخدم")
                mention = f"@{username}" if username else first_name
                msg += f"{idx}. {mention} (ID: {uid_str})\n"
            except Exception as e:
                print(f"[ERROR] Error in removed users display: {e}")
                continue

        await u.message.reply_text(msg)
        storage.log_cmd("المزالين")
        return

    if text == "جولة":
        await cmd_show_round(u, c)
        storage.log_cmd("جولة")
        return

    if text == "منظم":
        await cmd_show_organizer(u, c)
        storage.log_cmd("منظم")
        return

    if text.startswith("فتح جولة") or text.startswith("فتح جوله"):
        await cmd_round(u, c)
        storage.log_cmd("فتح جولة")
        return

    if text in ["قفل جولة", "قفل جوله"]:
        await cmd_end_round(u, c)
        storage.log_cmd("قفل جولة")
        return

    if text == "باند":
        await cmd_ban(u, c)
        storage.log_cmd("باند")
        return

    if text.startswith("حظر "):
        if not (storage.is_main_owner(uid) or storage.is_owner(uid)):
            await u.message.reply_text("هذا الأمر للملاك والمالك الأساسي فقط")
            return

        try:
            target_str = text[4:].strip()

            # قبول اليوزرنيم أو الأيدي
            if target_str.startswith("@"):
                target_str = target_str[1:]  # إزالة @

            # محاولة التحويل إلى رقم (ID)
            try:
                target_uid = int(target_str)
            except ValueError:
                # إذا لم يكن رقماً، البحث عن اليوزرنيم
                target_uid = get_user_id_by_username(target_str)
                if target_uid is None:
                    await u.message.reply_text("لم أجد هذا المستخدم. استخدم: حظر [ID] أو @username")
                    return

            await cmd_ban_by_id(u, c, target_uid)
            storage.log_cmd("حظر")
        except Exception as e:
            await u.message.reply_text(f"حدث خطأ: {str(e)}")
        return

    if text == "الغاء باند":
        await cmd_unban(u, c)
        storage.log_cmd("الغاء باند")
        return

    if text.startswith("إزالة حظر ") or text.startswith("ازالة حظر "):
        if not (storage.is_main_owner(uid) or storage.is_owner(uid)):
            await u.message.reply_text("هذا الأمر للملاك والمالك الأساسي فقط")
            return

        try:
            # التعامل مع كلا الصيغتين (مع الهمزة وبدونها)
            if text.startswith("إزالة حظر "):
                target_str = text[9:].strip()
            else:  # ازالة حظر
                target_str = text[8:].strip()

            # قبول اليوزرنيم أو الأيدي
            if target_str.startswith("@"):
                target_str = target_str[1:]  # إزالة @

            # محاولة التحويل إلى رقم (ID)
            try:
                target_uid = int(target_str)
            except ValueError:
                # إذا لم يكن رقماً، البحث عن اليوزرنيم
                target_uid = get_user_id_by_username(target_str)
                if target_uid is None:
                    await u.message.reply_text("لم أجد هذا المستخدم. استخدم: إزالة حظر [ID] أو @username")
                    return

            await cmd_unban_by_id(u, c, target_uid)
            storage.log_cmd("إزالة حظر")
        except Exception as e:
            await u.message.reply_text(f"حدث خطأ: {str(e)}")
        return

    if text.startswith("إزالة ادمن ") or text.startswith("ازاله ادمن "):
        if not storage.is_main_owner(uid):
            await u.message.reply_text("هذا الأمر للمالك الأساسي فقط")
            return

        try:
            # التعامل مع كلا الصيغتين
            if text.startswith("إزالة ادمن "):
                target_str = text[11:].strip()
            else:  # ازاله ادمن
                target_str = text[10:].strip()

            # قبول اليوزرنيم أو الأيدي
            if target_str.startswith("@"):
                target_str = target_str[1:]  # إزالة @

            # محاولة التحويل إلى رقم (ID)
            try:
                target_uid = int(target_str)
            except ValueError:
                # إذا لم يكن رقماً، البحث عن اليوزرنيم
                target_uid = get_user_id_by_username(target_str)
                if target_uid is None:
                    await u.message.reply_text("لم أجد هذا المستخدم. استخدم: إزالة ادمن [ID] أو @username")
                    return

            # الحصول على بيانات المستخدم للرسالة
            target_user_data = storage.data.get("users", {}).get(str(target_uid), {})
            target_username = target_user_data.get("username")
            target_name = target_user_data.get("first_name", "غير معروف")

            storage.remove_admin(target_uid)
            await u.message.reply_text("تم طار من الإشراف")

            # رسالة الإشراف للمالك الأساسي
            supervisor_msg = f"تم إزالة ادمن:\n"
            if target_username:
                supervisor_msg += f"@{target_username}"
            else:
                supervisor_msg += f"{target_name} (ID: {target_uid})"

            try:
                await c.bot.send_message(chat_id=OWNER_ID, text=supervisor_msg)
            except Exception as e:
                print(f"[ERROR] Failed to send supervision message: {e}")

            storage.log_cmd("إزالة ادمن")
        except Exception as e:
            await u.message.reply_text(f"حدث خطأ: {str(e)}")
        return

    if text.startswith("إزالة مالك ") or text.startswith("ازالة مالك "):
        if not storage.is_main_owner(uid):
            await u.message.reply_text("هذا الأمر للمالك الأساسي فقط")
            return

        try:
            # التعامل مع كلا الصيغتين
            if text.startswith("إزالة مالك "):
                target_str = text[11:].strip()
            else:  # ازالة مالك
                target_str = text[10:].strip()

            # قبول اليوزرنيم أو الأيدي
            if target_str.startswith("@"):
                target_str = target_str[1:]  # إزالة @

            # محاولة التحويل إلى رقم (ID)
            try:
                target_uid = int(target_str)
            except ValueError:
                # إذا لم يكن رقماً، البحث عن اليوزرنيم
                target_uid = get_user_id_by_username(target_str)
                if target_uid is None:
                    await u.message.reply_text("لم أجد هذا المستخدم. استخدم: إزالة مالك [ID] أو @username")
                    return

            # الحصول على بيانات المستخدم للرسالة
            target_user_data = storage.data.get("users", {}).get(str(target_uid), {})
            target_username = target_user_data.get("username")
            target_name = target_user_data.get("first_name", "غير معروف")

            storage.remove_owner(target_uid)
            await u.message.reply_text("تم طار من الإشراف")

            # رسالة الإشراف للمالك الأساسي
            supervisor_msg = f"تم إزالة مالك:\n"
            if target_username:
                supervisor_msg += f"@{target_username}"
            else:
                supervisor_msg += f"{target_name} (ID: {target_uid})"

            try:
                await c.bot.send_message(chat_id=OWNER_ID, text=supervisor_msg)
            except Exception as e:
                print(f"[ERROR] Failed to send supervision message: {e}")

            storage.log_cmd("إزالة مالك")
        except Exception as e:
            await u.message.reply_text(f"حدث خطأ: {str(e)}")
        return

    if text.startswith("حذف ") and ("من صدارة" in text) and ("قسم" in text):
        if not (storage.is_main_owner(uid) or storage.is_owner(uid)):
            await u.message.reply_text("هذا الأمر للملاك والمالك الأساسي فقط")
            return

        try:
            pattern = r"حذف\s+(@?\S+)\s+من\s+صدارة\s+(الجوال|الخارجي)\s+قسم\s+(\S+)"
            match = re.match(pattern, text)
            
            if not match:
                await u.message.reply_text("صيغة خاطئة. استخدم:\nحذف @username من صدارة الجوال قسم كرر\nأو\nحذف @username من صدارة الخارجي قسم كرر")
                return
            
            target_str = match.group(1)
            device_type_text = match.group(2)
            section = match.group(3)
            
            device_type = "جوال" if device_type_text == "الجوال" else "خارجي"
            
            valid_sections = ["ويكي", "مس", "جمم", "صج", "شك", "جش", "قص", "نص", "طب", "كرر", "شرط", "فكك", "دبل", "تر", "عكس", "فر", "E", "رق", "حر", "جب"]
            if section not in valid_sections:
                await u.message.reply_text(f"القسم '{section}' غير موجود\nالأقسام المتاحة: {', '.join(valid_sections)}")
                return
            
            if target_str.startswith("@"):
                target_str = target_str[1:]
            
            try:
                target_uid = int(target_str)
            except ValueError:
                target_uid = get_user_id_by_username(target_str)
                if target_uid is None:
                    await u.message.reply_text("لم أجد هذا المستخدم")
                    return
            
            target_user_data = storage.data.get("users", {}).get(str(target_uid), {})
            target_username = target_user_data.get("username")
            target_name = target_user_data.get("first_name", "غير معروف")
            display_name = f"@{target_username}" if target_username else target_name
            
            if storage.remove_section_scores(target_uid, section, device_type):
                msg = f"تم حذف أرقام {display_name} من قسم {section} في صدارة {device_type}\n"
                msg += f"المستخدم لا يزال في الصدارة لكن بدون أرقام في هذا القسم"
                await u.message.reply_text(msg)
                storage.log_cmd(f"حذف من صدارة {device_type} قسم {section}")
            else:
                await u.message.reply_text(f"المستخدم ليس لديه أرقام في قسم {section} صدارة {device_type}")
            
        except Exception as e:
            await u.message.reply_text(f"حدث خطأ: {str(e)}")
        return

    if text.startswith("ازل "):
        if not (storage.is_main_owner(uid) or storage.is_owner(uid)):
            await u.message.reply_text("هذا الأمر للملاك والمالك الأساسي فقط")
            return

        try:
            target_str = text[4:].strip()

            # قبول اليوزرنيم أو الأيدي
            if target_str.startswith("@"):
                target_str = target_str[1:]  # إزالة @

            # محاولة التحويل إلى رقم (ID)
            try:
                target_uid = int(target_str)
            except ValueError:
                # إذا لم يكن رقماً، البحث عن اليوزرنيم
                target_uid = get_user_id_by_username(target_str)
                if target_uid is None:
                    await u.message.reply_text("لم أجد هذا المستخدم. استخدم: ازل [ID] أو @username")
                    return

            # الحصول على بيانات المستخدم
            target_user_data = storage.data.get("users", {}).get(str(target_uid), {})
            target_username = target_user_data.get("username")
            target_name = target_user_data.get("first_name", "غير معروف")

            # حذف من الصدارة
            removed_types = storage.remove_from_leaderboard(target_uid)

            if removed_types:
                display_name = f"@{target_username}" if target_username else target_name
                msg = f"تم حذف {display_name} من الصدارة:\n\n"
                msg += f"الأقسام المحذوفة: {', '.join(removed_types)}"
                await u.message.reply_text(msg)
                storage.log_cmd("ازل")
            else:
                await u.message.reply_text("المستخدم غير موجود في الصدارة")

        except Exception as e:
            await u.message.reply_text(f"حدث خطأ: {str(e)}")
        return

    if text.startswith("ارجع "):
        if not storage.is_main_owner(uid):
            await u.message.reply_text("هذا الأمر للمالك الأساسي فقط")
            return

        try:
            target_str = text[5:].strip()

            # قبول اليوزرنيم أو الأيدي
            if target_str.startswith("@"):
                target_str = target_str[1:]  # إزالة @

            # محاولة التحويل إلى رقم (ID)
            try:
                target_uid = int(target_str)
            except ValueError:
                # إذا لم يكن رقماً، البحث عن اليوزرنيم
                target_uid = get_user_id_by_username(target_str)
                if target_uid is None:
                    await u.message.reply_text("لم أجد هذا المستخدم. استخدم: ارجع [ID] أو @username")
                    return

            # الحصول على بيانات المستخدم
            target_user_data = storage.data.get("users", {}).get(str(target_uid), {})
            target_username = target_user_data.get("username")
            target_name = target_user_data.get("first_name", "غير معروف")

            # إرجاع المستخدم للصدارة
            if storage.restore_from_leaderboard(target_uid):
                display_name = f"@{target_username}" if target_username else target_name
                msg = f"تم إرجاع {display_name} للصدارة"
                await u.message.reply_text(msg)
                storage.log_cmd("ارجع")
            else:
                await u.message.reply_text("المستخدم غير محذوف من الصدارة")

        except Exception as e:
            await u.message.reply_text(f"حدث خطأ: {str(e)}")
        return

    if text == "مدد":
        cid = u.effective_chat.id

        # التحقق من وجود جولة مفتوحة في حالة انتظار التمديد
        round_data = storage.get_round(cid)

        if not round_data:
            await u.message.reply_text("لا توجد جولة انتهت قابلة للتمديد")
            return

        if not storage.get_round_extension_status(cid):
            await u.message.reply_text("الجولة الحالية لا تنتظر تمديد")
            return

        # التحقق من انتهاء الحد الزمني (دقيقتين)
        if storage.check_extension_timeout(cid):
            await u.message.reply_text("انتهت فرصة التمديد، يجب عليك فتح جولة جديدة")
            return

        storage.data["round_extension_awaiting"] = storage.data.get("round_extension_awaiting", {})
        storage.data["round_extension_awaiting"][str(cid)] = True
        storage.mark_dirty()

        await u.message.reply_text("كم تبي تمدد؟")
        return

    # معالجة التمديد برقم مباشر
    if u.effective_chat.id in [int(k) for k in storage.data.get("round_extension_awaiting", {}).keys() if storage.data.get("round_extension_awaiting", {}).get(k)]:
        cid = u.effective_chat.id

        # التحقق من انتهاء الحد الزمني (دقيقتين)
        if storage.check_extension_timeout(cid):
            await u.message.reply_text("انتهت فرصة التمديد، يجب عليك فتح جولة جديدة")
            storage.data["round_extension_awaiting"].pop(str(cid), None)
            storage.mark_dirty()
            return

        # محاولة تحويل النص إلى رقم
        try:
            extension_count = arabic_to_num(text)
            if extension_count is None:
                extension_count = int(text)
        except (ValueError, TypeError):
            await u.message.reply_text("أدخل رقم صحيح")
            return

        if extension_count < 1:
            await u.message.reply_text("أدخل رقم موجب")
            return

        round_data = storage.get_round(cid)
        if not round_data:
            await u.message.reply_text("انتهت الجولة")
            storage.data["round_extension_awaiting"].pop(str(cid), None)
            storage.mark_dirty()
            return

        # الحصول على الجولة الحالية
        round_data = storage.get_round(cid)
        current_target = round_data.get("target", 1)
        new_target = current_target + extension_count

        # تمديد الجولة مباشرة بدون إغلاق
        if storage.extend_round(cid, new_target):
            msg = f"تم تمديد الجولة\n\nالنتيجة الجديدة: {new_target}"
            msg += f"\n\nالمتقدمين الحاليين:\n"
            wins_list = round_data.get('wins', {})
            sorted_wins = sorted(wins_list.items(), key=lambda x: x[1], reverse=True)
            for i, (user_id, wins) in enumerate(sorted_wins[:3], 1):
                user_data = storage.data["users"].get(str(user_id), {})
                user_name = user_data.get("first_name", "مستخدم")
                user_username = user_data.get("username")
                mention = f"@{user_username}" if user_username else user_name
                msg += f"{i}. {mention}: {wins}/{new_target}\n"
            await u.message.reply_text(msg)
        else:
            await u.message.reply_text("فشل التمديد")

        storage.data["round_extension_awaiting"].pop(str(cid), None)
        storage.mark_dirty()
        storage.save()
        return

    if text.startswith("شطب "):
        is_main_owner = storage.is_main_owner(uid)
        is_owner = storage.is_owner(uid)

        # التحقق من وجود جولة مفتوحة
        cid = u.effective_chat.id
        existing_round = storage.get_round(cid)
        if not existing_round:
            await u.message.reply_text("لا توجد جولة مفتوحة حالياً")
            return

        starter_uid = existing_round.get("starter_uid")
        is_starter = starter_uid and starter_uid == uid

        if not (is_main_owner or is_owner or is_starter):
            await u.message.reply_text("هذا الأمر للملاك والمالك الأساسي والمفتاح فقط")
            return

        # إذا كان المفتاح، تحقق من حد الاستخدام
        if is_starter and not (is_main_owner or is_owner):
            action_count = storage.get_starter_action_count(cid, uid)
            if action_count >= 2:
                await u.message.reply_text("وين يبوي وقف جالس توزع وتشطب على كيفك؟")
                return
            storage.add_starter_action(cid, uid)

        try:
            # تحليل الأمر: شطب [رقم] من [الأيدي أو اليوزرنيم]
            cmd_parts = text[4:].strip()  # إزالة "شطب "

            if " من " not in cmd_parts:
                await u.message.reply_text("صيغة الأمر غير صحيحة.\nاستخدم: شطب [رقم] من [ID أو @username]\nمثال: شطب 3 من @username")
                return

            # فصل الرقم عن المستخدم
            parts = cmd_parts.split(" من ", 1)
            points_str = parts[0].strip()
            target_str = parts[1].strip()

            # تحويل الرقم
            points = arabic_to_num(points_str)
            if points is None or points < 1:
                await u.message.reply_text("الرقم المدخل غير صحيح. أدخل رقماً من 1 إلى 100")
                return

            # البحث عن المستخدم
            if target_str.startswith("@"):
                target_str = target_str[1:]  # إزالة @

            # محاولة التحويل إلى رقم (ID)
            try:
                target_uid = int(target_str)
            except ValueError:
                # إذا لم يكن رقماً، البحث عن اليوزرنيم
                target_uid = get_user_id_by_username(target_str)
                if target_uid is None:
                    await u.message.reply_text("لم أجد هذا المستخدم. استخدم: شطب [رقم] من [ID] أو @username")
                    return

            # تقليل النقاط
            if storage.reduce_round_points(cid, target_uid, points):
                # الحصول على بيانات المستخدم
                target_user_data = storage.data.get("users", {}).get(str(target_uid), {})
                target_username = target_user_data.get("username")
                target_name = target_user_data.get("first_name", "غير معروف")
                display_name = f"@{target_username}" if target_username else target_name

                # الحصول على النقاط الحالية والهدف
                current_round = storage.get_round(cid)
                current_points = current_round.get("wins", {}).get(str(target_uid), 0)
                target = current_round.get('target', 0)

                msg = f"تم خصم {points} نقطة من {display_name}\n"
                msg += f"النقاط الحالية: {current_points}/{target}"
                await u.message.reply_text(msg)

                # فحص الفوز بعد خصم النقاط
                if current_points >= target:
                    await u.message.reply_text(f"مبروك يا {display_name} - أنت الفائز في الجولة!")
                    celebration_message = f"حيك يا {display_name}، {display_name} هو الفائز بالجولة\nمبروك!"
                    for _ in range(5):
                        await u.message.reply_text(celebration_message)
                        await asyncio.sleep(0.1)
                    storage.set_round_extension_status(cid, True)
                    await u.message.reply_text("الجوله ذي انتهت لكن إذا ودك تكمل على نفس النتيجة اكتب: مدد \n\nاذا ما تبي اكتب : قفل جوله")

                storage.log_cmd("شطب")
            else:
                await u.message.reply_text("المستخدم ليس لديه نقاط في هذه الجولة")

        except Exception as e:
            await u.message.reply_text(f"حدث خطأ: {str(e)}")
        return

    if text == "انسحب":
        # البحث عن لعبة matchmaking نشطة
        for key, session in list(storage.data["sessions"].items()):
            if session.get("type", "").startswith("match_"):
                game_id = session.get("type", "").replace("match_", "")
                game = storage.get_matchmaking_game(game_id)

                # التحقق من أن اللعبة لم تنته بعد
                if game and game.get("status") != "finished" and (game["player1"]["uid"] == uid or game["player2"]["uid"] == uid):
                    # تحديد اللاعب والخصم
                    is_player1 = game["player1"]["uid"] == uid
                    opponent_uid = game["player2"]["uid"] if is_player1 else game["player1"]["uid"]
                    current_player = game["player1"] if is_player1 else game["player2"]
                    current_player_name = current_player.get("first_name", "مستخدم")
                    current_player_username = current_player.get("username")
                    current_player_display = f"@{current_player_username}" if current_player_username else current_player_name

                    # رسالة للاعب الذي انسحب
                    await u.message.reply_text("أنت انسحبت من اللعبة - انتهت الجوله")

                    # رسالة للخصم - يخبره أن الخصم انسحب
                    if opponent_uid != -1:
                        try:
                            surrender_msg = "خصمك انسحب انت الفايز حيك يا الشريف\n\nاكتب سجلي وتطلع لك نتايجك"
                            await c.bot.send_message(opponent_uid, surrender_msg)
                        except:
                            pass

                    # تسجيل الانسحاب في البيانات (للإحصائيات)
                    game["surrender_by"] = uid
                    game["status"] = "finished"
                    storage.data["matchmaking_games"][game_id] = game

                    # حذف جميع الجلسات
                    storage.del_session(cid, session.get("type"))
                    if opponent_uid != -1:
                        storage.del_session(opponent_uid, session.get("type"))

                    storage.save()
                    return

        return


    if text == "أون لاين" or text == "اون لاين":
        # يعمل فقط في الخاص
        if u.effective_chat.type != "private":
            await u.message.reply_text("هذا الأمر في الخاص فقط")
            return

        uid = u.effective_user.id
        user_data = storage.data.get("users", {}).get(str(uid), {})

        # الرسالة الأساسية مع نقاط متحركة
        base_msg = "جاري البحث عن خصم"
        info_msg = "\n\nحاجات مهمة:\n- شطب: اذا ما عجبتك الجملة لا انت ولا خصمك\n- انسحب: اذا ما ودك تكمل\n\nاكتب: الغاء عشان تطفي البحث"

        # إرسال الرسالة الأولية
        msg_with_dots = await u.message.reply_text(f"{base_msg}." + info_msg)

        # محاولة البحث (30 ثانية مع مطابقة ذكية)
        # أول 20 ثانية: ±20 WPM
        # آخر 10 ثواني: أي خصم
        if not storage.add_to_matchmaking_queue(uid, user_data):
            await u.message.reply_text("أنت بالفعل في قائمة الانتظار")
            return

        opponent = None
        search_start_time = time.time()
        dots_update_time = time.time()
        dot_count = 1
        user_cancelled = False

        # البحث لمدة 30 ثانية مع تأثير النقاط المتحركة
        while time.time() - search_start_time < 30:
            opponent = storage.find_match(uid, search_start_time)
            if opponent:
                break

            # التحقق إذا كان المستخدم قد ألغى من قائمة الانتظار
            matchmaking_queue = storage.data.get("matchmaking_queue", [])
            if not any(p.get("uid") == uid for p in matchmaking_queue):
                user_cancelled = True
                break

            # تحديث النقاط كل ثانية تقريباً
            current_time = time.time()
            if current_time - dots_update_time >= 1:
                dot_count += 1
                if dot_count > 3:
                    dot_count = 1

                dots = "." * dot_count
                try:
                    await msg_with_dots.edit_text(f"{base_msg}{dots}" + info_msg)
                except:
                    pass

                dots_update_time = current_time

            await asyncio.sleep(0.5)

        # إذا لم نجد خصم حقيقي وكان بسبب انتهاء الوقت (ليس بسبب إلغاء المستخدم)
        if not opponent:
            storage.remove_from_matchmaking_queue(uid)
            if not user_cancelled:
                await u.message.reply_text("لم نجد خصم متاح الآن. جرب لاحقاً!")
            storage.log_cmd("أون لاين")
            return

        # وجدنا خصم حقيقي
        opponent_name = opponent.get("first_name", "مستخدم")
        await u.message.reply_text(f"تم لقينا لك خصم: {opponent_name}")

        try:
            await c.bot.send_message(opponent['uid'], f"تم لقينا لك خصم: {user_data.get('first_name', 'مستخدم')}")
        except:
            pass

        # حذف كلا اللاعبين من قائمة الانتظار فوراً (منع استدعاءات مزدوجة)
        storage.remove_from_matchmaking_queue(uid)
        storage.remove_from_matchmaking_queue(opponent['uid'])

        # إنشاء لعبة - استخدام UIDs مرتبة لضمان game_id موحد (بدون timestamp لضمان game_id واحد فقط)
        sorted_uids = sorted([uid, opponent['uid']])
        game_id = f"{sorted_uids[0]}_{sorted_uids[1]}"
        opponent_data = {"username": opponent.get("username"), "first_name": opponent.get("first_name")}

        # التحقق من أن اللعبة لم تُنشأ بالفعل (في حالة وجود race condition)
        existing_game = storage.get_matchmaking_game(game_id)
        if not existing_game:
            # تحديد من هو player1 ومن هو player2 بناءً على الـ sorted UIDs
            if sorted_uids[0] == uid:
                storage.create_matchmaking_game(game_id, uid, opponent['uid'], user_data, opponent_data, encounter_count=1)
            else:
                storage.create_matchmaking_game(game_id, opponent['uid'], uid, opponent_data, user_data, encounter_count=1)
        else:
            # إذا التقى نفس الخصمين مرة أخرى، زيادة العداد وإعادة تعيين النقاط (جولة جديدة)
            if existing_game.get("status") == "finished":
                existing_game["encounter_count"] = existing_game.get("encounter_count", 1) + 1
                existing_game["player1"]["wins"] = 0
                existing_game["player2"]["wins"] = 0
                existing_game["status"] = "active"
                existing_game["current_round"] = 0
                existing_game["skip_request"] = None
                storage.data["matchmaking_games"][game_id] = existing_game
                storage.save(force=True)

        # بدء اللعبة (إرسال جملة واحدة فقط)
        asyncio.create_task(send_next_match_sentence(c, uid, opponent['uid'], game_id, exclude_section=None))

        storage.log_cmd("أون لاين")
        return

    if text == "الغاء":
        # إلغاء البحث عن خصم بدون رسالة
        uid = u.effective_user.id

        # البحث في قائمة الانتظار
        matchmaking_queue = storage.data.get("matchmaking_queue", [])

        for i, player in enumerate(matchmaking_queue):
            if player.get("uid") == uid:
                matchmaking_queue.pop(i)
                storage.data["matchmaking_queue"] = matchmaking_queue
                storage.save()
                break

        storage.log_cmd("الغاء")
        return

    if text == "سجلي":
        uid = u.effective_user.id
        try:
            stats = storage.get_online_stats(uid)
            user_data = storage.data.get("users", {}).get(str(uid), {})
            user_name = user_data.get("first_name", "مستخدم")

            msg = "إحصائياتك في أون لاين:\n\n"
            msg += f"الفوز: {stats['wins']}\n"
            msg += f"الخسارة: {stats['losses']}\n"
            msg += f"الانسحاب: {stats['surrenders']}\n"

            total = stats['wins'] + stats['losses'] + stats['surrenders']
            if total > 0:
                rate = (stats['wins'] / total) * 100
                msg += f"\nمعدل الفوز: {rate:.1f}%"
                msg += f"\nإجمالي المباريات: {total}"
            else:
                msg += "\nلم تلعب أي مباريات بعد"

            await u.message.reply_text(msg)
        except Exception as e:
            await u.message.reply_text("خطأ في جلب الإحصائيات")
        storage.log_cmd("سجلي")
        return

    if text == "توب":
        # عرض نفس رسالة الصدارة (اختيار جوال/خارجي)
        await cmd_leaderboard(u, c)
        storage.log_cmd("توب")
        return

    if text in ["أيدي صدارة الجوال", "ايدي صدارة الجوال"]:
        # عرض أيدي الصدارة لصدارة الجوال
        uid = u.effective_user.id

        types = ["كرر", "ويكي", "مس", "شك", "جب", "جش", "حر"]
        sections = []

        for typ in types:
            lb = storage.get_leaderboard(typ, device_type="جوال")
            if lb:
                s = f"<b>{typ}</b>\n"
                for i, (uid_str, username, first_name, wpm) in enumerate(lb[:5], 1):
                    display = f"@{username}" if username else first_name
                    s += f"{i}. {display} (ID: {uid_str}): {wpm:.2f} WPM\n"
                sections.append(s)

        if sections:
            msg = "<b>أيدي صدارة الجوال - الخمسة الأوائل من كل قسم</b>\n\n" + "\n".join(sections)
            await u.message.reply_text(msg, parse_mode="HTML")
        else:
            await u.message.reply_text("لا توجد نتائج بعد")

        storage.log_cmd("أيدي صدارة الجوال")
        return

    if text in ["أيدي صدارة خارجي", "ايدي صدارة خارجي"]:
        # عرض أيدي الصدارة لصدارة خارجي
        uid = u.effective_user.id

        types = ["كرر", "ويكي", "مس", "شك", "جب", "جش", "حر"]
        sections = []

        for typ in types:
            lb = storage.get_leaderboard(typ, device_type="خارجي")
            if lb:
                s = f"<b>{typ}</b>\n"
                for i, (uid_str, username, first_name, wpm) in enumerate(lb[:5], 1):
                    display = f"@{username}" if username else first_name
                    s += f"{i}. {display} (ID: {uid_str}): {wpm:.2f} WPM\n"
                sections.append(s)

        if sections:
            msg = "<b>أيدي صدارة خارجي - الخمسة الأوائل من كل قسم</b>\n\n" + "\n".join(sections)
            await u.message.reply_text(msg, parse_mode="HTML")
        else:
            await u.message.reply_text("لا توجد نتائج بعد")

        storage.log_cmd("أيدي صدارة خارجي")
        return

    if text in ["أيدي الصدارة", "ايدي الصدارة"]:
        # عرض نفس رسالة الصدارة (اختيار جوال/خارجي) ثم إرسال ايدي الصدارة
        uid = u.effective_user.id

        # إذا كان لديه device_type، عرض الصدارة مباشرة
        if storage.has_device_type(uid):
            user_device_type = storage.get_device_type(uid)

            types = ["كرر", "ويكي", "مس", "شك", "جب", "جش", "حر"]
            sections = []

            for typ in types:
                lb = storage.get_leaderboard(typ, device_type=user_device_type)
                if lb:
                    s = f"<b>{typ}</b>\n"
                    for i, (uid_str, username, first_name, wpm) in enumerate(lb[:5], 1):
                        display = f"@{username}" if username else first_name
                        s += f"{i}. {display} (ID: {uid_str}): {wpm:.2f} WPM\n"
                    sections.append(s)

            if sections:
                msg = "<b>ايدي الصدارة - الخمسة الأوائل من كل قسم</b>\n\n" + "\n".join(sections)
                await u.message.reply_text(msg, parse_mode="HTML")
            else:
                await u.message.reply_text("لا توجد نتائج بعد")
        else:
            # إذا كان جديد بدون device_type، يطلب الاختيار
            leaderboard_state[uid] = "ايدي_صدارة"
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("جوال", callback_data="device_type_جوال_leaderboard"),
                    InlineKeyboardButton("خارجي", callback_data="device_type_خارجي_leaderboard")
                ]
            ])
            msg = (
                "ارحب اول شي انت جوال ولا خارجي اختر من الازرار\n\n"
                "انتبه اذا اخترت انت جوال ولا خارجي ترا بيثبت ولا يمديك تغير\n\n"
                "في صدارة الجوال لو نلقى خارجي او العكس راح يتبند من البوت تماما\n\n"
                "موفق"
            )
            await u.message.reply_text(msg, reply_markup=keyboard)

        storage.log_cmd("أيدي الصدارة")
        return

    if text == "ريست صدارة":
        if not (storage.is_main_owner(uid) or storage.is_owner(uid)):
            await u.message.reply_text("هذا الأمر للملاك والمالك الأساسي فقط")
            return

        week = storage.reset_leaderboard()
        await u.message.reply_text(f"تم ريست الصدارة!\n\nتم توزيع الجوائز على أول 3 في كل قسم\nالأسبوع: {week}")
        storage.log_cmd("ريست صدارة")
        return

    if text == "احصاء":
        await cmd_stats(u, c)
        storage.log_cmd("احصاء")
        return

    if text == "تفاعل البوت":
        if not (storage.is_main_owner(uid) or storage.is_owner(uid)):
            await u.message.reply_text("هذا الأمر للملاك والمالك الأساسي فقط")
            return

        from datetime import timedelta
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        today_commands = storage.data.get("stats", {}).get(today, {})
        yesterday_commands = storage.data.get("stats", {}).get(yesterday, {})

        today_count = sum(today_commands.values()) if today_commands else 0
        yesterday_count = sum(yesterday_commands.values()) if yesterday_commands else 0

        msg = f"تفاعل البوت:\n\n"
        msg += f"اليوم ({today}): {today_count} أمر\n"
        msg += f"أمس ({yesterday}): {yesterday_count} أمر"

        await u.message.reply_text(msg)
        storage.log_cmd("تفاعل البوت")
        return

    if text == "المستخدمين":
        total_users = len(storage.data["users"])
        await u.message.reply_text(f"عدد المستخدمين: {total_users}")
        storage.log_cmd("المستخدمين")
        return

    if text == "عرض الكل":
        await cmd_show_all_users(u, c)
        storage.log_cmd("عرض الكل")
        return

    if text == "المحظورين":
        await cmd_banned_list(u, c)
        storage.log_cmd("المحظورين")
        return

    if text == "ايديه":
        if not has_permission(uid, "admin"):
            await u.message.reply_text("هذا الأمر للمشرفين فقط")
            return

        if u.message.reply_to_message:
            target_uid = u.message.reply_to_message.from_user.id
            await u.message.reply_text(str(target_uid))
        else:
            await u.message.reply_text("رد على رسالة المستخدم لعرض ID")
        return

    if text == "الإشراف":
        await cmd_supervision(u, c)
        storage.log_cmd("الإشراف")
        return

    if text in ["إدارة", "اداره", "ادارة"]:
        await cmd_admin_menu(u, c)
        storage.log_cmd("إدارة")
        return

    if text in ["عرض", "مقالات", "بوت"]:
        await show_bot_sections(u, c, message_thread_id=message_thread_id)
        storage.log_cmd(text)
        return

    if text in ["عرض جميع الاوامر", "جميع الاوامر", "الاوامر كاملة"]:
        await show_all_bot_commands(u, c)
        storage.log_cmd("عرض جميع الاوامر")
        return

    # قسم خصص - متاح للجميع في الخاص والقروبات
    if text == "خصص":
        # التحقق من عدد التخصيصات الموجودة (حد أقصى 5 تخصيصات)
        uid_str = str(uid)
        customizations = storage.customizations_data.get("customizations", {}).get(uid_str, {})
        if len(customizations) >= 5:
            shortcuts = ", ".join(customizations.keys())
            await u.message.reply_text(f"أنت وصلت للحد الأقصى من التخصيصات (خمسة تخصيصات)\nالتخصيصات الموجودة: {shortcuts}")
            return

        # بدء عملية التخصيص
        customization_state[uid] = {
            "stage": "waiting_type",
            "data": {}
        }

        # عرض أزرار اختيار النوع
        keyboard = [
            [InlineKeyboardButton("كلمات عادية", callback_data="cust_type_normal")],
            [InlineKeyboardButton("تكرار", callback_data="cust_type_repeat")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        msg = ("ارحب يا الشيخ\n\n"
               "فكرة هذا القسم انك تحط كلمات من عندك وتلعب فيها والبوت يحسب سرعتك في التكرار والكلمات العادية\n\n"
               "نفس نظام كرر وجب لكن انت تختار الكلمات اللي تعجبك\n\n"
               "الحين اختار وش تبي قسم.؟")
        await u.message.reply_text(msg, reply_markup=reply_markup)
        storage.log_cmd("خصص")
        return

    # أمر عرض التخصيصات
    if text == "المحفوظ":
        uid_str = str(uid)
        customizations = storage.customizations_data.get("customizations", {}).get(uid_str, {})
        if customizations:
            msg = "ذي هي التخصيصات حقتك\n\n"
            for shortcut, data in customizations.items():
                words_count = len(data["words"].split())
                cust_type = "تكرار" if data.get("type") == "repeat" else "عادية"
                msg += f"{shortcut}  -    {cust_type} ({words_count} كلمات)\n"
            msg += f"\n\nاكتب حذف تخصيص مع الاختصار وينحذف التخصيص"
            await u.message.reply_text(msg)
        else:
            await u.message.reply_text("ما عندك تخصيصات محفوظة\nاكتب 'خصص' وسوي")
        return

    # أمر تعديل التخصيص الموجود
    if text.startswith("عدل تخصيص "):
        shortcut = text.replace("عدل تخصيص ", "").strip()
        uid_str = str(uid)
        customizations = storage.customizations_data.get("customizations", {}).get(uid_str, {})
        if shortcut in customizations:
            customization_state[uid] = {
                "stage": "waiting_words",
                "data": {"edit_shortcut": shortcut}
            }
            await u.message.reply_text(f"تعديل التخصيص '{shortcut}'\n\nأرسل الكلمات الجديدة:")
        else:
            await u.message.reply_text(f"التخصيص '{shortcut}' غير موجود")
        return

    # بديل بصياغة أطول: 'تعديل تخصيص <اختصار>' -> عرض الكلمات ثم انتظار التعديل
    if text.startswith("تعديل تخصيص "):
        shortcut = text.replace("تعديل تخصيص ", "").strip()
        uid_str = str(uid)
        customizations = storage.customizations_data.get("customizations", {}).get(uid_str, {})
        if shortcut in customizations:
            words = customizations[shortcut].get("words", "")
            # أرسل الكلمات الحالية ثم رسالة إرشادية
            await u.message.reply_text(words)
            await u.message.reply_text("(ذي الكلمات عدل عليها وارسل لي التعديل)")
            customization_state[uid] = {
                "stage": "waiting_words",
                "data": {"edit_shortcut": shortcut}
            }
        else:
            await u.message.reply_text(f"التخصيص '{shortcut}' غير موجود")
        return

    # أمر إظهار كلمات التخصيص: 'كلمات تخصيص <اختصار>' -> يعرض الكلمات المحفوظة
    if text.startswith("كلمات تخصيص "):
        shortcut = text.replace("كلمات تخصيص ", "").strip()
        uid_str = str(uid)
        customizations = storage.customizations_data.get("customizations", {}).get(uid_str, {})
        if shortcut in customizations:
            words = customizations[shortcut].get("words", "")
            await u.message.reply_text(f"كلمات التخصيص '{shortcut}':\n\n{words}")
        else:
            await u.message.reply_text(f"التخصيص '{shortcut}' غير موجود")
        return

    # حذف تخصيص
    if text.startswith("حذف تخصيص "):
        shortcut = text.replace("حذف تخصيص ", "").strip()
        uid_str = str(uid)
        customizations = storage.customizations_data.get("customizations", {}).get(uid_str, {})
        if shortcut in customizations:
            del storage.customizations_data["customizations"][uid_str][shortcut]
            storage.save_customizations()
            storage.mark_dirty()
            storage.save(force=True)
            await u.message.reply_text(f"تم حذف التخصيص '{shortcut}'")
        else:
            await u.message.reply_text(f"التخصيص '{shortcut}' غير موجود")
        return

    # معالج "خصص" مع تحديد عدد الكلمات (خصص 15)
    if text.startswith("خصص "):
        try:
            num_str = text.replace("خصص ", "").strip()
            num = int(num_str)
            if 1 <= num <= 60:
                storage.log_cmd(f"خصص {num}")
                storage.save_preference(uid, "خصص", num)
                storage.disable_section(uid, "خصص")
                await u.message.reply_text(f" تم تحديد التخصيص لـ {num} {'كلمة' if num == 1 else 'كلمات'}")
                return
            else:
                await u.message.reply_text("الرجاء إدخال رقم بين 1 و 60")
                return
        except ValueError:
            pass

    # تشغيل الاختصارات المحفوظة
    uid_str = str(uid)
    customizations = storage.customizations_data.get("customizations", {}).get(uid_str, {})
    if text in customizations:
        async with chat_locks[cid]:
            current_time = time.time()
            if current_time - sent_message_tracker[cid].get("خصص", 0) < 0.5:
                return

            cust = customizations[text]
            words_list = cust["words"].split()
            cust_type = cust.get("type", "normal")

            # احصل على عدد الكلمات المحفوظ (إن وجد)
            pref_count = storage.get_preference(uid, "خصص")

            # إذا كان النوع "عادية" - عشوئ الكلمات مع تكرار بدون تجاوز 3 مرات لكل كلمة
            if cust_type == "normal":
                max_possible = len(words_list)

                # استخدم التفضيل المحفوظ أو اختر طول عشوائي
                if pref_count and 1 <= pref_count:
                    target_length = pref_count
                else:
                    min_length = min(7, max_possible)
                    max_length = min(20, max_possible)
                    target_length = random.randint(min_length, max_length) if max_possible >= 7 else max_possible

                # بناء الجملة بتكرار الكلمات إذا لزم الأمر
                result = []
                word_count = {}
                max_repetitions = 3
                max_possible_with_repeats = max_possible * max_repetitions

                # حد أقصى آمن: لا تطلب أكثر من الحد الأقصى الممكن
                target_length = min(target_length, max_possible_with_repeats)

                if target_length <= max_possible:
                    # إذا كان الطول المطلوب <= الكلمات المتاحة - اختر عشوائياً بدون تكرار
                    shuffled_words = words_list.copy()
                    random.shuffle(shuffled_words)
                    result = shuffled_words[:target_length]
                else:
                    # إذا كان الطول المطلوب > الكلمات المتاحة - كرر الكلمات عشوائياً
                    attempts = 0
                    max_attempts = 100

                    while len(result) < target_length and attempts < max_attempts:
                        shuffled_words = words_list.copy()
                        random.shuffle(shuffled_words)

                        for word in shuffled_words:
                            if len(result) >= target_length:
                                break
                            # تحقق من عدم تكرار الكلمة أكثر من 3 مرات
                            if word_count.get(word, 0) < max_repetitions:
                                result.append(word)
                                word_count[word] = word_count.get(word, 0) + 1

                        attempts += 1

                    # إذا لم نستطع إكمال العدد - خذ ما هو متاح
                    if len(result) < target_length:
                        # كرر كل الكلمات مرة واحدة إضافية بشكل عشوائي
                        for _ in range(target_length - len(result)):
                            word = random.choice(words_list)
                            if word_count.get(word, 0) < max_repetitions:
                                result.append(word)
                                word_count[word] = word_count.get(word, 0) + 1

                sent = " ".join(result)
            else:
                # نوع "تكرار" - استخدام نفس الدالة المستخدمة في كرر العادي
                pattern_list = gen_pattern_from_custom_words(words_list)
                sent = " ".join(pattern_list)

            # للنوع "repeat" - بدون فواصل (مثل كرر تماماً) - لكن يحفظ كـ "خصص" لعدم الظهور في الصدارة
            if cust_type == "repeat":
                storage.del_session(cid, "خصص")
                storage.save_session(uid, cid, "خصص", sent, time.time(), sent=True)
                await u.message.reply_text(sent)
                asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "كرر"))
            else:
                # للنوع "normal" - مع فواصل
                storage.del_session(cid, "خصص")
                storage.save_session(uid, cid, "خصص", sent, time.time(), sent=True)
                display = format_display(sent)
                await u.message.reply_text(display)
                asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "خصص"))
            sent_message_tracker[cid]["خصص"] = current_time
        return

    # معالجة "ريست" مع أو بدون قسم معين
    if text == "ريست" or text.startswith("ريست "):
        all_sections = ["جمم", "ويكي", "مس", "اص", "صج", "شك", "جش", "قص", "نص", "طب", "شرط", "فكك", "دبل", "تر", "عكس", "فر", "E", "رق", "حر", "جب", "كرر", "خصص"]

        # التحقق من وجود قسم محدد
        parts = text.split()
        if len(parts) == 2:
            # ريست قسم معين (مثل: ريست جمم)
            section = parts[1]
            if section not in all_sections:
                await u.message.reply_text(f"القسم '{section}' غير موجود\nالأقسام المتاحة: {', '.join(all_sections)}")
                return
            # تفعيل قسم واحد فقط
            storage.enable_section(uid, section)
            storage.clear_preference(uid, section)
            await u.message.reply_text(f"تم تفعيل قسم '{section}' في الصدارة وإعادة تعيين تفضيلاته")
            storage.log_cmd(f"ريست {section}")
            return
        elif len(parts) == 1:
            # ريست عام - تفعيل جميع الأقسام
            for section in all_sections:
                storage.clear_preference(uid, section)
            storage.clear_patterns(uid)
            storage.save_preference(uid, "كرر_recent_words", [])
            storage.enable_all_sections(uid)
            await u.message.reply_text("تم إعادة تعيين تفضيلات جميع الأقسام بنجاح\nالآن سيتم إرسال جميع الجمل بشكلها الطبيعي العشوائي\nتم تفعيل جميع الأقسام في الصدارة")
            storage.log_cmd("ريست")
            return

    if text == "حذف ادمن":
        if not storage.is_main_owner(uid):
            await u.message.reply_text("هذا الأمر للمالك الأساسي فقط")
            return

        removed_admins = storage.clear_all_admins()
        if removed_admins:
            await u.message.reply_text(f"تم حذف جميع الإداريين ({len(removed_admins)})")

            # رسالة الإشراف
            supervisor_msg = f"تم حذف جميع الإداريين:\n\n"
            for admin_id in removed_admins:
                admin_data = storage.data.get("users", {}).get(admin_id, {})
                admin_username = admin_data.get("username")
                admin_name = admin_data.get("first_name", "ادمن")
                if admin_username:
                    supervisor_msg += f"- @{admin_username}\n"
                else:
                    supervisor_msg += f"- {admin_name} (ID: {admin_id})\n"

            try:
                await c.bot.send_message(chat_id=OWNER_ID, text=supervisor_msg)
            except Exception as e:
                print(f"[ERROR] Failed to send supervision message: {e}")

            storage.log_cmd("حذف ادمن")
        else:
            await u.message.reply_text("لا يوجد إداريين حالياً")
        return

    if text in ["حذف المالك", "حذف مالك", "حذف ملاك"]:
        if not storage.is_main_owner(uid):
            await u.message.reply_text("هذا الأمر للمالك الأساسي فقط")
            return

        removed_owners = storage.clear_all_owners()
        if removed_owners:
            await u.message.reply_text(f"تم حذف جميع الملاك ({len(removed_owners)})")

            # رسالة الإشراف
            supervisor_msg = f"تم حذف جميع الملاك:\n\n"
            for owner_id in removed_owners:
                owner_data = storage.data.get("users", {}).get(owner_id, {})
                owner_username = owner_data.get("username")
                owner_name = owner_data.get("first_name", "مالك")
                if owner_username:
                    supervisor_msg += f"- @{owner_username}\n"
                else:
                    supervisor_msg += f"- {owner_name} (ID: {owner_id})\n"

            try:
                await c.bot.send_message(chat_id=OWNER_ID, text=supervisor_msg)
            except Exception as e:
                print(f"[ERROR] Failed to send supervision message: {e}")

            storage.log_cmd("حذف ملاك")
        else:
            await u.message.reply_text("لا يوجد ملاك حالياً")
        return

    if text.startswith("ريست "):
        section = text[5:].strip()
        if section in ["جمم", "ويكي", "مس", "اص", "صج", "شك", "جش", "قص", "نص", "طب", "شرط", "فكك", "دبل", "تر", "عكس", "فر", "E", "رق", "حر", "جب", "كرر"]:
            if section == "رق":
                storage.save_preference(uid, "رق_عدد", None)
                await u.message.reply_text(f"تم إعادة تعيين تفضيلات القسم ({section}) بنجاح\nالآن سيتم إرسال الأرقام بشكلها الطبيعي العشوائي")
            elif section == "كرر":
                storage.clear_preference(uid, section)
                storage.save_preference(uid, "كرر_recent_words", [])
                storage.clear_patterns(uid)
                await u.message.reply_text(f"تم إعادة تعيين تفضيلات القسم ({section}) بنجاح\nالآن سيتم إرسال الجمل بشكلها الطبيعي")
            else:
                if storage.clear_preference(uid, section):
                    storage.clear_patterns(uid)
                    await u.message.reply_text(f"تم إعادة تعيين تفضيلات القسم ({section}) بنجاح\nالآن سيتم إرسال الجمل بشكلها الطبيعي")
                else:
                    await u.message.reply_text(f"لا يوجد تفضيل محفوظ للقسم ({section})")
        else:
            await u.message.reply_text("القسم غير موجود\nاستخدم: ريست [اسم القسم]\nمثال: ريست جمم")
        storage.log_cmd("ريست")
        return

    # معالج قسم عشوائي: يختار عشوائياً من الأقسام الستة
    if text == "عشوائي":
        storage.log_cmd("عشوائي")
        
        # قائمة الأقسام التي يختارها عشوائياً
        random_sections = ["ويكي", "مس", "كرر", "جمم", "جش", "جب", "شك", "حر"]
        
        # الحصول على الفهرس الحالي للمستخدم، أو تعيينه إلى 0 إذا لم يكن موجوداً
        if uid not in user_random_section_state:
            user_random_section_state[uid] = 0
        
        # اختيار القسم التالي من القائمة (دورة)
        current_index = user_random_section_state[uid]
        selected_section = random_sections[current_index]
        
        # تحديث الفهرس للعملية التالية
        user_random_section_state[uid] = (current_index + 1) % len(random_sections)
        
        # الآن نقوم بمعالجة الأمر كما لو أنه كتب اسم القسم مباشرة
        text = selected_section
        # المتابعة إلى معالجة الأقسام الطبيعية أدناه

    active_sessions = storage.get_all_active_sessions(cid)

    # ============ أمر نطاق الكلمات: (ويكي من 10 الى 20) ============
    # يخلي الجمل تنزل بعدد كلمات عشوائي بين الرقمين - يطبق على جميع الأقسام المدعومة
    range_match = re.match(r'^(.+?)\s+من\s+(\d+)\s+الى\s+(\d+)\s*$', text)
    if range_match:
        sec_name = range_match.group(1).strip()
        try:
            rlo = int(range_match.group(2))
            rhi = int(range_match.group(3))
        except ValueError:
            rlo = rhi = 0

        if sec_name in RANGE_SECTIONS and 1 <= rlo <= rhi <= 60:
            storage.save_preference_range(uid, sec_name, rlo, rhi)
            # تحديث حالة الصدارة حسب أقل عدد كلمات في النطاق
            leaderboard_sections = ["كرر", "ويكي", "مس", "شك", "جب", "جش", "جمم"]
            if sec_name in leaderboard_sections:
                if rlo >= 10:
                    storage.enable_section(uid, sec_name)
                else:
                    storage.disable_section(uid, sec_name)
            else:
                storage.disable_section(uid, sec_name)

            # توليد جملة فورية بعدد عشوائي داخل النطاق
            rc = random.randint(rlo, rhi)
            sent = build_sentence_for_section(uid, sec_name, rc)
            watermarked = None
            display = format_display(sent)
            if sec_name == "اص":
                # قسم اص: الجملة تنحفظ نظيفة والزخرفة للعرض فقط
                sent = as_strip_to_arabic(sent)
                if not sent:
                    sent = managers["اص"].get()
                watermarked = as_decorate_sentence(sent)
                display = watermarked
            storage.del_session(cid, sec_name)
            storage.save_session(uid, cid, sec_name, sent, time.time(), sent=True, random_mode=False, watermarked_text=watermarked)
            await u.message.reply_text(f"تم الحين الكلمات راح تكون عشوائية من {rlo} الى {rhi} كلمة في قسم {sec_name}")
            await asyncio.sleep(0.5)
            await u.message.reply_text(display)
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, sec_name))
            storage.log_cmd(f"{sec_name} نطاق")
            return
        else:
            await u.message.reply_text("القسم غير مدعوم أو الأرقام غلط، الصحيح مثل: (ويكي من 10 الى 20)")
            return

    command, word_count = extract_number_from_text(text)

    game_commands = ["جمم", "ويكي", "مس", "اص", "صج", "شك", "جش", "قص", "نص", "طب", "فر", "E", "e", "رق", "حر", "جب", "كرر", "شرط", "فكك", "دبل", "تر", "عكس"]
    is_game_command = (command in game_commands or text in game_commands)

    if is_game_command:
        if not await can_bot_send(cid):
            return

    # ============ قسم (طب) - جمل بالترتيب لكل مستخدم ============
    if command == "طب" or text == "طب":
        section = "طب"
        storage.log_cmd("طب")

        # جلب الجملة التالية بالترتيب لهذا المستخدم
        sent = managers["طب"].get_next(uid)
        storage.del_session(cid, "طب")
        storage.save_session(uid, cid, "طب", sent, time.time(), sent=True, random_mode=False)
        display = format_display(sent)
        await u.message.reply_text(display)
        asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "طب"))
        return

    # ============ قسم (اص) - جمل مس مزخرفة ============
    if command == "اص" or text == "اص":
        section = "اص"
        storage.log_cmd("اص")

        if word_count and 1 <= word_count <= 60:
            storage.save_preference(uid, section, word_count)
            storage.disable_section(uid, section)
            sent = get_text_with_word_count(managers["اص"], word_count)
            if sent:
                sent = as_strip_to_arabic(sent)
            if not sent:
                sent = managers["اص"].get()
            decorated = as_decorate_sentence(sent)
            storage.del_session(cid, "اص")
            storage.save_session(uid, cid, "اص", sent, time.time(), sent=True,
                                 random_mode=False, watermarked_text=decorated)
            await u.message.reply_text(f"تم الحين الكلمات {word_count} كلمة في الجملة")
            await asyncio.sleep(0.5)
            await u.message.reply_text(decorated)
        else:
            pref_count = storage.get_preference(uid, section)
            range_count = get_random_word_count(uid, section)
            if range_count is not None:
                pref_count = range_count
            if pref_count and 1 <= pref_count <= 60:
                sent = get_text_with_word_count(managers["اص"], pref_count)
                sent = as_strip_to_arabic(sent) if sent else None
                if not sent:
                    sent = managers["اص"].get()
            else:
                sent = managers["اص"].get()
            decorated = as_decorate_sentence(sent)
            storage.del_session(cid, "اص")
            storage.save_session(uid, cid, "اص", sent, time.time(), sent=True,
                                 random_mode=False, watermarked_text=decorated)
            await u.message.reply_text(decorated)
        return

    if command in ["جمم", "ويكي", "مس", "صج", "شك", "جش", "قص", "نص", "جب"] or text in ["جمم", "ويكي", "مس", "صج", "شك", "جش", "قص", "نص", "جب"]:
        section = command if word_count else text
        storage.log_cmd(section)

        if word_count and 1 <= word_count <= 60:
            storage.save_preference(uid, section, word_count)
            # تحكم الصدارة حسب عدد الكلمات للأقسام المعروضة في الصدارة
            leaderboard_sections = ["كرر", "ويكي", "مس", "شك", "جب", "جش", "جمم"]
            if section in leaderboard_sections:
                if word_count >= 10:
                    storage.enable_section(uid, section)
                else:
                    storage.disable_section(uid, section)
            else:
                # باقي الأقسام: تعطيل القسم من الصدارة (إلى أن يكتب ريست)
                storage.disable_section(uid, section)
            
            # معالجة خاصة لـ جب: استخدام generate_random_sentence بدل get_text_with_word_count
            if section == "جب":
                jab_type = user_jab_type.get(uid, "قديم")
                if jab_type == "حرفين":
                    current_jab_words = JAB_2_LETTERS
                elif jab_type == "ثلاث":
                    current_jab_words = JAB_3_LETTERS
                elif jab_type == "اربع":
                    current_jab_words = JAB_4_LETTERS
                elif jab_type == "خمس":
                    current_jab_words = JAB_5_LETTERS
                elif jab_type == "مختلط":
                    current_jab_words = JAB_2_LETTERS + JAB_3_LETTERS + JAB_4_LETTERS + JAB_5_LETTERS
                else:
                    current_jab_words = JAB_WORDS
                sent = generate_random_sentence(uid, current_jab_words, word_count, word_count, "جب")
            else:
                sent = get_text_with_word_count(managers[section], word_count)
            
            if sent:
                storage.del_session(cid, section)
                storage.save_session(uid, cid, section, sent, time.time(), sent=True, random_mode=False)
                display = format_display(sent)
                await u.message.reply_text(f"تم الحين الكلمات {word_count} كلمة في الجملة")
                await asyncio.sleep(0.5)
                await u.message.reply_text(display)
                asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, section))
            else:
                if section == "جب":
                    jab_type = user_jab_type.get(uid, "قديم")
                    if jab_type == "حرفين":
                        current_jab_words = JAB_2_LETTERS
                    elif jab_type == "ثلاث":
                        current_jab_words = JAB_3_LETTERS
                    elif jab_type == "اربع":
                        current_jab_words = JAB_4_LETTERS
                    elif jab_type == "خمس":
                        current_jab_words = JAB_5_LETTERS
                    elif jab_type == "مختلط":
                        current_jab_words = JAB_2_LETTERS + JAB_3_LETTERS + JAB_4_LETTERS + JAB_5_LETTERS
                    else:
                        current_jab_words = JAB_WORDS
                    sent = generate_random_sentence(uid, current_jab_words, word_count, word_count, "جب")
                else:
                    sent = managers[section].get()
                storage.del_session(cid, section)
                storage.save_session(uid, cid, section, sent, time.time(), sent=True, random_mode=True)
                display = format_display(sent)
                await u.message.reply_text(display)
                asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, section))
        else:
            pref_count = storage.get_preference(uid, section)
            range_count = get_random_word_count(uid, section)
            if range_count is not None:
                pref_count = range_count
            if pref_count and 1 <= pref_count <= 60:
                if section == "جب":
                    jab_type = user_jab_type.get(uid, "قديم")
                    if jab_type == "حرفين":
                        current_jab_words = JAB_2_LETTERS
                    elif jab_type == "ثلاث":
                        current_jab_words = JAB_3_LETTERS
                    elif jab_type == "اربع":
                        current_jab_words = JAB_4_LETTERS
                    elif jab_type == "خمس":
                        current_jab_words = JAB_5_LETTERS
                    elif jab_type == "مختلط":
                        current_jab_words = JAB_2_LETTERS + JAB_3_LETTERS + JAB_4_LETTERS + JAB_5_LETTERS
                    else:
                        current_jab_words = JAB_WORDS
                    sent = generate_random_sentence(uid, current_jab_words, pref_count, pref_count, "جب")
                else:
                    sent = get_text_with_word_count(managers[section], pref_count)
                    if not sent:
                        sent = managers[section].get()
            else:
                if section == "جب":
                    jab_type = user_jab_type.get(uid, "قديم")
                    if jab_type == "حرفين":
                        current_jab_words = JAB_2_LETTERS
                    elif jab_type == "ثلاث":
                        current_jab_words = JAB_3_LETTERS
                    elif jab_type == "اربع":
                        current_jab_words = JAB_4_LETTERS
                    elif jab_type == "خمس":
                        current_jab_words = JAB_5_LETTERS
                    elif jab_type == "مختلط":
                        current_jab_words = JAB_2_LETTERS + JAB_3_LETTERS + JAB_4_LETTERS + JAB_5_LETTERS
                    else:
                        current_jab_words = JAB_WORDS
                    sent = generate_random_sentence(uid, current_jab_words, 7, 20, "جب")
                else:
                    sent = managers[section].get()
            storage.del_session(cid, section)
            storage.save_session(uid, cid, section, sent, time.time(), sent=True, random_mode=False)
            display = format_display(sent)
            await u.message.reply_text(display)
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, section))
        return

    if command == "فر" or text == "فر":
        section = "فر"
        storage.log_cmd("فر")

        if word_count and 1 <= word_count <= 60:
            storage.save_preference(uid, section, word_count)
            storage.disable_section(uid, section)
            sent = get_text_with_word_count(managers["فر"], word_count)
            if sent:
                storage.del_session(cid, "فر")
                storage.save_session(uid, cid, "فر", sent, time.time(), sent=True, random_mode=False)
                display = format_display(sent)
                await u.message.reply_text(f"تم الحين الكلمات {word_count} كلمة في الجملة")
                await asyncio.sleep(0.5)
                await u.message.reply_text(display)
                asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "فر"))
            else:
                sent = managers["فر"].get()
                storage.del_session(cid, "فر")
                storage.save_session(uid, cid, "فر", sent, time.time(), sent=True, random_mode=False)
                display = format_display(sent)
                await u.message.reply_text(display)
                asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "فر"))
        else:
            pref_count = storage.get_preference(uid, section)
            range_count = get_random_word_count(uid, section)
            if range_count is not None:
                pref_count = range_count
            if pref_count and 1 <= pref_count <= 60:
                sent = get_text_with_word_count(managers["فر"], pref_count)
                if not sent:
                    sent = managers["فر"].get()
            else:
                sent = managers["فر"].get()
            storage.del_session(cid, "فر")
            storage.save_session(uid, cid, "فر", sent, time.time(), sent=True, random_mode=False)
            display = format_display(sent)
            await u.message.reply_text(display)
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "فر"))
        return

    if command == "E" or text in ["E", "e"]:
        section = "E"
        storage.log_cmd("E")

        if word_count and 1 <= word_count <= 60:
            storage.save_preference(uid, section, word_count)
            storage.disable_section(uid, section)
            sent = get_text_with_word_count(managers["E"], word_count)
            if sent:
                storage.del_session(cid, "E")
                storage.save_session(uid, cid, "E", sent, time.time(), sent=True, random_mode=False)
                display = format_display(sent)
                await u.message.reply_text(f"تم الحين الكلمات {word_count} كلمة في الجملة")
                await asyncio.sleep(0.5)
                await u.message.reply_text(display)
                asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "E"))
            else:
                sent = managers["E"].get()
                storage.del_session(cid, "E")
                storage.save_session(uid, cid, "E", sent, time.time(), sent=True, random_mode=False)
                display = format_display(sent)
                await u.message.reply_text(display)
                asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "E"))
        else:
            pref_count = storage.get_preference(uid, section)
            range_count = get_random_word_count(uid, section)
            if range_count is not None:
                pref_count = range_count
            if pref_count and 1 <= pref_count <= 60:
                sent = get_text_with_word_count(managers["E"], pref_count)
                if not sent:
                    sent = managers["E"].get()
            else:
                sent = managers["E"].get()
            storage.del_session(cid, "E")
            storage.save_session(uid, cid, "E", sent, time.time(), sent=True, random_mode=False)
            display = format_display(sent)
            await u.message.reply_text(display)
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "E"))
        return

    if text == "غير الرق":
        async with chat_locks[cid]:
            storage.log_cmd("غير الرق")
            keyboard = [
                [InlineKeyboardButton("لفظ (كلمات عربية)", callback_data="رق_لفظ")],
                [InlineKeyboardButton("ارقام صعبة (0-1000) اكتبها لفظاً", callback_data="رق_صعبة")],
                [InlineKeyboardButton("ارقام سهلة (0-100) اكتبها لفظاً", callback_data="رق_سهلة")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await u.message.reply_text("إذا تبي تغير نهج الأرقام اختر:\n\nلفظ: كلمات عربية جاهزة (واحد اثنين ثلاثه...)\nصعبة: أرقام من 0-1000 تكتبها لفظاً\nسهلة: أرقام من 0-100 تكتبها لفظاً", reply_markup=reply_markup)
        return

    if text == "ريست رق":
        async with chat_locks[cid]:
            storage.log_cmd("ريست رق")
            storage.save_preference(uid, "رق_عدد", None)
            storage.clear_number_type(uid)
            await u.message.reply_text("تم إعادة تعيين نظام الأرقام للوضع العشوائي (العدد والنوع)")
        return

    # معالج عام لتحديد عدد الكلمات لأي قسم (مثل: جمم 12، مق 15، إلخ)
    all_sections = ["جمم", "ويكي", "مس", "اص", "صج", "شك", "جش", "قص", "نص", "طب", "شرط", "فكك", "دبل", "تر", "عكس", "فر", "E", "رق", "حر", "جب", "كرر"]
    for section in all_sections:
        if text.startswith(f"{section} "):
            try:
                num_str = text.replace(f"{section} ", "").strip()
                num = int(num_str)
                if 1 <= num <= 60:
                    storage.log_cmd(f"{section} {num}")
                    storage.save_preference(uid, section, num)
                    storage.disable_section(uid, section)
                    await u.message.reply_text(f" تم تحديد {section} لـ {num} {'كلمة' if num == 1 else 'كلمات'}")
                    return
                else:
                    await u.message.reply_text("الرجاء إدخال رقم بين 1 و 60")
                    return
            except ValueError:
                pass

    if text.startswith("رق "):
        async with chat_locks[cid]:
            try:
                num_str = text.replace("رق ", "").strip()
                num = int(num_str)
                if 1 <= num <= 40:
                    storage.log_cmd(f"رق {num}")
                    storage.save_preference(uid, "رق_عدد", num)

                    await u.message.reply_text(f"تم حولنا رق لـ {num} {'رقم' if num == 1 else 'أرقام'}")
                    await asyncio.sleep(0.5)

                    saved_type = storage.get_number_type(uid)

                    if saved_type == "لفظ":
                        sent = generate_random_sentence(uid, NUMBER_WORDS, num, num, "رق")
                        storage.del_session(cid, "رق")
                        storage.save_session(uid, cid, "رق", sent, time.time(), sent=True)
                        display = format_display(sent)
                        await u.message.reply_text(display)
                        asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "رق"))
                    elif saved_type == "صعبة":
                        numbers, numbers_str = generate_hard_numbers_sentence(num)
                        storage.del_session(cid, "رق_صعبة")
                        storage.save_session(uid, cid, "رق_صعبة", numbers_str, time.time(), sent=True)
                        await u.message.reply_text(f"اكتب الأرقام لفظاً:\n\n{numbers_str}")
                    elif saved_type == "سهلة":
                        numbers, numbers_str = generate_easy_numbers_sentence(num)
                        storage.del_session(cid, "رق_سهلة")
                        storage.save_session(uid, cid, "رق_سهلة", numbers_str, time.time(), sent=True)
                        await u.message.reply_text(f"اكتب الأرقام لفظاً:\n\n{numbers_str}")
                    else:
                        numbers, numbers_str = generate_hard_numbers_sentence(num)
                        storage.del_session(cid, "رق_صعبة")
                        storage.save_session(uid, cid, "رق_صعبة", numbers_str, time.time(), sent=True)
                        await u.message.reply_text(f"اكتب الأرقام لفظاً:\n\n{numbers_str}")
                else:
                    await u.message.reply_text("الرجاء إدخال رقم بين 1 و 40")
            except ValueError:
                pass
        return

    if command == "رق" or text == "رق":
        async with chat_locks[cid]:
            if current_time - sent_message_tracker[cid]["رق"] < 0.5:
                return
            storage.log_cmd("رق")
            saved_type = storage.get_number_type(uid)
            pref_count = storage.get_preference(uid, "رق_عدد")

            if saved_type == "لفظ":
                count = pref_count or random.randint(7, 20)
                sent = generate_random_sentence(uid, NUMBER_WORDS, count, count, "رق")
                storage.del_session(cid, "رق")
                storage.save_session(uid, cid, "رق", sent, time.time(), sent=True)
                display = format_display(sent)
                await u.message.reply_text(display)
                asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "رق"))
            elif saved_type == "صعبة":
                count = pref_count or random.randint(5, 10)
                numbers, numbers_str = generate_hard_numbers_sentence(count)
                storage.del_session(cid, "رق_صعبة")
                storage.save_session(uid, cid, "رق_صعبة", numbers_str, time.time(), sent=True)
                await u.message.reply_text(f"اكتب الأرقام لفظاً:\n\n{numbers_str}")
            elif saved_type == "سهلة":
                count = pref_count or random.randint(5, 10)
                numbers, numbers_str = generate_easy_numbers_sentence(count)
                storage.del_session(cid, "رق_سهلة")
                storage.save_session(uid, cid, "رق_سهلة", numbers_str, time.time(), sent=True)
                await u.message.reply_text(f"اكتب الأرقام لفظاً:\n\n{numbers_str}")
            else:
                keyboard = [
                    [InlineKeyboardButton("لفظ (كلمات عربية)", callback_data="رق_لفظ")],
                    [InlineKeyboardButton("ارقام صعبة (0-1000) اكتبها لفظاً", callback_data="رق_صعبة")],
                    [InlineKeyboardButton("ارقام سهلة (0-100) اكتبها لفظاً", callback_data="رق_سهلة")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await u.message.reply_text("اختر نوع الأرقام:\n\nلفظ: كلمات عربية جاهزة (واحد اثنين ثلاثه...)\nصعبة: أرقام من 0-1000 تكتبها لفظاً\nسهلة: أرقام من 0-100 تكتبها لفظاً", reply_markup=reply_markup)
            sent_message_tracker[cid]["رق"] = current_time
        return

    if command == "حر" or text == "حر":
        async with chat_locks[cid]:
            message_id = f"{cid}_حر_{uid}_{current_time}"

            if current_time - sent_message_tracker[cid]["حر"] < 0.5:
                return

            storage.log_cmd("حر")

            if word_count and 1 <= word_count <= 60:
                storage.save_preference(uid, "حر", word_count)
                storage.disable_section(uid, "حر")
                sent = generate_random_sentence(uid, LETTER_WORDS, word_count, word_count, "حر")
                storage.del_session(cid, "حر")
                storage.save_session(uid, cid, "حر", sent, time.time(), sent=True)
                display = format_display(sent)
                await u.message.reply_text(f"تم الحين الكلمات {word_count} كلمة في الجملة")
                await asyncio.sleep(0.5)
                await u.message.reply_text(display)
                asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "حر"))
            else:
                pref_count = storage.get_preference(uid, "حر")
                if pref_count and 1 <= pref_count <= 60:
                    sent = generate_random_sentence(uid, LETTER_WORDS, pref_count, pref_count, "حر")
                else:
                    sent = generate_random_sentence(uid, LETTER_WORDS, 7, 20, "حر")
                storage.del_session(cid, "حر")
                storage.save_session(uid, cid, "حر", sent, time.time(), sent=True)
                display = format_display(sent)
                await u.message.reply_text(display)
                asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "حر"))

            sent_message_tracker[cid]["حر"] = current_time
        return

    # أوامر تغيير نوع جب - يجب أن تكون قبل معالجة أمر جب العادي
    if text == "جب حرفين":
        user_jab_type[uid] = "حرفين"
        await u.message.reply_text("تم الحين الكلمات صارت من حرفين")
        storage.log_cmd("جب حرفين")
        return

    if text in ["جب ثلاث حروف", "جب ثلاثه حروف"]:
        user_jab_type[uid] = "ثلاث"
        await u.message.reply_text("تم الحين الكلمات صارت من ثلاث حروف")
        storage.log_cmd("جب ثلاث حروف")
        return

    if text in ["جب اربع حروف", "جب اربعه حروف"]:
        user_jab_type[uid] = "اربع"
        await u.message.reply_text("تم الحين الكلمات صارت من اربع حروف")
        storage.log_cmd("جب اربع حروف")
        return

    if text in ["جب خمس حروف", "جب خمسه حروف"]:
        user_jab_type[uid] = "خمس"
        await u.message.reply_text("تم الحين الكلمات صارت من خمس حروف")
        storage.log_cmd("جب خمس حروف")
        return

    if text in ["جب مختلط", "جب عادي"]:
        user_jab_type[uid] = "مختلط"
        await u.message.reply_text("تم الحين الكلمات صارت مختلطة")
        storage.log_cmd("جب مختلط")
        return

    if text == "جب قديم":
        user_jab_type[uid] = "قديم"
        await u.message.reply_text("تم الحين الكلمات صارت من النظام القديم")
        storage.log_cmd("جب قديم")
        return

    if command == "جب" or text == "جب":
        async with chat_locks[cid]:
            message_id = f"{cid}_جب_{uid}_{current_time}"

            if current_time - sent_message_tracker[cid]["جب"] < 0.5:
                return

            storage.log_cmd("جب")

            # تحديد قائمة الكلمات حسب نوع جب المختار للمستخدم
            # الوضع الافتراضي هو "قديم" للمستخدمين الجدد
            jab_type = user_jab_type.get(uid, "قديم")
            if jab_type == "حرفين":
                current_jab_words = JAB_2_LETTERS
            elif jab_type == "ثلاث":
                current_jab_words = JAB_3_LETTERS
            elif jab_type == "اربع":
                current_jab_words = JAB_4_LETTERS
            elif jab_type == "خمس":
                current_jab_words = JAB_5_LETTERS
            elif jab_type == "مختلط":
                # مختلط: كلمات من جميع الأحجام
                current_jab_words = JAB_2_LETTERS + JAB_3_LETTERS + JAB_4_LETTERS + JAB_5_LETTERS
            else:
                # قديم: الوضع الافتراضي
                current_jab_words = JAB_WORDS

            pref_count = storage.get_preference(uid, "جب")
            if pref_count and 1 <= pref_count <= 60:
                sent = generate_random_sentence(uid, current_jab_words, pref_count, pref_count, "جب")
            else:
                sent = generate_random_sentence(uid, current_jab_words, 7, 20, "جب")
            storage.del_session(cid, "جب")
            storage.save_session(uid, cid, "جب", sent, time.time(), sent=True)
            display = format_display(sent)
            await u.message.reply_text(display)
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "جب"))

            sent_message_tracker[cid]["جب"] = current_time
        return

    # تحديد عدد كلمات جب تم نقله إلى نظام موحد - انظر السطر 7039-7150
    # الكود القديم تم حذفه

    if command == "كشف" or text == "كشف":
        async with chat_locks[cid]:
            storage.log_cmd("كشف")
            saved_type = user_kashf_type.get(uid)
            pref_count = storage.get_preference(uid, "كشف_عدد")

            if saved_type == "براد":
                count = pref_count or random.randint(7, 20)
                # جلب جملة من قسم نص
                sent = managers["نص"].get() if "نص" in managers else managers["ويكي"].get()
                words = sent.split()
                if len(words) > count:
                    words = words[:count]
                # اختيار حرف عشوائي
                separator = random.choice(ARABIC_LETTERS)
                user_kashf_separator[uid] = separator
                # إضافة الحرف بين الكلمات
                display_text = f" {separator} ".join(words)
                # حفظ الجملة الأصلية (بدون الحرف)
                original_text = " ".join(words)
                storage.del_session(cid, "كشف_براد")
                storage.save_session(uid, cid, "كشف_براد", original_text, time.time(), sent=True)
                await u.message.reply_text("اكتب الكلمات بدون الحرف اللي يفصل بينها")
                await asyncio.sleep(0.5)
                await u.message.reply_text(display_text)
            elif saved_type == "مايك":
                # كشف المايك: ما نرسل شيء، فقط رسالة توضيحية تم إرسالها عند الضغط على الزر
                pass
            elif saved_type == "نسوخي":
                count = pref_count or random.randint(7, 15)
                sent = managers["ويكي"].get()
                words = sent.split()
                if len(words) > count:
                    words = words[:count]
                # إضافة / بعد كل كلمة
                display_text = "/ ".join(words) + "/"
                original_text = " ".join(words)
                storage.del_session(cid, "كشف_نسوخي")
                storage.save_session(uid, cid, "كشف_نسوخي", original_text, time.time(), sent=True)
                await u.message.reply_text(display_text)
            else:
                keyboard = [
                    [InlineKeyboardButton("كشف البراد", callback_data="كشف_براد")],
                    [InlineKeyboardButton("كشف المايك", callback_data="كشف_مايك")],
                    [InlineKeyboardButton("كشف النسوخي", callback_data="كشف_نسوخي")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await u.message.reply_text("اختر نوع الكشف:", reply_markup=reply_markup)
            sent_message_tracker[cid]["كشف"] = current_time
        return

    # تحديد عدد كلمات كشف
    if text.startswith("كشف "):
        async with chat_locks[cid]:
            try:
                num_str = text.replace("كشف ", "").strip()
                num = int(num_str)
                if 1 <= num <= 60:
                    storage.log_cmd(f"كشف {num}")
                    storage.save_preference(uid, "كشف_عدد", num)
                    await u.message.reply_text(f"تم تحديد كشف بـ {num} كلمة")
                    await asyncio.sleep(0.5)
                    
                    saved_type = user_kashf_type.get(uid, "براد")
                    
                    if saved_type == "براد":
                        sent = managers["نص"].get() if "نص" in managers else managers["ويكي"].get()
                        words = sent.split()
                        if len(words) > num:
                            words = words[:num]
                        separator = random.choice(ARABIC_LETTERS)
                        user_kashf_separator[uid] = separator
                        display_text = f" {separator} ".join(words)
                        original_text = " ".join(words)
                        storage.del_session(cid, "كشف_براد")
                        storage.save_session(uid, cid, "كشف_براد", original_text, time.time(), sent=True)
                        await u.message.reply_text("اكتب الكلمات بدون الحرف اللي يفصل بينها")
                        await asyncio.sleep(0.5)
                        await u.message.reply_text(display_text)
                    elif saved_type == "مايك":
                        sent = generate_random_sentence(uid, NUMBER_WORDS, num, num, "رق")
                        storage.del_session(cid, "كشف_مايك")
                        storage.save_session(uid, cid, "كشف_مايك", sent, time.time(), sent=True)
                        await u.message.reply_text(sent)
                    elif saved_type == "نسوخي":
                        sent = managers["ويكي"].get()
                        words = sent.split()
                        if len(words) > num:
                            words = words[:num]
                        display_text = "/ ".join(words) + "/"
                        original_text = " ".join(words)
                        storage.del_session(cid, "كشف_نسوخي")
                        storage.save_session(uid, cid, "كشف_نسوخي", original_text, time.time(), sent=True)
                        await u.message.reply_text(display_text)
                else:
                    await u.message.reply_text("الرجاء إدخال رقم بين 1 و 60")
            except ValueError:
                pass
        return

    if text == "ريست كشف":
        async with chat_locks[cid]:
            storage.log_cmd("ريست كشف")
            storage.save_preference(uid, "كشف_عدد", None)
            user_kashf_type.pop(uid, None)
            user_kashf_separator.pop(uid, None)
            await u.message.reply_text("تم إعادة تعيين نظام كشف")
        return

    if text == "غير الكشف":
        async with chat_locks[cid]:
            storage.log_cmd("غير الكشف")
            keyboard = [
                [InlineKeyboardButton("كشف البراد", callback_data="كشف_براد")],
                [InlineKeyboardButton("كشف المايك", callback_data="كشف_مايك")],
                [InlineKeyboardButton("كشف النسوخي", callback_data="كشف_نسوخي")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await u.message.reply_text("اختر نوع الكشف:", reply_markup=reply_markup)
        return
    # ============ نهاية قسم كشف ============

    if command == "كرر" or text == "كرر":
        async with chat_locks[cid]:
            if current_time - sent_message_tracker[cid]["كرر"] < 0.5:
                return

            storage.log_cmd("كرر")

            # الحصول على الكلمات المستخدمة في آخر 4 رسائل
            recent_words = storage.get_preference(uid, "كرر_recent_words") or []

            if word_count and 1 <= word_count <= 60:
                storage.save_preference(uid, "كرر", word_count)
                storage.disable_section(uid, "كرر")
                patterns = gen_pattern(uid, word_count, exclude_words=recent_words)
                pattern = " ".join(patterns)
                # حفظ الكلمات المستخدمة
                words_used = [p.split('(')[0] for p in patterns]
                new_recent = (recent_words + words_used)[-4:]
                storage.save_preference(uid, "كرر_recent_words", new_recent)
                storage.del_session(cid, "كرر")
                storage.save_session(uid, cid, "كرر", pattern, time.time(), sent=True)
                await u.message.reply_text(f"تم تحديد كرر بـ {word_count} {'كلمة' if word_count == 1 else 'كلمات'}")
                await asyncio.sleep(0.5)
                await u.message.reply_text(pattern)
                asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, pattern, "كرر"))
            else:
                pref_count = storage.get_preference(uid, "كرر")
                if pref_count and 1 <= pref_count <= 60:
                    patterns = gen_pattern(uid, pref_count, exclude_words=recent_words)
                    pattern = " ".join(patterns)
                else:
                    random_count = random.randint(3, 5)
                    patterns = gen_pattern(uid, random_count, exclude_words=recent_words)
                    pattern = " ".join(patterns)
                # حفظ الكلمات المستخدمة
                words_used = [p.split('(')[0] for p in patterns]
                new_recent = (recent_words + words_used)[-4:]
                storage.save_preference(uid, "كرر_recent_words", new_recent)
                storage.del_session(cid, "كرر")
                storage.save_session(uid, cid, "كرر", pattern, time.time(), sent=True)
                await u.message.reply_text(pattern)
                asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, pattern, "كرر"))

            sent_message_tracker[cid]["كرر"] = current_time
        return

    if command == "شرط" or text == "شرط":
        section = "شرط"
        storage.log_cmd("شرط")

        if word_count and 1 <= word_count <= 60:
            storage.save_preference(uid, section, word_count)
            storage.disable_section(uid, section)
            sent = get_text_with_word_count(managers["شرط"], word_count)
            if not sent:
                sent = managers["شرط"].get()
            cond = random.choice(CONDITIONS)
            full = f"{sent}||{cond}"
            storage.del_session(cid, "شرط")
            storage.save_session(uid, cid, "شرط", full, time.time(), sent=True)
            await u.message.reply_text(f"تم الحين الكلمات {word_count} كلمة في الجملة")
            await asyncio.sleep(0.5)
            await u.message.reply_text(cond)
            await asyncio.sleep(2)
            await c.bot.send_message(chat_id=cid, text=format_display(sent))
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "شرط"))
        else:
            pref_count = storage.get_preference(uid, section)
            range_count = get_random_word_count(uid, section)
            if range_count is not None:
                pref_count = range_count
            if pref_count and 1 <= pref_count <= 60:
                sent = get_text_with_word_count(managers["شرط"], pref_count)
                if not sent:
                    sent = managers["شرط"].get()
            else:
                sent = managers["شرط"].get()
            cond = random.choice(CONDITIONS)
            full = f"{sent}||{cond}"
            storage.del_session(cid, "شرط")
            storage.save_session(uid, cid, "شرط", full, time.time(), sent=True)
            await u.message.reply_text(cond)
            await asyncio.sleep(2)
            await c.bot.send_message(chat_id=cid, text=format_display(sent))
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "شرط"))
        return

    if command == "فكك" or text == "فكك":
        section = "فكك"
        storage.log_cmd("فكك")

        if word_count and 1 <= word_count <= 60:
            storage.save_preference(uid, section, word_count)
            storage.disable_section(uid, section)
            sent = get_text_with_word_count(managers["فكك"], word_count)
            if not sent:
                sent = managers["فكك"].get()
            storage.del_session(cid, "فكك_تفكيك")
            storage.save_session(uid, cid, "فكك_تفكيك", sent, time.time(), sent=True)
            await u.message.reply_text(f"تم الحين الكلمات {word_count} كلمة في الجملة")
            await asyncio.sleep(0.5)
            await u.message.reply_text(format_display(sent))
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "فكك"))
        else:
            pref_count = storage.get_preference(uid, section)
            range_count = get_random_word_count(uid, section)
            if range_count is not None:
                pref_count = range_count
            if pref_count and 1 <= pref_count <= 60:
                sent = get_text_with_word_count(managers["فكك"], pref_count)
                if not sent:
                    sent = managers["فكك"].get()
            else:
                sent = managers["فكك"].get()
            storage.del_session(cid, "فكك_تفكيك")
            storage.save_session(uid, cid, "فكك_تفكيك", sent, time.time(), sent=True)
            await u.message.reply_text(format_display(sent))
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "فكك"))
        return

    if command == "دبل" or text == "دبل":
        section = "دبل"
        storage.log_cmd("دبل")

        if word_count and 1 <= word_count <= 60:
            storage.save_preference(uid, section, word_count)
            storage.disable_section(uid, section)
            sent = get_text_with_word_count(managers["دبل"], word_count)
            if not sent:
                sent = managers["دبل"].get()
            storage.del_session(cid, "دبل")
            storage.save_session(uid, cid, "دبل", sent, time.time(), sent=True)
            await u.message.reply_text(f"تم الحين الكلمات {word_count} كلمة في الجملة")
            await asyncio.sleep(0.5)
            await u.message.reply_text(format_display(sent))
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "دبل"))
        else:
            pref_count = storage.get_preference(uid, section)
            range_count = get_random_word_count(uid, section)
            if range_count is not None:
                pref_count = range_count
            if pref_count and 1 <= pref_count <= 60:
                sent = get_text_with_word_count(managers["دبل"], pref_count)
                if not sent:
                    sent = managers["دبل"].get()
            else:
                sent = managers["دبل"].get()
            storage.del_session(cid, "دبل")
            storage.save_session(uid, cid, "دبل", sent, time.time(), sent=True)
            display = format_display(sent)
            await u.message.reply_text(display)
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "دبل"))
        return

    if command == "تر" or text == "تر":
        section = "تر"
        storage.log_cmd("تر")

        if word_count and 1 <= word_count <= 60:
            storage.save_preference(uid, section, word_count)
            storage.disable_section(uid, section)
            sent = get_text_with_word_count(managers["تر"], word_count)
            if not sent:
                sent = managers["تر"].get()
            storage.del_session(cid, "تر")
            storage.save_session(uid, cid, "تر", sent, time.time(), sent=True)
            await u.message.reply_text(f"تم الحين الكلمات {word_count} كلمة في الجملة")
            await asyncio.sleep(0.5)
            await u.message.reply_text(format_display(sent))
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "تر"))
        else:
            pref_count = storage.get_preference(uid, section)
            range_count = get_random_word_count(uid, section)
            if range_count is not None:
                pref_count = range_count
            if pref_count and 1 <= pref_count <= 60:
                sent = get_text_with_word_count(managers["تر"], pref_count)
                if not sent:
                    sent = managers["تر"].get()
            else:
                sent = managers["تر"].get()
            storage.del_session(cid, "تر")
            storage.save_session(uid, cid, "تر", sent, time.time(), sent=True)
            display = format_display(sent)
            await u.message.reply_text(display)
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "تر"))
        return

    if command == "عكس" or text == "عكس":
        section = "عكس"
        storage.log_cmd("عكس")

        if word_count and 1 <= word_count <= 60:
            storage.save_preference(uid, section, word_count)
            storage.disable_section(uid, section)
            sent = get_text_with_word_count(managers["عكس"], word_count)
            if not sent:
                sent = managers["عكس"].get()
            storage.del_session(cid, "عكس")
            storage.save_session(uid, cid, "عكس", sent, time.time(), sent=True)
            await u.message.reply_text(f"تم الحين الكلمات {word_count} كلمة في الجملة")
            await asyncio.sleep(0.5)
            await u.message.reply_text(format_display(sent))
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "عكس"))
        else:
            pref_count = storage.get_preference(uid, section)
            range_count = get_random_word_count(uid, section)
            if range_count is not None:
                pref_count = range_count
            if pref_count and 1 <= pref_count <= 60:
                sent = get_text_with_word_count(managers["عكس"], pref_count)
                if not sent:
                    sent = managers["عكس"].get()
            else:
                sent = managers["عكس"].get()
            storage.del_session(cid, "عكس")
            storage.save_session(uid, cid, "عكس", sent, time.time(), sent=True)
            display = format_display(sent)
            await u.message.reply_text(display)
            asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "عكس"))
        return

    best_match = None
    best_elapsed = None

    correction_applied = False  # صار True إذا الجواب كان تصحيح (تعديل)

    for session in active_sessions:
        typ = session.get("type")
        orig = session.get("text")
        start_time = session.get("time")
        elapsed = time.time() - start_time

        if elapsed > 120:
            continue

        matched = False
        accuracy = None
        via_correction = False

        # ===== نظام التعديل/التصحيح =====
        # إذا المستخدم كتب كلمة ناقصة (تصحيح) بعد إجابة خاطئة -> تحسب سرعته
        if not session.get("type", "").startswith("match_") and typ in CORRECTION_SECTIONS:
            corr = clean_correction_text(text)
            wrong = session.get("wrong_attempts", {}).get(str(uid))
            if corr and wrong:
                missing = find_missing_words(orig, wrong.get("text", ""))
                if len(missing) == 1 and (corr == missing[0] or corr in missing[0]):
                    matched = True
                    via_correction = True
                    accuracy = 100.0
                else:
                    # برضو: لو كتب الجملة كاملة صحيحة مرة ثانية بعد الخطأ -> تعتبر تعديل وتحسب له
                    try:
                        if normalize(orig) == normalize(text):
                            matched = True
                            via_correction = True
                            accuracy = 100.0
                    except Exception:
                        pass

        try:
            user_accuracy_on = is_accuracy_enabled_for(uid)
            if typ == "اص":
                # قسم اص: لازم يكتب الجملة بشكلها العادي
                # إذا كتب أي حرف مزخرف أو تطويل => لا تُحسب السرعة إطلاقاً
                if as_user_used_fancy(text):
                    await u.message.reply_text("اكتب الجملة بحروفها العادية بدون زخرفة ولا تطويل، وإلا ما تنحسب سرعتك")
                    storage.del_session(cid, typ)
                    continue
                base_accuracy = compute_word_based_accuracy(orig, text, "arabic")
                accuracy = base_accuracy
                matched = True if user_accuracy_on else (base_accuracy == 100.0)
            elif typ in ["جمم", "ويكي", "مس", "صج", "شك", "جش", "قص", "نص", "طب", "جب", "حر"]:
                # دقة مبنية على الكلمات تسمح بتغيير الترتيب والتكرار الصحيح
                base_accuracy = compute_word_based_accuracy(orig, text, "arabic")
                all_words_present = base_accuracy == 100.0
                if user_accuracy_on:
                    # مع تفعيل الدقة: حساب الدقة الفعلية (تسمح بالترتيب/التكرار) + قبول دائماً
                    accuracy = base_accuracy
                    matched = True
                else:
                    # مع تعطيل الدقة: قبول فقط عند 100%
                    accuracy = base_accuracy
                    matched = all_words_present
            elif typ == "فر":
                base_accuracy = compute_word_based_accuracy(orig, text, "persian")
                all_words_present = base_accuracy == 100.0
                if user_accuracy_on:
                    # مع تفعيل الدقة: حساب الدقة الفعلية (تسمح بالترتيب/التكرار) + قبول دائماً
                    accuracy = base_accuracy
                    matched = True
                else:
                    # مع تعطيل الدقة: قبول فقط عند 100%
                    accuracy = base_accuracy
                    matched = all_words_present
            elif typ == "E":
                base_accuracy = compute_word_based_accuracy(orig, text, "english")
                all_words_present = base_accuracy == 100.0
                if user_accuracy_on:
                    # مع تفعيل الدقة: حساب الدقة الفعلية (تسمح بالترتيب/التكرار) + قبول دائماً
                    accuracy = base_accuracy
                    matched = True
                else:
                    # مع تعطيل الدقة: قبول فقط عند 100%
                    accuracy = base_accuracy
                    matched = all_words_present
            elif typ == "رق":
                if match_numbers(orig, text):
                    matched = True
                    accuracy = 100.0  # إذا تطابقت الأرقام تماماً، الدقة 100%
                else:
                    matched = False
            elif typ in ["رق_صعبة", "رق_سهلة"]:
                if match_numbers(orig, text):
                    matched = True
                    accuracy = 100.0  # إذا تطابقت الأرقام تماماً، الدقة 100%
                else:
                    matched = False
            elif typ == "كشف_براد":
                # كشف البراد: يجب أن يكتب بدون الحرف الفاصل
                separator = user_kashf_separator.get(uid, "")
                # فحص إذا كتب مع الحرف الفاصل (الحرف محاط بمسافات كفاصل)
                separator_pattern = f" {separator} "
                if separator and separator_pattern in text:
                    # كتب مع الحرف كفاصل = براد
                    await u.message.reply_text("هل انت براد ام ماذا يا اخي")
                    storage.del_session(cid, typ)
                    continue
                # فحص التطابق
                base_accuracy = compute_word_based_accuracy(orig, text, "arabic")
                if base_accuracy == 100.0:
                    matched = True
                    accuracy = 100.0
                else:
                    matched = False
            elif typ == "كشف_مايك":
                # كشف المايك: فحص إذا أرسل أرقام بدل كلمات
                if re.search(r'\d', text):
                    # أرسل أرقام = مايك
                    await u.message.reply_text("قوم يا واد يا نسوخي شكلك تبغى تتبند تراك مايك يا مايك لا تلعب على الناس وتسوي انك رجال هههههههههههههههههههههههههههههههههههههههههههههههههه")
                    storage.del_session(cid, typ)
                    continue
                # نفس طريقة رق لفظ بالضبط
                if match_numbers(orig, text):
                    matched = True
                    accuracy = 100.0
                else:
                    # حساب الدقة مثل باقي الأقسام
                    accuracy = compute_accuracy(orig, text, "arabic")
                    matched = False
            elif typ == "كشف_نسوخي":
                # كشف النسوخي: يجب أن يكتب بدون الفواصل /
                if "/" in text:
                    # كتب مع الفواصل = نسوخي
                    await u.message.reply_text("شف شكلك على نياتك اكتب الجمله بدون الفواصل\n واذا انت نسوخي سردب يا حمار كشفناك هههههههههههههههههههههههههههههههههههههههههههههههههه")
                    storage.del_session(cid, typ)
                    continue
                # فحص التطابق
                base_accuracy = compute_word_based_accuracy(orig, text, "arabic")
                if base_accuracy == 100.0:
                    matched = True
                    accuracy = 100.0
                else:
                    matched = False
            elif typ == "كرر":
                valid, err = validate_repeat(orig, text)
                matched = bool(valid)
                if matched:
                    accuracy = compute_accuracy(orig, text, "arabic")
            elif typ == "خصص":
                if '(' in orig and ')' in orig:
                    valid, err = validate_repeat(orig, text)
                    matched = bool(valid)
                    if matched:
                        accuracy = compute_accuracy(orig, text, "arabic")
                else:
                    # تحقق من وجود جميع الكلمات بدلاً من الاعتماد فقط على المطابقة الحرفية
                    base_accuracy = compute_word_based_accuracy(orig, text, "arabic")
                    all_words_present = base_accuracy == 100.0
                    if user_accuracy_on:
                        # مع تفعيل الدقة: حساب الدقة الفعلية (تسمح بالترتيب/التكرار) + قبول دائماً
                        accuracy = base_accuracy
                        matched = True
                    else:
                        # مع تعطيل الدقة: قبول فقط عند 100%
                        accuracy = base_accuracy
                        matched = all_words_present
            elif typ == "شرط":
                if '||' in orig:
                    orig_s, cond = orig.split('||')
                    valid, exp = validate_condition(cond, orig_s, text)
                    matched = bool(valid)
                    if matched:
                        accuracy = compute_accuracy(orig, text, "arabic")
            elif typ == "فكك_تفكيك":
                if is_correct_disassembly(orig, text):
                    matched = True
                    accuracy = compute_accuracy(orig, text, "arabic")
                else:
                    matched = False
            elif typ == "دبل":
                valid, err = validate_double(orig, text)
                matched = bool(valid)
                if matched:
                    accuracy = compute_accuracy(orig, text, "arabic")
            elif typ == "تر":
                valid, err = validate_triple(orig, text)
                matched = bool(valid)
                if matched:
                    accuracy = compute_accuracy(orig, text, "arabic")
            elif typ == "عكس":
                valid, err = validate_reverse(orig, text)
                matched = bool(valid)
                if matched:
                    accuracy = compute_accuracy(orig, text, "arabic")
        except Exception as e:
            print(f"Error matching session: {e}")
            continue

        # إذا كان تصحيح: نرجع القيم الصحيحة لأن فحص المطابقة العادي ما يناسب رسالة التصحيح
        if via_correction:
            matched = True
            accuracy = 100.0

        # إذا الإجابة ما طابقت: سجلها كمحاولة خاطئة (عشان يقدر يعدلها بعدين)
        if not matched:
            if not via_correction and not session.get("type", "").startswith("match_") and typ in CORRECTION_SECTIONS:
                if word_overlap_ratio(orig, text) >= 0.5:
                    storage.record_wrong_attempt(cid, typ, uid, text)

        if matched:
            if via_correction:
                # التعديل مربوط بهذي الجلسة بالذات - خذها فوراً
                best_match = session
                best_elapsed = elapsed
                correction_applied = True
            elif best_match is None or elapsed < best_elapsed:
                best_match = session
                best_elapsed = elapsed

        # فحص 1v1 matchmaking - اختر أقرب جلسة match بغض النظر عما إذا كانت مطابقة
        if not correction_applied and session.get("type", "").startswith("match_"):
            if best_match is None or (best_match.get("type", "").startswith("match_") and elapsed < best_elapsed):
                best_match = session
                best_elapsed = elapsed

    if best_match:
        typ = best_match.get("type")
        orig = best_match.get("text")
        elapsed = best_elapsed
        random_mode = best_match.get("random_mode", True)
        watermarked_text = best_match.get("watermarked_text")

        # حماية إضافية لقسم اص: أي حرف مزخرف أو تطويل = لا سرعة
        if typ == "اص" and as_user_used_fancy(text):
            storage.del_session(cid, typ)
            storage.save()
            return

        # حساب الدقة للجملة المطابقة لتضمينها في الرد أو لتجاهل الإجابات الضعيفة
        accuracy = None
        try:
            user_accuracy_enabled = is_accuracy_enabled_for(uid)
            # تحديد اللغة بناءً على نوع الجلسة
            if typ.startswith("فر"):
                accuracy = compute_accuracy(orig, text, "persian") if user_accuracy_enabled else compute_word_based_accuracy(orig, text, "persian")
            elif typ.startswith("E"):
                accuracy = compute_accuracy(orig, text, "english") if user_accuracy_enabled else compute_word_based_accuracy(orig, text, "english")
            elif typ.startswith("match_"):
                # matchmaking سيُحسب الدقة لاحقًا حسب القسم الأصلي
                accuracy = None
            elif typ.startswith("رق") or typ == "كشف_مايك":
                accuracy = 100.0 if match_numbers(orig, text) else compute_accuracy(orig, text, "arabic")
            elif typ in ["كرر", "دبل", "دبل وتر", "خصص"]:
                if '(' in orig and ')' in orig:
                    valid, err = validate_repeat(orig, text)
                    accuracy = 100.0 if valid else compute_accuracy(orig, text, "arabic")
                else:
                    accuracy = compute_accuracy(orig, text, "arabic") if user_accuracy_enabled else compute_word_based_accuracy(orig, text, "arabic")
            else:
                accuracy = compute_accuracy(orig, text, "arabic") if user_accuracy_enabled else compute_word_based_accuracy(orig, text, "arabic")
        except Exception:
            accuracy = compute_accuracy(orig, text, "arabic")

        # إذا كان الجواب تصحيح (تعديل): الدقة 100% لأن الكلمة الناقصة انكتبت صح
        if correction_applied:
            accuracy = 100.0

        # التحقق من 1v1 matchmaking
        if typ.startswith("match_"):
            game_id = typ.replace("match_", "")
            game = storage.get_matchmaking_game(game_id)

            # استخراج القسم الأصلي من الجملة المخزنة
            chosen_section = game.get("last_section", "كرر") if game else "كرر"

            # استثناء "كرر" و "دبل وتر" - استخدام كلمات المستخدم
            # للأقسام الأخرى - استخدام كلمات الجملة الأصلية فقط
            if chosen_section in ["كرر", "دبل وتر"]:
                word_count = count_words_for_wpm(text)
            else:
                word_count = count_words_for_wpm(orig)

            elapsed = max(elapsed, 0.01)
            wpm = (word_count / elapsed) * 60 + 20

            if game and text != "جاهز" and text != "تنسحب":
                # التحقق من أن اللعبة لم تنته بعد
                if game.get("status") == "finished":
                    await u.message.reply_text("هذه الجولة انتهت بالفعل. ابدأ جولة جديدة!")
                    return

                player1 = game["player1"]
                player2 = game["player2"]
                opponent_uid = player2['uid'] if player1['uid'] == uid else player1['uid']

                # التحقق من طلب الشطب
                if text == "شطب":
                    # إذا كان الخصم هو البوت، وافق مباشرة
                    if opponent_uid == -1:
                        # البوت يوافق فوراً
                        await u.message.reply_text("تم الشطب")

                        # حذف الجلسات القديمة
                        storage.del_session(uid, typ)
                        storage.del_session(opponent_uid, typ)

                        # إرسال جملة جديدة من قسم مختلف - استدعاء من أي لاعب
                        await asyncio.sleep(1)
                        asyncio.create_task(send_next_match_sentence(c, player1['uid'], player2['uid'], game_id, exclude_section=game.get("last_section")))

                        storage.save()
                        return

                    # إذا كان هناك طلب شطب بالفعل من الخصم
                    if game.get("skip_request") and game["skip_request"] != uid:
                        # تنفيذ الشطب - حذف الجلسة الحالية وإرسال جملة جديدة
                        await u.message.reply_text("تم الشطب")

                        if opponent_uid != -1:
                            try:
                                await c.bot.send_message(opponent_uid, "تم الشطب")
                            except:
                                pass

                        # حذف الجلسات القديمة
                        storage.del_session(uid, typ)
                        storage.del_session(opponent_uid, typ)

                        # إرسال جملة جديدة من قسم مختلف - استدعاء من أي لاعب
                        await asyncio.sleep(1)
                        asyncio.create_task(send_next_match_sentence(c, player1['uid'], player2['uid'], game_id, exclude_section=game.get("last_section")))

                        # حذف طلب الشطب
                        game["skip_request"] = None
                        storage.data["matchmaking_games"][game_id] = game
                        storage.save()
                        return
                    else:
                        # طلب شطب جديد
                        game["skip_request"] = uid
                        storage.data["matchmaking_games"][game_id] = game

                        opponent_name = player2['first_name'] if player1['uid'] == uid else player1['first_name']

                        # رسالة للمستخدم الذي طلب الشطب
                        await u.message.reply_text("تم ننتظر الطرف الثاني يشطب")

                        if opponent_uid != -1:
                            try:
                                await c.bot.send_message(opponent_uid, "خصمك قال نشطب تبي تشطب ؟\n(عشان تشطب اكتب شطب)")
                            except:
                                pass

                        storage.del_session(cid, typ)
                        storage.save()
                        return

                # التحقق من صحة الإجابة حسب نوع القسم مع حساب الدقة
                match_result = False
                accuracy = None

                user_accuracy_on = is_accuracy_enabled_for(uid)
                if chosen_section == "كرر":
                    valid, err = validate_repeat(orig, text)
                    match_result = valid
                    if match_result:
                        accuracy = 100.0
                elif chosen_section == "شرط":
                    orig_s, cond = orig.split('||')
                    valid, exp = validate_condition(cond, orig_s, text)
                    match_result = bool(valid)
                    if match_result:
                        accuracy = 100.0
                elif chosen_section in ["ويكي", "مس", "شك", "جب", "جش", "قص", "نص", "طب", "جمم", "صج", "حر"]:
                    base_accuracy = compute_word_based_accuracy(orig, text, "arabic")
                    all_words_present = base_accuracy == 100.0
                    if user_accuracy_on:
                        # مع تفعيل الدقة: حساب الدقة الفعلية (تسمح بالترتيب/التكرار) + قبول دائماً
                        accuracy = base_accuracy
                        match_result = True
                    else:
                        # مع تعطيل الدقة: قبول فقط عند 100%
                        accuracy = base_accuracy
                        match_result = all_words_present
                else:
                    # افتراضيًا استخدم المطابقة الحرفية العامة
                    match_result, accuracy = match_with_accuracy(orig, text, "arabic")

                if not match_result:
                    # لم تتطابق الإجابة بالشكل المطلوب — تجاهل / احذف الجلسة
                    storage.del_session(cid, typ)
                    return

                mention = f"@{usr}" if usr else name

                # تسجيل الإجابة مع الوقت
                global pending_match_answers
                current_time = time.time()

                if game_id not in pending_match_answers:
                    pending_match_answers[game_id] = {}

                    # إذا كانت هناك إجابة معلقة من اللاعب الآخر
                    other_uid = player2['uid'] if player1['uid'] == uid else player1['uid']
                    is_loser = False
                    if other_uid in pending_match_answers[game_id]:
                        other_time = pending_match_answers[game_id][other_uid]
                        if other_time < current_time:
                            # الإجابة الأخرى أسرع - الإجابة الحالية أبطأ
                            is_loser = True
                            elapsed_for_other = other_time - (current_time - elapsed)
                            other_wpm = (word_count / max(abs(elapsed_for_other), 0.01)) * 60 + 20
                            # حفظ سرعة الخصم: مع تفعيل الدقة احفظ دائماً، بدون احفظ فقط عند 100%
                            other_accuracy_on = is_accuracy_enabled_for(other_uid)
                            should_save_other = other_accuracy_on or (accuracy is not None and accuracy == 100.0)
                            if should_save_other:
                                other_device_type = storage.get_device_type(other_uid)
                                storage.save_speed_for_section(other_uid, chosen_section, other_wpm)
                                # حفظ الصدارة: للأقسام الستة احفظ فقط عند دقة 100%
                                leaderboard_sections = ["كرر", "ويكي", "مس", "شك", "جب", "جش", "جمم"]
                                if chosen_section in leaderboard_sections and accuracy == 100.0:
                                    storage.update_score(other_uid, chosen_section, other_wpm, other_device_type)
                        else:
                            # الإجابة الحالية أسرع - تجاهل الإجابة الأخرى وحسب النقطة للحالية
                            del pending_match_answers[game_id][other_uid]
                            storage.update_matchmaking_game(game_id, uid, won=True)
                            elapsed_for_other = other_time - (current_time - elapsed)
                            other_wpm = (word_count / max(abs(elapsed_for_other), 0.01)) * 60 + 20
                            # حفظ سرعة الخصم: مع تفعيل الدقة احفظ دائماً، بدون احفظ فقط عند 100%
                            other_accuracy_on = is_accuracy_enabled_for(other_uid)
                            should_save_other = other_accuracy_on or (accuracy is not None and accuracy == 100.0)
                            if should_save_other:
                                other_device_type = storage.get_device_type(other_uid)
                                storage.save_speed_for_section(other_uid, chosen_section, other_wpm)
                                # حفظ الصدارة: للأقسام الستة احفظ فقط عند دقة 100%
                                leaderboard_sections = ["كرر", "ويكي", "مس", "شك", "جب", "جش", "جمم"]
                                if chosen_section in leaderboard_sections and accuracy == 100.0:
                                    storage.update_score(other_uid, chosen_section, other_wpm, other_device_type)
                        # لا توجد إجابة معلقة - الإجابة الحالية فائزة
                        storage.update_matchmaking_game(game_id, uid, won=True)

                    # سجل الإجابة الحالية في المعلقات (إذا كانت فائزة أم خاسرة)
                    pending_match_answers[game_id][uid] = current_time

                    # حفظ السرعة للقسم: 
                    # - مع تفعيل الدقة: احفظ دائماً
                    # - بدون تفعيل الدقة: احفظ فقط عند دقة 100%
                    should_save_uid = user_accuracy_on or (accuracy is not None and accuracy == 100.0)
                    if should_save_uid:
                        device_type = storage.get_device_type(uid)
                        storage.save_speed_for_section(uid, chosen_section, wpm)
                        # حفظ الصدارة: للأقسام الستة احفظ فقط عند دقة 100%
                        # استثناء: جب حرفين لا يحسب في الصدارة
                        leaderboard_sections = ["كرر", "ويكي", "مس", "شك", "جب", "جش", "جمم"]
                        if chosen_section in leaderboard_sections and accuracy == 100.0:
                            # التحقق من أن جب حرفين لا يدخل الصدارة
                            if chosen_section == "جب" and user_jab_type.get(uid) == "حرفين":
                                pass  # لا تحفظ جب حرفين في الصدارة
                            else:
                                storage.update_score(uid, chosen_section, wpm, device_type)

                    # إعادة تحميل البيانات المحدثة
                    game = storage.get_matchmaking_game(game_id)
                    player1 = game["player1"]
                    player2 = game["player2"]

                    # النتيجة المحدثة
                    player_wins = player1['wins'] if player1['uid'] == uid else player2['wins']
                    opponent_uid = player2['uid'] if player1['uid'] == uid else player1['uid']
                    opponent_wins = player2['wins'] if player1['uid'] == uid else player1['wins']

                    # الحصول على اسم الخصم
                    opponent_name = player2['first_name'] if player1['uid'] == uid else player1['first_name']
                    opponent_username = player2.get('username') if player1['uid'] == uid else player1.get('username')
                    opponent_display = f"@{opponent_username}" if opponent_username else opponent_name

                    stats_msg = f"الإحصائيات:\n{mention}: {player_wins} | {opponent_display}: {opponent_wins}"

                    # إرسال الرسائل حسب الفائز والخاسر
                    if not is_loser:
                        # الفائز - يتلقى فقط السرعة والإحصائيات (بدون رسالة راحت عليك)
                        speed_msg = f"كفو يا {mention}\n\nسرعتك: {wpm:.2f} كلمة/دقيقة\nالوقت : {elapsed:.2f} ثانية"
                        if accuracy is not None and is_accuracy_enabled_for(uid):
                               speed_msg += f"\nالدقة : {accuracy}%"
                        await u.message.reply_text(speed_msg)
                        await u.message.reply_text(stats_msg)

                        # الخصم الخاسر - يتلقى فقط الرسالة والإحصائيات (بدون السرعة)
                        if opponent_uid != -1:
                            try:
                                await c.bot.send_message(opponent_uid, f"راحت عليك جاوب قبلك")
                                await c.bot.send_message(opponent_uid, stats_msg)
                            except:
                                pass
                    else:
                        # الخاسر - يتلقى فقط الرسالة والإحصائيات (بدون السرعة)
                        await u.message.reply_text(f"راحت عليك جاوب قبلك")
                        await u.message.reply_text(stats_msg)

                    # حذف جلسات كلا المستخدمين فوراً
                    storage.del_session(uid, typ)
                    if opponent_uid != -1:
                        storage.del_session(opponent_uid, typ)

                    # فحص الفائز (5)
                    if player_wins >= 5:
                        winner_msg = f"مبروك! فزت على {opponent_display} بـ 5 انتصارات!"
                        await u.message.reply_text(winner_msg)

                        # إرسال رسالة الخسارة للخاسر
                        if opponent_uid != -1:
                            try:
                                await c.bot.send_message(opponent_uid, f"خسرت المباراة!\n\n{opponent_display}: {opponent_wins}/5\n{mention}: {player_wins}/5")
                            except:
                                pass

                        storage.end_matchmaking_game(game_id)
                        # حذف الإجابات المعلقة عند انتهاء اللعبة
                        if game_id in pending_match_answers:
                            del pending_match_answers[game_id]
                    else:
                        # جولة جديدة - حذف الإجابات المعلقة من الجولة السابقة
                        if game_id in pending_match_answers:
                            pending_match_answers[game_id] = {}

                        # استدعاء من أي لاعب (القفل في send_next_match_sentence يمنع التكرار)
                        await asyncio.sleep(1.5)
                        asyncio.create_task(send_next_match_sentence(c, player1['uid'], player2['uid'], game_id, exclude_section=game.get("last_section")))
                    storage.save()
                    return
                else:
                    # تجاهل الإجابات الخاطئة - لا ترسل أي رسالة ولا تنهي الجلسة
                    # اللاعب ينتظر ليحاول مرة أخرى
                    return
        else:
            # حالة عادية (غير matchmaking) - احسب wpm هنا
            # استثناء "كرر" و "دبل وتر" و "خصص" - استخدام كلمات المستخدم
            # للأقسام الأخرى - استخدام كلمات الجملة الأصلية
            if typ in ["كرر", "دبل وتر", "خصص"]:
                word_count = count_words_for_wpm(text)
            else:
                word_count = count_words_for_wpm(orig)

            elapsed = max(elapsed, 0.01)
            wpm = (word_count / elapsed) * 60 + 20
            random_mode = True

            # فحص النسخ لصق والفواصل - ترفض الإجابة
            if not check_answer_validity(orig, text):
                storage.del_session(cid, typ)
                storage.save()
                return

        score_typ = 'فكك' if typ == 'فكك_تفكيك' else 'كشف' if typ == 'كشف_مايك' else (typ.split('_')[0] if '_' in typ else typ)

        # فحص مكافحة الغش
        if await check_and_ban_cheater(u, c, wpm, score_typ, accuracy):
            storage.del_session(cid, typ)
            storage.save()
            return

        device_type = storage.get_device_type(uid)
        old_score = storage.get_score(uid, score_typ, device_type)
        old_rank = storage.get_rank_in_leaderboard(uid, score_typ, device_type=device_type)

        # التحقق من الدقة وتحديد ما إذا كانت الجملة مقبولة تماماً
        round_data = storage.get_round(cid)
        user_accuracy_enabled = is_accuracy_enabled_for(uid)
        # تحقق سريع: هل كل كلمات الجملة الأصلية موجودة في إجابة المستخدم؟ (للسماح بالترتيب/التكرار)
        try:
            all_words_present_flag = False
            if typ.startswith("فر"):
                all_words_present_flag = is_all_words_present(orig, text, "persian")
            elif typ.startswith("E"):
                all_words_present_flag = is_all_words_present(orig, text, "english")
            elif typ.startswith("رق") or typ == "كشف_مايك":
                # للأرقام: استخدم match_numbers للتحقق من صحة الإجابة
                all_words_present_flag = match_numbers(orig, text)
            elif typ in ["كرر", "دبل", "دبل وتر", "خصص"]:
                try:
                    if '(' in orig and ')' in orig:
                        valid, _ = validate_repeat(orig, text)
                        all_words_present_flag = bool(valid)
                    else:
                        all_words_present_flag = is_all_words_present(orig, text, "arabic")
                except Exception:
                    all_words_present_flag = False
            else:
                all_words_present_flag = is_all_words_present(orig, text, "arabic")
        except Exception:
            all_words_present_flag = False

        # إذا كان التصحيح (تعديل) -> كل الكلمات موجودة لأن الناقص انكتب صح
        if correction_applied:
            all_words_present_flag = True

        # المنطق:
        # - في الجولات: قبول 100% فقط، تجاهل ما دون ذلك بدون إرسال رسالة
        # - عند تفعيل الدقة (خارج الجولات): قبول فقط إذا دقة >= 80%
        # - عند تعطيل الدقة (خارج الجولات): قبول فقط إذا كانت جميع الكلمات موجودة (أي ترتيب/تكرار)
        if round_data and not storage.is_round_finished(cid):
            # جولة نشطة - فقط 100% مقبول، الباقي يُتجاهل بدون رسالة
            is_fully_accepted = (accuracy == 100.0) if accuracy is not None else False
        elif user_accuracy_enabled:
            # خارج الجولات مع تفعيل الدقة - قبول فقط عند دقة >= 80%
            is_fully_accepted = (accuracy is not None and accuracy >= 80.0)
        else:
            # خارج الجولات مع تعطيل الدقة - قبول فقط إذا كانت جميع الكلمات موجودة (أي ترتيب/تكرار)
            is_fully_accepted = all_words_present_flag

        # إذا الإجابة ما قبلت نهائياً: سجلها كمحاولة خاطئة للمستخدم
        if not is_fully_accepted and not correction_applied:
            storage.record_wrong_attempt(cid, typ, uid, text)

        # إذا كانت الإجابة مقبولة (إرسال السرعة)، حفظ الصدارة
        if is_fully_accepted:
            # للأقسام الستة المرئية في الصدارة: احفظ دائماً إذا كانت الإجابة مقبولة
            # استثناء: جب حرفين لا يحسب في الصدارة
            leaderboard_sections = ["كرر", "ويكي", "مس", "شك", "جب", "جش", "جمم"]
            if score_typ in leaderboard_sections:
                # التحقق من أن جب حرفين لا يدخل الصدارة
                if score_typ == "جب" and user_jab_type.get(uid) == "حرفين":
                    pass  # لا تحفظ جب حرفين في الصدارة
                else:
                    storage.update_score(uid, score_typ, wpm, device_type)

                if wpm > old_score:
                    rank = storage.get_rank_in_leaderboard(uid, score_typ, device_type=device_type)
                    if rank and rank <= 3 and (not old_rank or old_rank > 3):
                        await u.message.reply_text(f"مبروك يا {usr if usr else name} - أنت الآن في المركز #{rank} بصدارة {device_type} في قسم {score_typ}")
            if random_mode:
                storage.add_correct_sentence(uid)

        mention = f"@{usr}" if usr else name

        round_data = storage.get_round(cid)
        if round_data:
            # التحقق: هل الجولة منتهية بالفعل؟
            if storage.is_round_finished(cid):
                # الجولة منتهية - أرسل السرعة بدون نقاط (فقط إذا الدقة مقبولة)
                # فحص الدقة إذا كانت مفعلة
                if user_accuracy_enabled and accuracy is not None and accuracy < 80.0:
                    # الدقة مفعلة وأقل من 80% - لا ترسل شي
                    storage.del_session(cid, typ)
                    storage.save()
                    return
                
                # إرسال السرعة بدون إضافة نقاط
                reply = f"كفو يا {mention}\n\nسرعتك: {wpm:.2f} كلمة/دقيقة\nالوقت : {elapsed:.2f} ثانية"
                if accuracy is not None and user_accuracy_enabled:
                    reply += f"\nالدقة : {accuracy}%"
                if correction_applied:
                    reply = "بعد التعديل ✅\n\n" + reply
                await u.message.reply_text(reply)
                storage.del_session(cid, typ)
                storage.save()
                return
            else:
                # الجولة مستمرة - أضف النقطة وتحقق من الفوز
                # فحص الدقة: لا تضيف نقطة إذا الدقة مفعلة وأقل من 80%
                if user_accuracy_enabled and accuracy is not None and accuracy < 80.0:
                    # الدقة مفعلة وأقل من 80% - لا ترسل شي ولا تضيف نقطة
                    storage.update_session_attempt(cid, typ)
                    return
                
                # تطبيق نفس منطق الدقة الموحد
                if is_fully_accepted:
                    storage.update_round_activity(cid)
                    wins = storage.add_win(cid, uid)
                    target = round_data['target']
                    wins_list = round_data.get('wins', {})

                    round_stats = "\n\nإحصائيات الجولة:\n"
                    sorted_wins = sorted(wins_list.items(), key=lambda x: x[1], reverse=True)
                    for i, (user_id, user_wins) in enumerate(sorted_wins, 1):
                        if i <= 3:
                            user_data = storage.data["users"].get(str(user_id), {})
                            user_name = user_data.get("first_name", "مستخدم")
                            user_username = user_data.get("username")
                            user_mention = f"@{user_username}" if user_username else user_name
                            round_stats += f"{i}. {user_mention}: {user_wins}/{target}\n"

                    if wins >= target:
                        reply = f"كفو يا {mention}\n\nسرعتك: {wpm:.2f} كلمة/دقيقة\nالوقت : {elapsed:.2f} ثانية\n"
                        if accuracy is not None and user_accuracy_enabled:
                               reply += f"الدقة : {accuracy}%\n"
                        reply += f"\n{round_stats}"
                        if correction_applied:
                            reply = "بعد التعديل ✅\n\n" + reply
                        await u.message.reply_text(reply)

                        # التحقق: هل الجولة بالفعل انتهت (أحدهم وصل للهدف بالفعل)؟
                        if not storage.get_round_extension_status(cid):
                            # الفوز الأول - إرسال الرسائل الاحتفالية
                            celebration_message = f"حيك يا {mention}، {mention} هو الفائز بالجولة\nمبروك!"
                            for _ in range(5):
                                await u.message.reply_text(celebration_message)
                                await asyncio.sleep(0.1)  # تأخير صغير بين الرسائل لتجنب حد معدل التليجرام

                            await u.message.reply_text("الجوله ذي انتهت لكن إذا ودك تكمل على نفس النتيجة اكتب: مدد \n\nاذا ما تبي اكتب : قفل جوله")

                        # وضع الجولة في حالة انتظار التمديد
                        storage.set_round_extension_status(cid, True)
                        storage.save()
                    else:
                        reply = f"كفو يا {mention}\n\nسرعتك: {wpm:.2f} كلمة/دقيقة\nالوقت : {elapsed:.2f} ثانية\n"
                        if accuracy is not None and user_accuracy_enabled:
                               reply += f"الدقة : {accuracy}%\n"
                        reply += f"التقدم: {wins}/{target}\n{round_stats}"
                        if correction_applied:
                            reply = "بعد التعديل ✅\n\n" + reply
                        await u.message.reply_text(reply)
                        # حذف الجلسة فقط إذا كانت مقبولة تماماً
                        storage.del_session(cid, typ)
                else:
                    # الإجابة غير مقبولة تماماً (دقة < 100%) - في الجولات يجب 100% فقط
                    # لا ترسل أي رسالة - فقط حدّث معلومات المحاولة
                    storage.update_session_attempt(cid, typ)
        else:
            # خارج الجولات
            # فحص الدقة إذا كانت مفعلة: لا ترسل إذا أقل من 80%
            if user_accuracy_enabled and accuracy is not None and accuracy < 80.0:
                # الدقة مفعلة وأقل من 80% - لا ترسل شي
                storage.update_session_attempt(cid, typ)
                return
            
            if is_fully_accepted:
                # الإجابة مقبولة - أرسل السرعة
                reply = f"كفو يا {mention}\n\nسرعتك: {wpm:.2f} كلمة/دقيقة\nالوقت : {elapsed:.2f} ثانية"
                if accuracy is not None and user_accuracy_enabled:
                    reply += f"\nالدقة : {accuracy}%"
                if correction_applied:
                    reply = "بعد التعديل ✅\n\n" + reply
                await u.message.reply_text(reply)
            else:
                # الإجابة غير مقبولة - لا ترسل شي، فقط اتركها معلقة للمحاولة مرة أخرى
                storage.update_session_attempt(cid, typ)
                return
            
            # حذف الجلسة بعد الإجابة المقبولة
            storage.del_session(cid, typ)


    storage.save()

async def periodic_save():
    while True:
        await asyncio.sleep(save_interval)
        storage.save()

async def periodic_cleanup():
    while True:
        await asyncio.sleep(3600)
        storage.cleanup()
        storage.save(force=True)

async def periodic_round_cleanup():
    while True:
        await asyncio.sleep(60)
        removed = storage.cleanup_inactive_rounds()
        if removed:
            print(f"Removed {len(removed)} inactive rounds")
            storage.save(force=True)

async def periodic_auto_cleanup():
    while True:
        await asyncio.sleep(30)
        removed = storage.cleanup_inactive_auto_modes()
        if removed:
            print(f"Removed {len(removed)} inactive auto modes")

async def periodic_stories_update():
    while True:
        await asyncio.sleep(24 * 60 * 60)
        try:
            if "قص" in managers:
                current_time = time.time()
                stories_manager = managers["قص"]
                if (current_time - stories_manager.last_update) >= stories_manager.update_interval:
                    print("[STORIES] Starting scheduled update...")
                    stories_manager.load()
                    print("[STORIES] Scheduled update completed")
        except Exception as e:
            print(f"[STORIES] Error in periodic update: {e}")

async def periodic_nass_update():
    if "نص" not in managers:
        return

    nass_manager = managers["نص"]

    print("[NASS] Starting initial content load...")
    try:
        await asyncio.to_thread(nass_manager.load)
        print("[NASS] Initial load completed")
    except Exception as e:
        print(f"[NASS] Error in initial load: {e}")

    while True:
        await asyncio.sleep(3600)
        try:
            if nass_manager.needs_update():
                print("[NASS] Starting scheduled update...")
                await asyncio.to_thread(nass_manager.load)
                print("[NASS] Scheduled update completed")
        except Exception as e:
            print(f"[NASS] Error in periodic update: {e}")

async def periodic_tibb_update():
    """تحديث دوري لمحتوى قسم طب"""
    if "طب" not in managers:
        return

    tibb_manager = managers["طب"]

    print("[TIBB] Starting initial content load...")
    try:
        await asyncio.to_thread(tibb_manager.load)
        print("[TIBB] Initial load completed")
    except Exception as e:
        print(f"[TIBB] Error in initial load: {e}")

    while True:
        await asyncio.sleep(3600)
        try:
            if tibb_manager.needs_update():
                print("[TIBB] Starting scheduled update...")
                await asyncio.to_thread(tibb_manager.load)
                print("[TIBB] Scheduled update completed")
        except Exception as e:
            print(f"[TIBB] Error in periodic update: {e}")

async def display_leaderboard(query, device_type):
    """عرض الصدارة حسب نوع الجهاز"""
    types = ["كرر", "ويكي", "مس", "شك", "جب", "جش", "حر"]
    sections = []

    for typ in types:
        lb = storage.get_leaderboard(typ, device_type=device_type)
        if lb:
            s = f"<b>{typ}</b>\n"
            # عرض أول 5 فقط لكل قسم
            for i, (uid_str, username, first_name, wpm) in enumerate(lb[:5], 1):
                display = f"@{username}" if username else first_name
                s += f"{i}. {display}: {wpm:.2f} WPM\n"
            sections.append(s)

    if sections:
        msg = f"<b>صدارة {device_type}</b>\n\n" + "\n".join(sections)
        await query.edit_message_text(msg, parse_mode="HTML")
    else:
        await query.edit_message_text(f"لا توجد نتائج في صدارة {device_type}")

async def display_online_leaderboard_merged():
    """عرض صدارة الاون لاين (1v1) مدموجة (جوال + خارجي معاً)"""
    players = []

    # جمع بيانات الانتصارات من جميع المستخدمين بدون تفريق
    for uid_str in storage.data.get("users", {}).keys():
        try:
            uid = int(uid_str)
            user_data = storage.data["users"][uid_str]

            stats = storage.get_online_stats(uid)
            wins = stats.get("wins", 0)

            if wins > 0:
                username = user_data.get("username")
                first_name = user_data.get("first_name", "مستخدم")
                display = f"@{username}" if username else first_name
                players.append((uid, display, wins))
        except:
            continue

    # ترتيب من الأعلى انتصارات للأقل
    players.sort(key=lambda x: x[2], reverse=True)

    if players:
        msg = "<b>صدارة الاون لاين</b>\n\n"
        for i, (uid, display, wins) in enumerate(players[:20], 1):
            msg += f"{i}. {display}: {wins} انتصار\n"
        return msg
    else:
        return "لا توجد نتائج في صدارة الاون لاين"

async def handle_callback(u: Update, c: ContextTypes.DEFAULT_TYPE):
    query = u.callback_query
    if not query or not query.from_user:
        return

    if not await require_channel_membership(u, c):
        return

    uid = query.from_user.id
    cid = u.effective_chat.id if u.effective_chat else 0
    if not uid or not cid:
        return

    # معالجة اختيار device type عند التسجيل - من الصدارة
    if query.data == "device_type_جوال_leaderboard":
        if storage.has_device_type(uid):
            await query.answer("أنت اخترت جهازك بالفعل", show_alert=True)
            return
        await query.answer()
        # تسجيل المستخدم في الملف إذا لم يكن موجود
        if str(uid) not in storage.data.get("users", {}):
            storage.add_user(uid, query.from_user.username, query.from_user.first_name)
        storage.save_device_type(uid, "جوال")
        await query.edit_message_text("تصنيفك راح يكون في صدارة الجوال ما يمديك تغير ، اتمنى لو بتجيب رقم يكون مصور")

        # التحقق من نوع الطلب (صدارة عادية أم ايدي صدارة)
        leaderboard_type = leaderboard_state.pop(uid, None)

        if leaderboard_type == "ايدي_صدارة":
            # إرسال ايدي الصدارة
            user_device_type = "جوال"
            types = ["كرر", "ويكي", "مس", "شك", "جب", "جش"]
            sections = []
            for typ in types:
                lb = storage.get_leaderboard(typ, device_type=user_device_type)
                if lb:
                    s = f"<b>{typ}</b>\n"
                    for i, (uid_str, username, first_name, wpm) in enumerate(lb[:5], 1):
                        display = f"@{username}" if username else first_name
                        s += f"{i}. {display} (ID: {uid_str}): {wpm:.2f} WPM\n"
                    sections.append(s)
            if sections:
                msg = "<b>ايدي الصدارة - الخمسة الأوائل من كل قسم</b>\n\n" + "\n".join(sections)
                await u.callback_query.message.reply_text(msg, parse_mode="HTML")
            else:
                await u.callback_query.message.reply_text("لا توجد نتائج بعد")
        else:
            # إرسال رسالة الصدارة العادية
            keyboard = [
                [InlineKeyboardButton("صدارة الخارجي", callback_data="leaderboard_خارجي")],
                [InlineKeyboardButton("صدارة الجوال", callback_data="leaderboard_جوال")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await u.callback_query.message.reply_text(
                "ارحب اختر من الازرار وش تبي صدارة الخارجي ولا الجوال؟\n\n"
                "اتمنى اي رقم راح يجيبه شخص يكون مصور واي رقم عالي بدون تصوير او اثبات بينشال من التوب",
                reply_markup=reply_markup
            )
        return

    if query.data == "device_type_خارجي_leaderboard":
        if storage.has_device_type(uid):
            await query.answer("أنت اخترت جهازك بالفعل", show_alert=True)
            return
        await query.answer()
        # تسجيل المستخدم في الملف إذا لم يكن موجود
        if str(uid) not in storage.data.get("users", {}):
            storage.add_user(uid, query.from_user.username, query.from_user.first_name)
        storage.save_device_type(uid, "خارجي")
        await query.edit_message_text("تصنيفك راح يكون في صدارة الخارجي ما يمديك تغير ، اتمنى لو بتجيب رقم يكون مصور")

        # التحقق من نوع الطلب (صدارة عادية أم ايدي صدارة)
        leaderboard_type = leaderboard_state.pop(uid, None)

        if leaderboard_type == "ايدي_صدارة":
            # إرسال ايدي الصدارة
            user_device_type = "خارجي"
            types = ["كرر", "ويكي", "مس", "شك", "جب", "جش"]
            sections = []
            for typ in types:
                lb = storage.get_leaderboard(typ, device_type=user_device_type)
                if lb:
                    s = f"<b>{typ}</b>\n"
                    for i, (uid_str, username, first_name, wpm) in enumerate(lb[:5], 1):
                        display = f"@{username}" if username else first_name
                        s += f"{i}. {display} (ID: {uid_str}): {wpm:.2f} WPM\n"
                    sections.append(s)
            if sections:
                msg = "<b>ايدي الصدارة - الخمسة الأوائل من كل قسم</b>\n\n" + "\n".join(sections)
                await u.callback_query.message.reply_text(msg, parse_mode="HTML")
            else:
                await u.callback_query.message.reply_text("لا توجد نتائج بعد")
        else:
            # إرسال رسالة الصدارة العادية
            keyboard = [
                [InlineKeyboardButton("صدارة الخارجي", callback_data="leaderboard_خارجي")],
                [InlineKeyboardButton("صدارة الجوال", callback_data="leaderboard_جوال")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await u.callback_query.message.reply_text(
                "ارحب اختر من الازرار وش تبي صدارة الخارجي ولا الجوال؟\n\n"
                "اتمنى اي رقم راح يجيبه شخص يكون مصور واي رقم عالي بدون تصوير او اثبات بينشال من التوب",
                reply_markup=reply_markup
            )
        return

    # معالجة اختيار device type عند التسجيل - من أي أمر عادي
    if query.data == "device_type_جوال":
        if storage.has_device_type(uid):
            await query.answer("أنت اخترت جهازك بالفعل", show_alert=True)
            return
        await query.answer()
        # تسجيل المستخدم في الملف إذا لم يكن موجود
        if str(uid) not in storage.data.get("users", {}):
            storage.add_user(uid, query.from_user.username, query.from_user.first_name)
        storage.save_device_type(uid, "جوال")
        await query.edit_message_text("تصنيفك راح يكون في صدارة الجوال ما يمديك تغير ، اتمنى لو بتجيب رقم يكون مصور")
        await show_bot_sections(u, c)
        return

    if query.data == "device_type_خارجي":
        if storage.has_device_type(uid):
            await query.answer("أنت اخترت جهازك بالفعل", show_alert=True)
            return
        await query.answer()
        # تسجيل المستخدم في الملف إذا لم يكن موجود
        if str(uid) not in storage.data.get("users", {}):
            storage.add_user(uid, query.from_user.username, query.from_user.first_name)
        storage.save_device_type(uid, "خارجي")
        await query.edit_message_text("تصنيفك راح يكون في صدارة الخارجي ما يمديك تغير ، اتمنى لو بتجيب رقم يكون مصور")
        await show_bot_sections(u, c)
        return

    await query.answer()

    # معالجة اختيار نوع التخصيص
    if query.data == "cust_type_normal":
        if uid in customization_state:
            customization_state[uid]["data"]["type"] = "normal"
            customization_state[uid]["stage"] = "waiting_words"
            await query.edit_message_text("أرسل الكلمات اللي تبي تحفظها")
        return

    if query.data == "cust_type_repeat":
        if uid in customization_state:
            customization_state[uid]["data"]["type"] = "repeat"
            customization_state[uid]["stage"] = "waiting_words"
            await query.edit_message_text("أرسل الكلمات اللي تبي تحفظها")
        return

    # معالجة تغيير device type من أمر صنف (للمالك الأساسي فقط)
    if query.data == "change_device_type_جوال":
        if not storage.is_main_owner(uid):
            await query.answer("هذا الأمر للمالك الأساسي فقط", show_alert=True)
            return
        storage.save_device_type(uid, "جوال")
        await query.edit_message_text(" تم تغيير الصنف إلى: جوال")
        return

    if query.data == "change_device_type_خارجي":
        if not storage.is_main_owner(uid):
            await query.answer("هذا الأمر للمالك الأساسي فقط", show_alert=True)
            return
        storage.save_device_type(uid, "خارجي")
        await query.edit_message_text(" تم تغيير الصنف إلى: خارجي")
        return

    # معالجة اختيار نوع الصدارة
    if query.data == "leaderboard_جوال":
        await display_leaderboard(query, "جوال")
        return

    if query.data == "leaderboard_خارجي":
        await display_leaderboard(query, "خارجي")
        return

    if query.data == "hide_message":
        await query.delete_message()
        return

    if query.data == "show_commands":
        await show_bot_commands(u, c, is_callback=True)
        return

    if query.data == "show_sections":
        await show_bot_sections(u, c, is_callback=True)
        return

    if query.data == "verify_channel_access":
        await query.answer()
        if await require_channel_membership(u, c):
            await show_bot_sections(u, c, is_callback=True)
        return

    if query.data == "رق_لفظ":
        storage.save_number_type(uid, "لفظ")
        pref_count = storage.get_preference(uid, "رق") or random.randint(7, 20)
        sent = generate_random_sentence(uid, NUMBER_WORDS, pref_count, pref_count, "رق")
        storage.del_session(cid, "رق")
        storage.save_session(uid, cid, "رق", sent, time.time(), sent=True)
        display = format_display(sent)
        await query.edit_message_text(display)
        asyncio.create_task(trigger_speed_bot_if_enabled(c, cid, sent, "رق"))
        return

    if query.data == "رق_صعبة":
        storage.save_number_type(uid, "صعبة")
        numbers, numbers_str = generate_hard_numbers_sentence()
        storage.del_session(cid, "رق_صعبة")
        storage.save_session(uid, cid, "رق_صعبة", numbers_str, time.time(), sent=True)
        await query.edit_message_text(f"اكتب الأرقام لفظاً:\n\n{numbers_str}")
        return

    if query.data == "رق_سهلة":
        storage.save_number_type(uid, "سهلة")
        numbers, numbers_str = generate_easy_numbers_sentence()
        storage.del_session(cid, "رق_سهلة")
        storage.save_session(uid, cid, "رق_سهلة", numbers_str, time.time(), sent=True)
        await query.edit_message_text(f"اكتب الأرقام لفظاً:\n\n{numbers_str}")
        return

    # ============ معالجة أزرار كشف ============
    if query.data == "كشف_براد":
        user_kashf_type[uid] = "براد"
        pref_count = storage.get_preference(uid, "كشف_عدد") or random.randint(7, 20)
        sent = managers["نص"].get() if "نص" in managers else managers["ويكي"].get()
        words = sent.split()
        if len(words) > pref_count:
            words = words[:pref_count]
        separator = random.choice(ARABIC_LETTERS)
        user_kashf_separator[uid] = separator
        display_text = f" {separator} ".join(words)
        original_text = " ".join(words)
        storage.del_session(cid, "كشف_براد")
        storage.save_session(uid, cid, "كشف_براد", original_text, time.time(), sent=True)
        await query.edit_message_text("اكتب الكلمات بدون الحرف اللي يفصل بينها")
        await asyncio.sleep(0.5)
        await query.message.reply_text(display_text)
        return

    if query.data == "كشف_مايك":
        await query.edit_message_text("اذا تبي تقفط واحد مايك انه يلعب نزل له من قسم رق زر لفظ راح ينزل لك كلمات على شكل حروف اذا كتبها هو ارقام فهو نسوخي لو كتبها لفظ فهو مب نسوخي او مايك وبرضو جرب عليه باقي الاختبارات عشان تشوف لو الشخص مستخدم طريقة غش ثانيه")
        return

    if query.data == "كشف_نسوخي":
        user_kashf_type[uid] = "نسوخي"
        pref_count = storage.get_preference(uid, "كشف_عدد") or random.randint(7, 15)
        sent = managers["ويكي"].get()
        words = sent.split()
        if len(words) > pref_count:
            words = words[:pref_count]
        display_text = "/ ".join(words) + "/"
        original_text = " ".join(words)
        storage.del_session(cid, "كشف_نسوخي")
        storage.save_session(uid, cid, "كشف_نسوخي", original_text, time.time(), sent=True)
        await query.edit_message_text(display_text)
        return
    # ============ نهاية معالجة أزرار كشف ============

    # معالجة استعادة مستخدم مع الأرقام السابقة
    if query.data and query.data.startswith("restore_with_scores_"):
        target_uid = int(query.data.split("_")[-1])

        if not has_permission(uid, "admin"):
            await query.answer("هذا الإجراء للمشرفين فقط", show_alert=True)
            return

        success = storage.restore_from_leaderboard(target_uid, restore_scores=True)
        if success:
            target_user = storage.data["users"].get(str(target_uid), {})
            target_name = f"@{target_user.get('username')}" if target_user.get('username') else target_user.get('first_name', 'المستخدم')
            await query.edit_message_text(f" تم استعادة {target_name} مع كامل أرقامه السابقة!")
            storage.save(force=True)
        else:
            await query.answer("لم يتمكن من استعادة المستخدم", show_alert=True)
        return

    # معالجة استعادة مستخدم بدون الأرقام السابقة
    if query.data and query.data.startswith("restore_without_scores_"):
        target_uid = int(query.data.split("_")[-1])

        if not has_permission(uid, "admin"):
            await query.answer("هذا الإجراء للمشرفين فقط", show_alert=True)
            return

        success = storage.restore_from_leaderboard(target_uid, restore_scores=False)
        if success:
            target_user = storage.data["users"].get(str(target_uid), {})
            target_name = f"@{target_user.get('username')}" if target_user.get('username') else target_user.get('first_name', 'المستخدم')
            await query.edit_message_text(f" تم استعادة {target_name} في الصدارة (بدون أرقام سابقة)!")
            storage.save(force=True)
        else:
            await query.answer("لم يتمكن من استعادة المستخدم", show_alert=True)
        return

    if query.data and query.data.startswith("end_round_"):
        cid = int(query.data.split("_")[2])

        round_data = storage.get_round(cid)
        if round_data:
            wins_list = round_data.get('wins', {})
            if wins_list:
                msg = "نتائج الجولة:\n\n"
                sorted_wins = sorted(wins_list.items(), key=lambda x: x[1], reverse=True)
                for i, (user_id, wins) in enumerate(sorted_wins, 1):
                    user_data = storage.data["users"].get(str(user_id), {})
                    user_name = user_data.get("first_name", "مستخدم")
                    user_username = user_data.get("username")
                    mention = f"@{user_username}" if user_username else user_name
                    msg += f"{i}. {mention}: {wins} فوز\n"
                await query.edit_message_text(msg)

            storage.end_round(cid)
            if query.message:
                await query.message.reply_text("تم إنهاء الجولة")
        else:
            await query.edit_message_text("لا توجد جولة نشطة حالياً")

async def handle_register_device(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """معالج تسجيل مستخدم جديد مع نوع الجهاز - للمالك الأساسي فقط"""
    if not u.effective_user or not u.message:
        print("[REGISTER] No user or message")
        return False
    
    uid = u.effective_user.id
    text = u.message.text.strip()
    print(f"[REGISTER] Handler called with text: {text}")
    
    # التحقق من أن المستخدم هو المالك الأساسي
    if not storage.is_main_owner(uid):
        await u.message.reply_text("هذا الأمر للمالك الأساسي فقط")
        print(f"[REGISTER] User {uid} is not main owner")
        return True
    
    # التحقق من أن الرسالة تبدأ بـ "تسجيل"
    if not text.startswith("تسجيل"):
        print(f"[REGISTER] Text doesn't start with 'تسجيل': {text}")
        return False
    
    print(f"[REGISTER] Processing command: {text}")
    
    # استخراج نوع الجهاز والهدف من النص
    parts = text.split(maxsplit=2)
    if len(parts) < 3:
        await u.message.reply_text("الاستخدام:\nتسجيل [الأيدي أو اليوزر] [جوال/خارجي]\n\nمثال:\nتسجيل 5562144078 جوال\nتسجيل @username خارجي")
        return True
    
    target = parts[1]
    device_type = parts[2]
    
    print(f"[REGISTER] Target: {target}, Device type: {device_type}")
    
    # التحقق من أن نوع الجهاز صحيح
    if device_type not in ["جوال", "خارجي"]:
        await u.message.reply_text("نوع الجهاز غير صحيح. استخدم: 'جوال' أو 'خارجي'")
        return True
    
    target_uid = None
    target_name = None
    
    # البحث عن المستخدم بالأيدي أو اليوزر
    if target.isdigit():
        target_uid = int(target)
        user_data = storage.data.get("users", {}).get(target, {})
        target_name = f"@{user_data.get('username')}" if user_data.get('username') else user_data.get('first_name', target)
        print(f"[REGISTER] Found by ID: {target_uid}, name: {target_name}")
    else:
        # إزالة @ إذا كانت موجودة
        username = target.lstrip('@')
        print(f"[REGISTER] Searching for username: {username}")
        target_uid = get_user_id_by_username(username)
        if target_uid:
            user_data = storage.data.get("users", {}).get(str(target_uid), {})
            target_name = f"@{username}"
            print(f"[REGISTER] Found user: {target_uid}, name: {target_name}")
        else:
            print(f"[REGISTER] Username not found: {username}")
            await u.message.reply_text(f"لم أجد مستخدماً باسم @{username}")
            return True
    
    if not target_uid:
        await u.message.reply_text(f"لم أجد المستخدم برقم {target}")
        return True
    
    # حفظ نوع الجهاز الجديد
    storage.save_device_type(target_uid, device_type)
    print(f"[REGISTER] Registered device type {device_type} for user {target_uid}")
    
    # رسالة التأكيد
    type_display = "جوال" if device_type == "جوال" else "خارجي"
    await u.message.reply_text(f"تم تسجيل {target_name} كـ {type_display}")
    
    print(f"[REGISTER] Owner {uid} registered device type for {target_uid}: {device_type}")
    return True

async def handle_delete_leaderboard(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """معالج حذف المستخدم من صدارة قسم محدد مع نوع جهاز محدد"""
    if not u.effective_user or not u.message:
        print("[DELETE_LB] No user or message")
        return False
    
    uid = u.effective_user.id
    text = u.message.text.strip()
    print(f"[DELETE_LB] Handler called with text: {text}")
    
    # التحقق من الصلاحيات (الادمن فما فوق)
    if not has_permission(uid, "admin"):
        await u.message.reply_text("هذا الأمر للمشرفين والملاك فقط")
        print(f"[DELETE_LB] User {uid} no permission")
        return True
    
    # النمط: حذف [target] من صدارة [device_type] قسم [section]
    # مثال: حذف 5562144078 من صدارة جوال قسم ويكي
    #      حذف @username من صدارة خارجي قسم كرر
    
    # استخراج الأجزاء بناءً على الكلمات المفتاحية
    if "من صدارة" not in text or "قسم" not in text:
        await u.message.reply_text("الاستخدام:\nحذف [الأيدي أو اليوزر] من صدارة [جوال/خارجي] قسم [اسم القسم]\n\nمثال:\nحذف 5562144078 من صدارة جوال قسم ويكي\nحذف @username من صدارة خارجي قسم كرر")
        return True
    
    try:
        # تقسيم النص بناءً على الفواصل المفتاحية
        parts = text.split(" من صدارة ")
        if len(parts) != 2:
            await u.message.reply_text("صيغة الأمر غير صحيحة")
            return True
        
        target = parts[0].replace("حذف", "").strip()
        remaining = parts[1]
        
        # تقسيم الجزء المتبقي: [device_type] قسم [section]
        device_and_section = remaining.split(" قسم ")
        if len(device_and_section) != 2:
            await u.message.reply_text("صيغة الأمر غير صحيحة")
            return True
        
        device_type = device_and_section[0].strip()
        section = device_and_section[1].strip()
        
        print(f"[DELETE_LB] Target: {target}, Device: {device_type}, Section: {section}")
        
        # التحقق من نوع الجهاز
        if device_type not in ["جوال", "خارجي"]:
            await u.message.reply_text("نوع الجهاز غير صحيح. استخدم: 'جوال' أو 'خارجي'")
            return True
        
        # التحقق من اسم القسم
        valid_sections = ["ويكي", "مس", "جمم", "صج", "شك", "جش", "قص", "نص", "طب", "كرر", "شرط", "فكك", "دبل", "تر", "عكس", "فر", "E", "رق", "حر", "جب"]
        if section not in valid_sections:
            await u.message.reply_text(f"القسم غير صحيح. الأقسام المتاحة:\n{', '.join(valid_sections)}")
            return True
        
        target_uid = None
        target_name = None
        
        # البحث عن المستخدم
        if target.isdigit():
            target_uid = int(target)
            user_data = storage.data.get("users", {}).get(target, {})
            target_name = f"@{user_data.get('username')}" if user_data.get('username') else user_data.get('first_name', target)
            print(f"[DELETE_LB] Found by ID: {target_uid}, name: {target_name}")
        else:
            username = target.lstrip('@')
            print(f"[DELETE_LB] Searching for username: {username}")
            target_uid = get_user_id_by_username(username)
            if target_uid:
                user_data = storage.data.get("users", {}).get(str(target_uid), {})
                target_name = f"@{username}"
                print(f"[DELETE_LB] Found user: {target_uid}, name: {target_name}")
            else:
                print(f"[DELETE_LB] Username not found: {username}")
                await u.message.reply_text(f"لم أجد مستخدماً باسم @{username}")
                return True
        
        if not target_uid:
            await u.message.reply_text(f"لم أجد المستخدم برقم {target}")
            return True
        
        # حذف الأرقام من القسم المحدد
        success = storage.remove_section_scores(target_uid, section, device_type)
        
        if success:
            await u.message.reply_text(f"تم حذف {target_name} من صدارة {device_type} قسم {section}")
            print(f"[DELETE_LB] Admin {uid} removed {target_uid} from {device_type} leaderboard section {section}")
        else:
            await u.message.reply_text(f"لم يتم العثور على أرقام لـ {target_name} في صدارة {device_type} قسم {section}")
            print(f"[DELETE_LB] No scores found for {target_uid} in {device_type} {section}")
        
        return True
        
    except Exception as e:
        print(f"[DELETE_LB] Error: {e}")
        await u.message.reply_text("حدث خطأ في معالجة الأمر")
        return True

async def handle_device_type_change(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """معالج تغيير نوع جهاز المستخدم من الرسائل"""
    if not u.effective_user or not u.message:
        print("[DEVICE_TYPE] No user or message")
        return False
    
    text = u.message.text.strip()
    print(f"[DEVICE_TYPE] Handler called with text: {text}")
    
    # التحقق من أن الرسالة تبدأ بـ "تغيير" وتحتوي على نوع جهاز
    if not text.startswith("تغيير"):
        print(f"[DEVICE_TYPE] Text doesn't start with 'تغيير': {text}")
        return False
    
    print(f"[DEVICE_TYPE] Processing command: {text}")
    
    uid = u.effective_user.id
    
    # التحقق من الصلاحيات (المالك أو الادمن فقط)
    if not has_permission(uid, "admin"):
        await u.message.reply_text("هذا الأمر للمشرفين والملاك فقط")
        print(f"[DEVICE_TYPE] User {uid} no permission")
        return True
    
    # استخراج نوع الجهاز والهدف من النص
    parts = text.split(maxsplit=2)
    if len(parts) < 3:
        await u.message.reply_text("الاستخدام:\nتغيير جوال [الأيدي أو اليوزر]\nتغيير خارجي [الأيدي أو اليوزر]\n\nمثال:\nتغيير جوال 5562144078\nتغيير جوال @username")
        return True
    
    device_type = parts[1]
    target = parts[2]
    
    print(f"[DEVICE_TYPE] Device type: {device_type}, Target: {target}")
    
    # التحقق من أن نوع الجهاز صحيح
    if device_type not in ["جوال", "خارجي"]:
        await u.message.reply_text("نوع الجهاز غير صحيح. استخدم: 'جوال' أو 'خارجي'")
        return True
    
    target_uid = None
    target_name = None
    
    # البحث عن المستخدم بالأيدي أو اليوزر
    if target.isdigit():
        target_uid = int(target)
        user_data = storage.data.get("users", {}).get(str(target_uid), {})
        target_name = f"@{user_data.get('username')}" if user_data.get('username') else user_data.get('first_name', target)
        print(f"[DEVICE_TYPE] Found by ID: {target_uid}, name: {target_name}")
    else:
        # إزالة @ إذا كانت موجودة
        username = target.lstrip('@')
        print(f"[DEVICE_TYPE] Searching for username: {username}")
        target_uid = get_user_id_by_username(username)
        if target_uid:
            user_data = storage.data.get("users", {}).get(str(target_uid), {})
            target_name = f"@{username}"
            print(f"[DEVICE_TYPE] Found user: {target_uid}, name: {target_name}")
        else:
            print(f"[DEVICE_TYPE] Username not found: {username}")
            await u.message.reply_text(f"لم أجد مستخدماً باسم @{username}")
            return True
    
    if not target_uid:
        await u.message.reply_text(f"لم أجد المستخدم برقم {target}")
        return True
    
    # حذف أي تصنيف سابق ثم حفظ النوع الجديد
    storage.save_device_type(target_uid, device_type)
    print(f"[DEVICE_TYPE] Saved device type {device_type} for user {target_uid}")
    
    # رسالة التأكيد
    type_display = "جوال" if device_type == "جوال" else "خارجي"
    await u.message.reply_text(f"تم تصنيف {target_name} كـ {type_display}")
    
    print(f"[DEVICE_TYPE] Admin {uid} changed device type for {target_uid} to {device_type}")
    return True

async def post_init(application: Application):
    await init_http_session()
    asyncio.create_task(periodic_save())
    asyncio.create_task(periodic_cleanup())
    asyncio.create_task(periodic_round_cleanup())
    asyncio.create_task(periodic_auto_cleanup())
    asyncio.create_task(periodic_stories_update())
    asyncio.create_task(periodic_nass_update())
    asyncio.create_task(periodic_tibb_update())
    print("[BACKGROUND] Started background tasks: periodic_save, periodic_cleanup, periodic_round_cleanup, periodic_auto_cleanup, periodic_stories_update, periodic_nass_update, periodic_tibb_update")
    print("[HTTP] Initialized shared HTTP session")

async def shutdown(application: Application):
    print("[SHUTDOWN] Saving final data...")
    storage.save(force=True)
    print("[HTTP] Closing HTTP session...")
    await close_http_session()
    print("[SHUTDOWN] Cleanup complete")
    # Cancel all pending tasks gracefully
    try:
        for task in asyncio.all_tasks():
            if not task.done():
                task.cancel()
    except:
        pass

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN environment variable not set!")
        return

    app = Application.builder().token(BOT_TOKEN).concurrent_updates(8).post_init(post_init).post_shutdown(shutdown).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("restore", cmd_restore))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    # معالج لأوامر تغيير نوع الجهاز - يجب أن يكون قبل handle_msg
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^تغيير\s+(جوال|خارجي)\s+"), handle_device_type_change))
    
    # معالج الرسائل العادية
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))

    print("Bot starting...")
    while True:
        try:
            app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        except KeyboardInterrupt:
            print("[SHUTDOWN] Keyboard interrupt received")
            break
        except Exception as e:
            print(f"[ERROR] Bot error: {e}")
            print("[INFO] Restarting bot in 5 seconds...")
            import time
            time.sleep(5)

if __name__ == '__main__':
    main()
