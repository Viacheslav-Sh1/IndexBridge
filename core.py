"""
ВСЯ бизнес-логика: конфигурация, фильтры, студии, парсинг, конвертация.
Перенесено из app.py без изменений для поддержки Prowlarr.
"""
import os
import re
import logging
import math
import unicodedata
from typing import List, Tuple, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

# ==================== КОНФИГУРАЦИЯ ====================

PROXY_API_KEY = os.getenv("PROXY_API_KEY")

# Новый способ: единый список NAMES
PROVIDER_NAMES = os.getenv("NAMES", "").split(",")

# Старые переменные для обратной совместимости
JACKETT_NAMES = os.getenv("JACKETT_NAMES", "").split(",")
PROWLARR_NAMES = os.getenv("PROWLARR_NAMES", "").split(",")

# Объединяем все имена из всех источников
ALL_NAMES = set()
for name in PROVIDER_NAMES + JACKETT_NAMES + PROWLARR_NAMES:
    name = name.strip()
    if name:
        ALL_NAMES.add(name)

JACKETTS = {}
PROWLARRS = {}

for name in ALL_NAMES:
    name = name.strip()
    # Проверяем Jackett переменные
    jackett_url = os.getenv(f"JACKETT_{name}_URL")
    jackett_apikey = os.getenv(f"JACKETT_{name}_API_KEY")
    
    # Проверяем Prowlarr переменные
    prowlarr_url = os.getenv(f"PROWLARR_{name}_URL")
    prowlarr_apikey = os.getenv(f"PROWLARR_{name}_API_KEY")
    
    if jackett_url and jackett_apikey:
        JACKETTS[name] = {"url": jackett_url.rstrip('/'), "apikey": jackett_apikey}
        logger.info(f"✅ Jackett: {name} → {jackett_url}")
    
    if prowlarr_url and prowlarr_apikey:
        PROWLARRS[name] = {"url": prowlarr_url.rstrip('/'), "apikey": prowlarr_apikey}
        logger.info(f"✅ Prowlarr: {name} → {prowlarr_url}")

if not PROXY_API_KEY:
    raise RuntimeError("❌ PROXY_API_KEY не задан!")

if not JACKETTS and not PROWLARRS:
    raise RuntimeError("❌ Не настроено ни одного провайдера! Укажите NAMES и для каждого JACKETT_{name}_URL или PROWLARR_{name}_URL")

# ==================== ФИЛЬТРЫ ====================

FILTER_MIN_SEEDERS = int(os.getenv("FILTER_MIN_SEEDERS", "1"))
FILTER_MAX_SEEDERS = int(os.getenv("FILTER_MAX_SEEDERS", "0"))
FILTER_MIN_PEERS = int(os.getenv("FILTER_MIN_PEERS", "0"))
FILTER_LANGUAGES = os.getenv("FILTER_LANGUAGES", "").split(",")
FILTER_VOICES = os.getenv("FILTER_VOICES", "").split(",")
FILTER_BLACKLIST_TITLES = os.getenv("FILTER_BLACKLIST_TITLES", "").split(",")
FILTER_QUALITY_MIN = int(os.getenv("FILTER_QUALITY_MIN", "0"))
FILTER_QUALITY_MAX = int(os.getenv("FILTER_QUALITY_MAX", "9999"))

# ==================== СТУДИИ ОЗВУЧКИ ====================

RUSSIAN_STUDIOS = {
    "LostFilm": [r'\blostfilm\b', r'\blф\b', r'\blost\b'],
    "Red Head Sound": [r'red head sound', r'redhead', r'r\.h\.s', r'рхс'],
    "Pifagor": [r'pifagor', r'пифагор'],
    "WStudio": [r'\bwstudio\b', r'\bws\b'],
    "HDRezka": [r'\bhdrezka\b'],
    "HDRezka Studio": [r'hdrezka studio'],
    "TVShows": [r'\btvshows\b'],
    "Сербин": [r'сербин'],
    "LE-Production": [r'le-production', r'leprod', r'лепродакшн'],
    "Кубик в Кубе": [r'кубик в кубе', r'\bквк\b', r'kubik v kube'],
    "AlexFilm": [r'alexfilm', r'алексфильм'],
    "Новая Студия": [r'новая студия', r'new studio'],
    "Студия Бай": [r'студия бай', r'studio bay'],
    "Golden Films": [r'golden films', r'голден'],
    "Ozon Studio": [r'ozon studio'],
    "Sony Sci-Fi": [r'sony sci-fi'],
    "Парапапарам": [r'парапапарам'],
    "HTB": [r'\bhtb\b'],
    "Jaskier": [r'\bjaskier\b'],
    "ПМ": [r'\bпм\b'],
    "Zone Vision": [r'zone vision', r'зон вижн'],
    "Кириллица": [r'кириллица', r'кирил'],
    "Contentica": [r'contentica', r'контэнтика'],
    "NewComers": [r'newcomers', r'ньюкамерс'],
    "Amedia": [r'amedia', r'амедиа'],
    "ЛМ": [r'\bлм\b'],
    "СТ": [r'\bст\b'],
    "Так Треба Продакшн": [r'так треба', r'tak treba', r'такнадо'],
    "Treba Production": [r'treba production'],
    "Jetvis Studio": [r'jetvis studio', r'jetvis'],
    "Jetvis": [r'\bjetvis\b'],
}

UKRAINIAN_STUDIOS = {
    "UA озвучка": [r'uaозвучка', r'ua озвучка'],
    "Студия 1+1": [r'1\+1', r'студия 1\+1'],
    "ICTV": [r'\bictv\b'],
    "Українська озвучка": [r'українська озвучка', r'укр озвучка'],
    "Ukrainian Voice": [r'ukrainian voice'],
    "Озервуд": [r'озервуд'],
    "Погляд": [r'погляд'],
    "Мост": [r'\bмост\b'],
    "СТБ": [r'\bстб\b'],
    "Новий канал": [r'новий канал'],
    "Квартал TV": [r'квартал tv', r'квартал тв'],
    "Медіа Група": [r'медіа група'],
    "ПрАТ УТ": [r'прaт ут'],
    "Ukr studio": [r'ukr studio', r'укр студия'],
    "UA-Pershiy": [r'ua\-перший', r'ua\-first'],
    "Кинохаб": [r'кинохаб'],
    "Film UA": [r'film ua'],
    "StarLight": [r'starlight'],
    "Cinema Sound": [r'cinema sound'],
    "Voice Art": [r'voice art'],
    "AudioForce": [r'audioforce'],
    "SoundLab": [r'soundlab'],
    "Vox Studio": [r'vox studio'],
    "Silver Sound": [r'silver sound'],
}

VOICE_STUDIOS = {**RUSSIAN_STUDIOS, **UKRAINIAN_STUDIOS}
RUSSIAN_STUDIOS_SET = set(RUSSIAN_STUDIOS.keys())
UKRAINIAN_STUDIOS_SET = set(UKRAINIAN_STUDIOS.keys())

def get_studio_language(studio: str) -> str:
    if studio in UKRAINIAN_STUDIOS_SET:
        return "ukr"
    elif studio in RUSSIAN_STUDIOS_SET:
        return "rus"
    else:
        studio_lower = studio.lower()
        if any(keyword in studio_lower for keyword in ['укр', 'укра', 'ua', 'ukr', 'україн']):
            return "ukr"
        return "rus"

# ==================== ПАРСИНГ JACRED ====================

def extract_voices_from_ffprobe(ffprobe: List[Dict]) -> List[str]:
    voices = []
    for track in ffprobe:
        if track.get("codec_type") == "audio":
            title = track.get("tags", {}).get("title", "")
            if title:
                for studio in VOICE_STUDIOS.keys():
                    if studio.lower() in title.lower():
                        if studio not in voices:
                            voices.append(studio)
                        break
                else:
                    if title.upper() in ["UKR", "ENG", "RUS", "DUB", "MVO", "AVO", "TV"]:
                        if title.upper() not in voices:
                            voices.append(title.upper())
                    elif title in ["ЛМ", "ПМ", "СТ", "КВК", "РХС"]:
                        abbr_map = {
                            "ЛМ": "ЛМ", "ПМ": "ПМ", "СТ": "СТ",
                            "КВК": "Кубик в Кубе", "РХС": "Red Head Sound"
                        }
                        studio_name = abbr_map.get(title, title)
                        if studio_name not in voices:
                            voices.append(studio_name)
    return voices

def extract_languages_from_ffprobe(ffprobe: List[Dict]) -> List[str]:
    languages = set()
    for track in ffprobe:
        if track.get("codec_type") in ["audio", "subtitle"]:
            lang = track.get("tags", {}).get("language", "")
            if lang and lang != "und":
                languages.add(lang)
    return list(languages)

def extract_audio_info_from_ffprobe(ffprobe: List[Dict]) -> Dict:
    audio_tracks = [t for t in ffprobe if t.get("codec_type") == "audio"]
    if not audio_tracks:
        return {"codec": "aac", "codec_long": "AAC (Advanced Audio Coding)", "channels": 2, "channel_layout": "stereo", "has_51": False}
    first_audio = audio_tracks[0]
    audio_info = {
        "codec": first_audio.get("codec_name", "aac"),
        "codec_long": first_audio.get("codec_long_name", "AAC (Advanced Audio Coding)"),
        "channels": first_audio.get("channels", 2),
        "channel_layout": first_audio.get("channel_layout", "stereo"),
        "has_51": False
    }
    if audio_info["channels"] >= 6 or "5.1" in str(audio_info["channel_layout"]).lower():
        audio_info["has_51"] = True
    return audio_info

def extract_video_info_from_ffprobe(ffprobe: List[Dict]) -> Dict:
    video_tracks = [t for t in ffprobe if t.get("codec_type") == "video"]
    if not video_tracks:
        return {"codec": "h264", "codec_long": "H.264 / AVC (Advanced Video Coding)", "width": 1920, "height": 1080, "quality": 1080}
    first_video = video_tracks[0]
    video_info = {
        "codec": first_video.get("codec_name", "h264"),
        "codec_long": first_video.get("codec_long_name", "H.264 / AVC (Advanced Video Coding)"),
        "width": first_video.get("width", 1920),
        "height": first_video.get("height", 1080),
        "quality": 1080
    }
    height = video_info["height"]
    if height >= 2160: video_info["quality"] = 2160
    elif height >= 1440: video_info["quality"] = 1440
    elif height >= 1080: video_info["quality"] = 1080
    elif height >= 720: video_info["quality"] = 720
    elif height >= 576: video_info["quality"] = 576
    else: video_info["quality"] = 480
    return video_info

def parse_jacred_data(item: Dict) -> Tuple[List[str], List[str], Dict, Dict]:
    ffprobe = item.get("ffprobe", [])
    if ffprobe and isinstance(ffprobe, list) and len(ffprobe) > 0:
        voices = extract_voices_from_ffprobe(ffprobe)
        languages = extract_languages_from_ffprobe(ffprobe)
        audio_info = extract_audio_info_from_ffprobe(ffprobe)
        video_info = extract_video_info_from_ffprobe(ffprobe)
        return voices, languages, audio_info, video_info
    return [], [], {}, {}

# ==================== ОБЪЕДИНЁННЫЕ ФУНКЦИИ ====================

def parse_voices_from_all_sources(title: str, item: Dict) -> list:
    voices_from_title = parse_voices_from_title(title)
    voices_from_jacred, _, _, _ = parse_jacred_data(item)
    all_voices = []
    seen = set()
    for voice in voices_from_title + voices_from_jacred:
        if voice not in seen:
            seen.add(voice)
            all_voices.append(voice)
    return all_voices

def get_languages_from_all_sources(title: str, item: Dict, voices: List[str]) -> List[str]:
    languages_from_title = get_languages_from_title(title, voices)
    _, languages_from_jacred, _, _ = parse_jacred_data(item)
    all_languages = set()
    for lang in languages_from_title + languages_from_jacred:
        if lang:
            all_languages.add(lang)
    if not all_languages:
        title_lower = title.lower()
        if re.search(r'\bukr\b|\bукраинский\b|\bукраїнський\b|\bукр\b', title_lower): all_languages.add("ukr")
        if re.search(r'\beng\b|\bанглийский\b|\benglish\b|\bангл\b', title_lower): all_languages.add("eng")
        if re.search(r'\brus\b|\bрусский\b|\brussian\b|\bрус\b', title_lower): all_languages.add("rus")
        for voice in voices:
            if voice in UKRAINIAN_STUDIOS_SET: all_languages.add("ukr")
            elif voice in RUSSIAN_STUDIOS_SET: all_languages.add("rus")
            elif voice == "UKR": all_languages.add("ukr")
            elif voice == "ENG": all_languages.add("eng")
            elif voice == "RUS": all_languages.add("rus")
    return list(all_languages)

def extract_audio_info_from_all_sources(title: str, item: Dict, languages: List[str]) -> Dict:
    _, _, audio_info_jacred, _ = parse_jacred_data(item)
    if audio_info_jacred and audio_info_jacred.get("codec"):
        return audio_info_jacred
    return extract_audio_info(title, languages)

def extract_video_info_from_all_sources(title: str, item: Dict) -> Dict:
    _, _, _, video_info_jacred = parse_jacred_data(item)
    if video_info_jacred and video_info_jacred.get("codec"):
        return video_info_jacred
    return extract_video_info(title)

# ==================== ПАРСИНГ ЗАГОЛОВКОВ ====================

def normalize_title(title: str) -> str:
    t = title
    t = re.sub(r'\(S(\d+)[-\~](\d+)\)', r'S\1-\2', t, flags=re.IGNORECASE)
    t = re.sub(r'\(S(\d+)\)', r'S\1', t, flags=re.IGNORECASE)
    t = re.sub(r'\bS(\d+)[-\~](\d+)\b', r'S\1-\2', t, flags=re.IGNORECASE)
    t = re.sub(r'season\s*(\d+)', r'S\1', t, flags=re.IGNORECASE)
    t = re.sub(r'сезон\s*(\d+)', r'S\1', t, flags=re.IGNORECASE)
    t = re.sub(r'^сезон\s*(\d+)[-\~](\d+)', r'S\1-\2', t, flags=re.IGNORECASE)
    t = re.sub(r'episode\s*(\d+)', r'E\1', t, flags=re.IGNORECASE)
    t = re.sub(r'ep\.\s*(\d+)', r'E\1', t, flags=re.IGNORECASE)
    t = re.sub(r'серия\s*(\d+)', r'E\1', t, flags=re.IGNORECASE)
    t = re.sub(r'серія\s*(\d+)', r'E\1', t, flags=re.IGNORECASE)
    t = re.sub(r'(\d+)\s*x\s*(\d+)', r'S\1E\2', t, flags=re.IGNORECASE)
    t = re.sub(r'(\d+)\s*серия\s*(\d+)', r'S\1E\2', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*S(\d+)\s*', r' S\1', t)
    t = re.sub(r'\s*E(\d+)\s*', r'E\1', t)
    return t

def extract_season_info(title: str) -> Tuple[str, List[int], str]:
    normalized_title = normalize_title(title)
    original_lower = title.lower()
    seasons = []
    human_readable = ""
    confidence = "unknown"

    # Высокая уверенность
    match = re.search(r'S(\d+)[-\~]S(\d+)E(\d+)[-\~](\d+)', normalized_title, re.IGNORECASE)
    if match:
        start_season = int(match.group(1)); end_season = int(match.group(2))
        start_ep = int(match.group(3)); end_ep = int(match.group(4))
        seasons = list(range(start_season, end_season + 1))
        human_readable = f"Сезоны {start_season}-{end_season} (серии {start_ep}-{end_ep})"
        confidence = "high"; return human_readable, seasons, confidence

    match = re.search(r'S(\d+)E(\d+)[-\~](\d+)', normalized_title, re.IGNORECASE)
    if match:
        season = int(match.group(1)); start_ep = int(match.group(2)); end_ep = int(match.group(3))
        seasons = [season]
        human_readable = f"Сезон {season} (серии {start_ep}-{end_ep})"
        confidence = "high"; return human_readable, seasons, confidence

    match = re.search(r'S(\d+)E(\d+)', normalized_title, re.IGNORECASE)
    if match:
        season = int(match.group(1)); episode = int(match.group(2))
        seasons = [season]
        human_readable = f"Сезон {season} (серия {episode})"
        confidence = "high"; return human_readable, seasons, confidence

    # Средняя уверенность
    match = re.search(r'S(\d+)[-\~](\d+)', normalized_title, re.IGNORECASE)
    if match:
        start_season = int(match.group(1)); end_season = int(match.group(2))
        if start_season <= end_season and end_season - start_season < 20:
            seasons = list(range(start_season, end_season + 1))
            human_readable = f"Сезоны {start_season}-{end_season}"
            confidence = "medium"; return human_readable, seasons, confidence

    match = re.search(r'\bS(\d+)\b', normalized_title, re.IGNORECASE)
    if match:
        season = int(match.group(1))
        if season < 100:
            seasons = [season]
            human_readable = f"Сезон {season}"
            confidence = "medium"; return human_readable, seasons, confidence

    # Низкая уверенность
    match = re.search(r'(\d+)\s*сезон\s*\(\s*(\d+)[-\~](\d+)\s*серии\s*\)', original_lower)
    if match:
        season = int(match.group(1)); start_ep = int(match.group(2)); end_ep = int(match.group(3))
        seasons = [season]
        human_readable = f"Сезон {season} (серии {start_ep}-{end_ep})"
        confidence = "medium"; return human_readable, seasons, confidence

    match = re.search(r'(\d+)[-\~](\d+)\s*сезон', original_lower)
    if match:
        start_season = int(match.group(1)); end_season = int(match.group(2))
        seasons = list(range(start_season, end_season + 1))
        human_readable = f"Сезоны {start_season}-{end_season}"
        confidence = "low"; return human_readable, seasons, confidence

    match = re.search(r'(\d+)\s*сезон\b', original_lower)
    if match:
        season = int(match.group(1))
        seasons = [season]
        human_readable = f"Сезон {season}"
        confidence = "low"; return human_readable, seasons, confidence

    # Скобки
    match = re.search(r'\([Ss](\d+)[-\~](\d+)\)', title)
    if match:
        start_season = int(match.group(1)); end_season = int(match.group(2))
        if start_season <= end_season:
            seasons = list(range(start_season, end_season + 1))
            human_readable = f"Сезоны {start_season}-{end_season}"
            confidence = "medium"; return human_readable, seasons, confidence

    match = re.search(r'\([Ss](\d+)\)', title)
    if match:
        season = int(match.group(1))
        if season < 100:
            seasons = [season]
            human_readable = f"Сезон {season}"
            confidence = "medium"; return human_readable, seasons, confidence

    # Fallback
    match = re.match(r'^Сезон\s+(\d+)\s*\|\s*.*?\(S(\d+)[-\~](\d+)\)', title, re.IGNORECASE)
    if match:
        start_season = int(match.group(2)); end_season = int(match.group(3))
        seasons = list(range(start_season, end_season + 1))
        human_readable = f"Сезоны {start_season}-{end_season}"
        confidence = "medium"; return human_readable, seasons, confidence

    match = re.search(r'(\d+)[-\~](\d+)\s+(?:серия|серии|серія|серії)', original_lower)
    if match:
        start_ep = int(match.group(1)); end_ep = int(match.group(2))
        human_readable = f"Сезон ? (серии {start_ep}-{end_ep})"
        confidence = "fallback"; return human_readable, seasons, confidence

    if re.match(r'^Сезон\s+\d+\s*\|', title, re.IGNORECASE):
        match = re.match(r'^Сезон\s+(\d+)', title, re.IGNORECASE)
        if match:
            season = int(match.group(1))
            seasons = [season]
            human_readable = f"Сезон {season}"
            confidence = "fallback"; return human_readable, seasons, confidence

    return human_readable, seasons, confidence

def create_enhanced_title(title: str) -> str:
    human_readable, seasons, confidence = extract_season_info(title)
    original_start = title.split('|')[0].strip() if '|' in title else title
    has_mismatch = False
    if confidence in ["high", "medium"] and seasons:
        if re.match(r'^Сезон\s+\d+$', original_start, re.IGNORECASE):
            match = re.match(r'^Сезон\s+(\d+)', original_start, re.IGNORECASE)
            if match:
                stated_season = int(match.group(1))
                if stated_season != seasons[0] or len(seasons) > 1:
                    has_mismatch = True
    if human_readable and confidence in ["high", "medium"] and (has_mismatch or not re.match(r'^Сезон|^Season|^S\d+', original_start, re.IGNORECASE)):
        return f"{human_readable} | {title}"
    return title

# ==================== ФИЛЬТРАЦИЯ ====================

def should_filter_item(item: dict, voices: List[str], languages: List[str], video_quality: int) -> bool:
    title = item.get("Title", "")
    title_lower = title.lower()
    filter_reasons = []

    if FILTER_BLACKLIST_TITLES and any(blackword for blackword in FILTER_BLACKLIST_TITLES if blackword and blackword.lower() in title_lower):
        filter_reasons.append("черный список")

    seeders = item.get("Seeders", 0)
    if FILTER_MIN_SEEDERS > 0 and seeders < FILTER_MIN_SEEDERS:
        filter_reasons.append(f"сидеры {seeders} < {FILTER_MIN_SEEDERS}")
    if FILTER_MAX_SEEDERS > 0 and seeders > FILTER_MAX_SEEDERS:
        filter_reasons.append(f"сидеры {seeders} > {FILTER_MAX_SEEDERS}")

    peers = item.get("Peers", 0)
    if FILTER_MIN_PEERS > 0 and peers < FILTER_MIN_PEERS:
        filter_reasons.append(f"пиры {peers} < {FILTER_MIN_PEERS}")

    if video_quality < FILTER_QUALITY_MIN or video_quality > FILTER_QUALITY_MAX:
        filter_reasons.append(f"качество {video_quality} не в диапазоне {FILTER_QUALITY_MIN}-{FILTER_QUALITY_MAX}")

    if FILTER_LANGUAGES and any(lang.strip() for lang in FILTER_LANGUAGES):
        for lang in languages:
            if lang in FILTER_LANGUAGES:
                filter_reasons.append(f"язык {lang} в чёрном списке")
                break
        else:
            # Дополнительная проверка для русского по шаблонам
            if "rus" in FILTER_LANGUAGES:
                if re.search(r'\b(?:rus|русс?|russian)\b', title_lower):
                    filter_reasons.append("язык rus в чёрном списке")
                else:
                    for studio in RUSSIAN_STUDIOS.keys():
                        for pattern in RUSSIAN_STUDIOS[studio]:
                            if re.search(pattern, title, re.IGNORECASE):
                                filter_reasons.append("язык rus в чёрном списке")
                                break
            # Дополнительная проверка для украинского по шаблонам
            if "ukr" in FILTER_LANGUAGES:
                if re.search(r'\b(?:ukr|укр|украинский|український)\b', title_lower):
                    filter_reasons.append("язык ukr в чёрном списке")
                else:
                    for studio in UKRAINIAN_STUDIOS.keys():
                        for pattern in UKRAINIAN_STUDIOS[studio]:
                            if re.search(pattern, title, re.IGNORECASE):
                                filter_reasons.append("язык ukr в чёрном списке")
                                break

    if FILTER_VOICES and any(voice.strip() for voice in FILTER_VOICES):
        for voice in voices:
            if voice in FILTER_VOICES:
                filter_reasons.append(f"озвучка {voice} в чёрном списке")
                break
        else:
            for studio in FILTER_VOICES:
                if studio in VOICE_STUDIOS:
                    for pattern in VOICE_STUDIOS[studio]:
                        if re.search(pattern, title, re.IGNORECASE):
                            filter_reasons.append(f"озвучка {studio} в чёрном списке")
                            break

    if filter_reasons:
        logger.debug(f"Фильтрация '{title[:50]}...': {', '.join(filter_reasons)}")
        return True
    return False

# ==================== РЕЛЕВАНТНОСТЬ ЗАПРОСУ ====================
# Jackett/Prowlarr иногда возвращают раздачи, не связанные с запросом (например, свежие
# релизы, когда по запросу ничего не найдено). Правила те же, что у JacRed:
#   1. Название: полное равенство после нормализации (регистр, ё/е, знаки и пробелы не важны)
#      одного из названий запроса (Query, title, title_original) и одного из названий раздачи
#      (части заголовка через «/»). Совпадение по отдельным словам или части названия не считается.
#   2. Год (если он есть и в запросе, и в заголовке раздачи):
#        фильмы  — год раздачи в пределах year ± 1;
#        сериалы — наибольший год раздачи не меньше year − 1 (верхней границы нет).
#      Нет года в заголовке — раздача проходит.
#   3. Фильмы: заголовки с «сезон» / «серии» отбрасываются.
# Если точных совпадений нет, ответ пустой (без отката к поиску по вхождению).
# Заголовок раздачи НЕ изменяется: нормализация нужна только для сравнения.
#   off — не проверять; любое другое значение (on, loose, strict) — проверять

FILTER_RELEVANCE = os.getenv("FILTER_RELEVANCE", "on").strip().lower()
if FILTER_RELEVANCE in ("0", "false", "no"):
    FILTER_RELEVANCE = "off"

_YEAR_RE = re.compile(r"(?<!\w)((?:19|20)\d{2})(?!\w)")
_EPISODE_RE = re.compile(r"\bs\d{1,2}(?:e\d{1,3})?\b", re.IGNORECASE)
_3D_RE = re.compile(r"(?<!\w)3D(?!\w)", re.IGNORECASE)
_SEASON_TAIL_RE = re.compile(r"\s+(?:сезон|season)\s*:?\s*\d+(?:\s*-\s*\d+)?\s*$", re.IGNORECASE)
_MOVIE_SERIES_MARK_RE = re.compile(r" (сезон|сери(и|я|й))", re.IGNORECASE)


def _norm_name(text: str) -> str:
    """Нормализованное название для сравнения на равенство: NFC, нижний регистр, ё→е,
    без знаков препинания и пробелов. Буквы любых письменностей (и их диакритика) сохраняются."""
    text = _3D_RE.sub(" ", unicodedata.normalize("NFC", text or "")).lower().replace("ё", "е")   # «3D» — формат, не название
    return "".join(ch for ch in text if ch.isalnum() or unicodedata.category(ch)[0] == "M")


def _years_in(text: str) -> List[int]:
    return [int(y) for y in _YEAR_RE.findall(text.replace("_", " "))]


def _query_name_keys(raws: List[str], year: Optional[int]) -> set:
    """Нормализованные названия запроса. SxxExx и год из параметра year в конце запроса отбрасываются."""
    keys = set()
    for raw in raws:
        text = _EPISODE_RE.sub(" ", raw).strip()
        if year:
            text = re.sub(r"[\s(\[]*" + str(year) + r"[\s)\]]*$", "", text)
        key = _norm_name(text)
        if key:
            keys.add(key)
    return keys


def _release_name_keys(title: str) -> set:
    """Нормализованные названия раздачи: все части заголовка через «/», а также «(Latin)» в скобках."""
    keys = set()
    for name in _name_candidates(title):
        name = _SEASON_TAIL_RE.sub("", _EPISODE_RE.sub(" ", _strip_series_tail(name))).strip()
        key = _norm_name(name)
        if key:
            keys.add(key)
    return keys


def _request_kind(params: Dict[str, Any]) -> str:
    """movie | series: is_serial от Lampa (1 — фильм, 2 — сериал), иначе по категории; прочее считается сериалом."""
    serial = str(params.get("is_serial") or "").strip()
    if serial == "1":
        return "movie"
    if serial:
        return "series"
    category = str(params.get("Category[]") or params.get("Category") or params.get("cat") or "")
    if category.startswith("20") and not category.startswith("2010"):
        return "movie"
    return "series"


def _year_ok(kind: str, year: Optional[int], years: List[int]) -> bool:
    """Фильмы: год раздачи в пределах year ±1; сериалы: наибольший год не меньше year − 1.
    Нет года в запросе или в раздаче — проверка пройдена."""
    if not year or not years:
        return True
    if kind == "movie":
        return any(abs(y - year) <= 1 for y in years)
    return max(years) >= year - 1


def _request_names(params: Dict[str, Any]) -> List[str]:
    raws: List[str] = []
    for key in ("Query", "query", "q", "title", "title_original"):
        value = params.get(key)
        if value and str(value) not in raws:
            raws.append(str(value))
    return raws


def _request_year(params: Dict[str, Any]) -> Optional[int]:
    try:
        return int(params.get("year") or 0) or None
    except (TypeError, ValueError):
        return None


def _is_jacred_item(item: Any) -> bool:
    return isinstance(item, dict) and "ffprobe" in item and "languages" in item and isinstance(item.get("info"), dict)


def collect_aliases(raw_items: List[Dict[str, Any]], params: Dict[str, Any]) -> List[str]:
    """
    Названия из раздач в формате JacRed, подтверждённые запросом: если info.name или info.originalname
    раздачи точно равны одному из названий запроса и год подходит, оба названия JacRed считаются
    названиями этого же произведения (например, украинское ↔ английское). Раздачи JacRed не изменяются,
    названия живут только внутри одного запроса.
    """
    if FILTER_RELEVANCE == "off":
        return []
    year = _request_year(params)
    wanted = _query_name_keys(_request_names(params), year)
    if not wanted:
        return []
    kind = _request_kind(params)

    aliases: List[str] = []
    seen = set(wanted)
    for item in raw_items:
        if not _is_jacred_item(item):
            continue
        info = item["info"]
        names = [info.get("name"), info.get("originalname")]
        names = [n.strip() for n in names if isinstance(n, str) and n.strip()]
        if not names or not ({_norm_name(n) for n in names} & wanted):
            continue
        released = info.get("relased")
        years = [released] if isinstance(released, int) and released > 0 else _years_in(str(item.get("Title") or ""))
        if not _year_ok(kind, year, years):
            continue
        for n in names:
            key = _norm_name(n)
            if key and key not in seen:
                seen.add(key)
                aliases.append(n)
    return aliases


def build_relevance_matcher(params: Dict[str, Any], extra_names: Optional[List[str]] = None
                            ) -> Optional[Callable[[str], Tuple[bool, str]]]:
    """
    Строит функцию title -> (относится ли раздача к запросу, причина) по ИСХОДНЫМ параметрам клиента.
    extra_names — названия, подтверждённые JacRed (collect_aliases).
    Возвращает None, если проверять нечего (RSS без запроса, режим off).
    """
    if FILTER_RELEVANCE == "off":
        return None

    year = _request_year(params)
    raws = _request_names(params)
    for name in extra_names or []:
        if name not in raws:
            raws.append(name)

    wanted = _query_name_keys(raws, year)
    if not wanted:
        return None

    kind = _request_kind(params)

    def matches(title: str) -> Tuple[bool, str]:
        if not _norm_name(title):
            return False, "empty_title"

        if not (_release_name_keys(title) & wanted):
            return False, "title_mismatch"

        if kind == "movie" and _MOVIE_SERIES_MARK_RE.search(title):
            return False, "series_marker_in_movie"

        years = _years_in(title)
        if not _year_ok(kind, year, years):
            return False, f"year_mismatch ({', '.join(map(str, sorted(set(years))))} != {year})"
        return True, "title_match"

    return matches

# ==================== ИНФО ИЗ ЗАГОЛОВКА ====================

def extract_audio_info(title: str, languages: List[str] = None) -> Dict:
    title_lower = title.lower()
    default_language = "und"
    if languages:
        default_language = languages[0] if languages[0] in ["rus", "ukr", "eng"] else "und"
    elif "украин" in title_lower or "укр" in title_lower or "ukr" in title_lower: default_language = "ukr"
    elif "русск" in title_lower or "rus" in title_lower: default_language = "rus"
    elif "англ" in title_lower or "eng" in title_lower: default_language = "eng"

    audio_info = {"codec": "aac", "codec_long": "AAC (Advanced Audio Coding)", "channels": 2, "channel_layout": "stereo", "language": default_language, "studio": None, "has_51": False}

    if "dts" in title_lower or "dts-hd" in title_lower: audio_info["codec"] = "dts"; audio_info["codec_long"] = "DTS (Digital Theater Systems)"
    elif "ac3" in title_lower or "dolby digital" in title_lower: audio_info["codec"] = "ac3"; audio_info["codec_long"] = "AC-3 (Audio Coding 3)"
    elif "aac" in title_lower: audio_info["codec"] = "aac"; audio_info["codec_long"] = "AAC (Advanced Audio Coding)"
    elif "mp3" in title_lower: audio_info["codec"] = "mp3"; audio_info["codec_long"] = "MP3 (MPEG Audio Layer III)"
    elif "flac" in title_lower: audio_info["codec"] = "flac"; audio_info["codec_long"] = "FLAC (Free Lossless Audio Codec)"
    elif "opus" in title_lower: audio_info["codec"] = "opus"; audio_info["codec_long"] = "Opus Audio Codec"

    if re.search(r'\b5\.1\b|\b5ch\b|\b6ch\b|5\.1ch|шестиканальный', title_lower): audio_info["has_51"] = True; audio_info["channels"] = 6; audio_info["channel_layout"] = "5.1"
    elif re.search(r'\b7\.1\b|\b7ch\b|7\.1ch|восьмиканальный', title_lower): audio_info["has_51"] = True; audio_info["channels"] = 8; audio_info["channel_layout"] = "7.1"
    elif re.search(r'\b2\.0\b|\b2ch\b|стерео|stereo', title_lower): audio_info["channels"] = 2; audio_info["channel_layout"] = "stereo"
    elif re.search(r'\b1\.0\b|\b1ch\b|моно|mono', title_lower): audio_info["channels"] = 1; audio_info["channel_layout"] = "mono"

    return audio_info

def extract_video_info(title: str) -> Dict:
    title_lower = title.lower()
    video_info = {"codec": "h264", "codec_long": "H.264 / AVC (Advanced Video Coding)", "width": 1920, "height": 1080, "quality": 1080, "type": "sdr", "source": "web"}

    if re.search(r'\b(?:hevc|h265|x265|h\.265)\b', title_lower): video_info["codec"] = "hevc"; video_info["codec_long"] = "H.265 / HEVC (High Efficiency Video Coding)"
    elif "av1" in title_lower: video_info["codec"] = "av1"; video_info["codec_long"] = "AV1 (AOMedia Video 1)"
    elif "vp9" in title_lower: video_info["codec"] = "vp9"; video_info["codec_long"] = "VP9 (Google)"
    elif re.search(r'\b(?:h264|x264|avc|h\.264)\b', title_lower): video_info["codec"] = "h264"; video_info["codec_long"] = "H.264 / AVC (Advanced Video Coding)"

    resolution_patterns = [
        (r'2160p|\b4k\b|\buhd\b|3840x2160', 2160, 3840, 2160),
        (r'1440p|\b2k\b|2560x1440', 1440, 2560, 1440),
        (r'1080p|\bfullhd\b|\bfhd\b|1920x1080', 1080, 1920, 1080),
        (r'720p|\bhd\b|1280x720', 720, 1280, 720),
        (r'576p|720x576', 576, 720, 576),
        (r'480p|640x480', 480, 640, 480),
    ]
    for pattern, quality, width, height in resolution_patterns:
        if re.search(pattern, title_lower): video_info["quality"] = quality; video_info["width"] = width; video_info["height"] = height; break

    if re.search(r'\bhdr10\+\b', title_lower): video_info["type"] = "hdr10+"
    elif re.search(r'\bhdr10\b', title_lower): video_info["type"] = "hdr10"
    elif re.search(r'\bhdr\b', title_lower): video_info["type"] = "hdr"
    elif re.search(r'\bdolby vision\b|\bdv\b|\bdovi\b', title_lower): video_info["type"] = "dolby vision"
    elif re.search(r'\bsdr\b', title_lower): video_info["type"] = "sdr"

    if re.search(r'\bbluray\b|\bblu\-ray\b|\bbdrip\b|\bbdremux\b', title_lower): video_info["source"] = "bluray"
    elif re.search(r'\bweb\-dl\b|\bwebdl\b|\bweb\b', title_lower): video_info["source"] = "webdl"
    elif re.search(r'\bwebrip\b|\bweb\-rip\b', title_lower): video_info["source"] = "webrip"
    elif re.search(r'\bhdtv\b|\btvrip\b', title_lower): video_info["source"] = "hdtv"
    elif re.search(r'\bdvdrip\b|\bdvd\b', title_lower): video_info["source"] = "dvd"

    return video_info

def extract_subtitle_info(title: str) -> dict:
    title_lower = title.lower()
    sub_info = {"has_subs": False, "codec": "ass", "codec_long": "ASS (Advanced SSA) subtitle", "language": "und", "forced": False, "format": "ass"}
    if re.search(r'\b(?:sub|субтитр|сабы|srt|ass|ssa|vtt|pgs|sup)\b', title_lower):
        sub_info["has_subs"] = True
        if re.search(r'\bsrt\b', title_lower): sub_info["codec"] = "subrip"; sub_info["codec_long"] = "SubRip subtitle"; sub_info["format"] = "srt"
        elif re.search(r'\bvtt\b', title_lower): sub_info["codec"] = "webvtt"; sub_info["codec_long"] = "WebVTT subtitle"; sub_info["format"] = "vtt"
        elif re.search(r'\bpgs\b|\bsup\b', title_lower): sub_info["codec"] = "hdmv_pgs_subtitle"; sub_info["codec_long"] = "HDMV PGS subtitle"; sub_info["format"] = "pgs"
        if re.search(r'\b(?:rus|русс?|russian)\b', title_lower): sub_info["language"] = "rus"
        elif re.search(r'\b(?:ukr|укр|украинский|українськ)\b', title_lower): sub_info["language"] = "ukr"
        elif re.search(r'\b(?:eng|англ|english)\b', title_lower): sub_info["language"] = "eng"
        elif re.search(r'\b(?:multi|мульти)\b', title_lower): sub_info["language"] = "multi"
        if "forced" in title_lower or "принудительные" in title_lower or "forc" in title_lower: sub_info["forced"] = True
        if "sdh" in title_lower or "для слабослышащих" in title_lower: sub_info["forced"] = True
    return sub_info

# ==================== ОЗВУЧКИ ====================

def parse_voices_from_title(title: str) -> list:
    voices = []
    title_lower = title.lower()
    multi_lang_pattern = re.compile(r'(\d+)x\s*([a-zA-Zа-яА-Я]+)\s*[/|]\s*([a-zA-Zа-яА-Я]+)', re.IGNORECASE)
    match = multi_lang_pattern.search(title)
    if match:
        count = int(match.group(1)); lang1 = match.group(2).lower(); lang2 = match.group(3).lower()
        lang_map = {'ukr': 'UKR', 'украинский': 'UKR', 'український': 'UKR', 'укр': 'UKR', 'eng': 'ENG', 'english': 'ENG', 'английский': 'ENG', 'англ': 'ENG', 'rus': 'RUS', 'russian': 'RUS', 'русский': 'RUS', 'рус': 'RUS'}
        if lang1 in lang_map and lang_map[lang1] not in voices: voices.append(lang_map[lang1])
        if lang2 in lang_map and lang_map[lang2] not in voices: voices.append(lang_map[lang2])
    if re.search(r'\b(?:dub|дубляж|дублирован|дубль)\b', title_lower): voices.append("DUB")
    if re.search(r'\b(?:mvo|мво|многоголосый|multi voice|мультиголос)\b', title_lower): voices.append("MVO")
    if re.search(r'\b(?:avo|авто|одноголосый|single voice)\b', title_lower): voices.append("AVO")
    if re.search(r'\b(?:tv|тв|телевизионная)\b', title_lower): voices.append("TV")
    for studio, patterns in UKRAINIAN_STUDIOS.items():
        for pattern in patterns:
            if re.search(pattern, title, re.IGNORECASE):
                if studio not in voices: voices.append(studio)
                break
    for studio, patterns in RUSSIAN_STUDIOS.items():
        for pattern in patterns:
            if re.search(pattern, title, re.IGNORECASE):
                if studio not in voices: voices.append(studio)
                break
    lang_keywords = {'UKR': [r'\bukr\b', r'\bукраинский\b', r'\bукраїнський\b', r'\bукраин\b', r'\bукр\b'], 'ENG': [r'\beng\b', r'\bанглийский\b', r'\benglish\b', r'\bангл\b'], 'RUS': [r'\brus\b', r'\bрусский\b', r'\brussian\b', r'\bрус\b']}
    for lang_code, patterns in lang_keywords.items():
        if lang_code not in voices:
            for pattern in patterns:
                if re.search(pattern, title_lower, re.IGNORECASE): voices.append(lang_code); break
    if re.search(r'sub\s+eng', title_lower, re.IGNORECASE) and 'ENG' not in voices: voices.append('ENG')
    if re.search(r'sub\s+ukr', title_lower, re.IGNORECASE) and 'UKR' not in voices: voices.append('UKR')
    if re.search(r'sub\s+rus', title_lower, re.IGNORECASE) and 'RUS' not in voices: voices.append('RUS')
    unique_voices = []; seen = set()
    for voice in voices:
        if voice not in seen: seen.add(voice); unique_voices.append(voice)
    return unique_voices

def get_languages_from_title(title: str, voices: list) -> List[str]:
    title_lower = title.lower()
    languages = set()
    multi_match = re.search(r'(\d+)x\s*([a-zA-Zа-яА-Я]+)\s*[/|]\s*([a-zA-Zа-яА-Я]+)', title, re.IGNORECASE)
    if multi_match:
        lang1 = multi_match.group(2).lower(); lang2 = multi_match.group(3).lower()
        lang_map = {'ukr': 'ukr', 'украинский': 'ukr', 'український': 'ukr', 'укр': 'ukr', 'eng': 'eng', 'english': 'eng', 'английский': 'eng', 'англ': 'eng', 'rus': 'rus', 'russian': 'rus', 'русский': 'rus', 'рус': 'rus'}
        if lang1 in lang_map: languages.add(lang_map[lang1])
        if lang2 in lang_map: languages.add(lang_map[lang2])
    if re.search(r'\bukr\b|\bукраинский\b|\bукраїнський\b|\bукр\b', title_lower): languages.add("ukr")
    if re.search(r'\beng\b|\bанглийский\b|\benglish\b|\bангл\b', title_lower): languages.add("eng")
    if re.search(r'\brus\b|\bрусский\b|\brussian\b|\bрус\b', title_lower): languages.add("rus")
    for voice in voices:
        if voice in UKRAINIAN_STUDIOS_SET: languages.add("ukr")
        elif voice in RUSSIAN_STUDIOS_SET: languages.add("rus")
        elif voice == "UKR": languages.add("ukr")
        elif voice == "ENG": languages.add("eng")
        elif voice == "RUS": languages.add("rus")
    return list(languages)

# ==================== FFROBE ====================

def create_ffprobe(title: str, voices: list, item: Dict = None) -> list:
    if item and item.get("ffprobe"): return item["ffprobe"]
    video_info = extract_video_info(title)
    languages = get_languages_from_title(title, voices)
    audio_info = extract_audio_info(title, languages)
    sub_info = extract_subtitle_info(title)
    title_lower = title.lower()
    ffprobe = [{"index": 0, "codec_name": video_info["codec"], "codec_long_name": video_info["codec_long"], "codec_type": "video", "width": video_info["width"], "height": video_info["height"], "coded_width": video_info["width"], "coded_height": video_info["height"], "tags": {"DURATION": "00:54:17.646000000"}}]
    multi_match = re.search(r'(\d+)x\s*([a-zA-Zа-яА-Я]+)\s*[/|]\s*([a-zA-Zа-яА-Я]+)', title, re.IGNORECASE)
    track_count = int(multi_match.group(1)) if multi_match else 2
    audio_tracks_added = 0
    lang_order = ['UKR', 'ENG', 'RUS']
    for lang in lang_order:
        if lang in voices and audio_tracks_added < track_count:
            language_code = lang.lower()[:3]
            channels = 6 if audio_info["has_51"] and lang == 'UKR' and audio_tracks_added == 0 else audio_info["channels"]
            channel_layout = "5.1" if channels == 6 else audio_info["channel_layout"]
            ffprobe.append({"index": len(ffprobe), "codec_name": audio_info["codec"], "codec_long_name": audio_info["codec_long"], "codec_type": "audio", "sample_fmt": "fltp", "sample_rate": "48000", "channels": channels, "channel_layout": channel_layout, "tags": {"language": language_code, "DURATION": "00:54:17.621000000", "title": lang}})
            audio_tracks_added += 1
            if audio_tracks_added >= track_count: break
    studio_voices = [v for v in voices if v in VOICE_STUDIOS.keys()]
    for studio in studio_voices:
        studio_language = get_studio_language(studio)
        ffprobe.append({"index": len(ffprobe), "codec_name": audio_info["codec"], "codec_long_name": audio_info["codec_long"], "codec_type": "audio", "sample_fmt": "fltp", "sample_rate": "48000", "channels": audio_info["channels"], "channel_layout": audio_info["channel_layout"], "tags": {"language": studio_language, "DURATION": "00:54:17.621000000", "title": studio}})
        audio_tracks_added += 1
    if sub_info["has_subs"]:
        ffprobe.append({"index": len(ffprobe), "codec_name": sub_info["codec"], "codec_long_name": sub_info["codec_long"], "codec_type": "subtitle", "tags": {"language": sub_info["language"], "DURATION": "00:53:05.568000000", "title": "forced" if sub_info["forced"] else "subtitles"}})
    if re.search(r'sub\s+eng', title_lower, re.IGNORECASE):
        ffprobe.append({"index": len(ffprobe), "codec_name": "subrip", "codec_long_name": "SubRip subtitle", "codec_type": "subtitle", "tags": {"language": "eng", "DURATION": "00:53:05.568000000"}})
    if re.search(r'sub\s+ukr', title_lower, re.IGNORECASE):
        ffprobe.append({"index": len(ffprobe), "codec_name": "subrip", "codec_long_name": "SubRip subtitle", "codec_type": "subtitle", "tags": {"language": "ukr", "DURATION": "00:53:05.568000000"}})
    if re.search(r'sub\s+rus', title_lower, re.IGNORECASE):
        ffprobe.append({"index": len(ffprobe), "codec_name": "subrip", "codec_long_name": "SubRip subtitle", "codec_type": "subtitle", "tags": {"language": "rus", "DURATION": "00:53:05.568000000"}})
    return ffprobe

# ==================== УТИЛИТЫ ====================

_SEASON_PREFIX_RE = re.compile(
    r'^(?:сезон\w*|season\w*|s\d{1,2}\b|\d+(?:\s*-\s*\d+)?\s*сезон\w*)', re.IGNORECASE)
_QUALITY_RE = re.compile(
    r'\b(?:web[-\s]?dl|web[-\s]?rip|bd[-\s]?rip|bd[-\s]?remux|dvd[-\s]?rip|hdtv[-\s]?rip|hd[-\s]?rip|'
    r'ts[-\s]?rip|cam[-\s]?rip|hdtv|blu[-\s]?ray|remux|uhd|4k|dvd\d?|\d{3,4}p)\b', re.IGNORECASE)
_QUALITY_UPPER_RE = re.compile(r'\b(?:TS|CAM|TC|HDTS)\b')
# год считается началом технического хвоста, только если за ним конец, запятая, скобка или тег качества
_YEAR_TAIL_RE = re.compile(r'\b(?:19|20)\d{2}\b(?=\s*(?:$|[,;)\]|]|[A-Za-z]{2,}|\d{3,4}p\b))')
_NOT_ORIGINAL_RE = re.compile(r'\b(?:web|dl|rip|bluray|hdtv|dub|mvo|сезон|серии|s\d|e\d|of\s+\d+)\b', re.IGNORECASE)


def _head_before_tags(text: str) -> str:
    """Часть заголовка до технического хвоста (качество, источник, год раздачи)."""
    cut = len(text)
    for rx in (_QUALITY_RE, _QUALITY_UPPER_RE, _YEAR_TAIL_RE):
        for m in rx.finditer(text):
            if m.start() > 0:
                cut = min(cut, m.start())
                break
    return text[:cut]


def _clean_name_part(part: str) -> str:
    """Название до скобки. Тире внутри названия («Джек – покоритель великанов») сохраняется."""
    m = re.search(r'\(', part)
    if m:
        part = part[:m.start()]
    return re.sub(r'\s+', ' ', part).strip(' \t,;:-–—|')


_SERIES_TAIL_RE = re.compile(
    r'\s*(?:[-–—]\s*)?(?:(?:сезон|season)\s*:?\s*\d+.*|s\d{1,2}(?:e\d{1,3})?\b.*)$', re.IGNORECASE)


def _strip_series_tail(name: str) -> str:
    """«Game of Thrones - Season 1» → «Game of Thrones»; «Name - S01E01» → «Name»."""
    return _SERIES_TAIL_RE.sub('', name).strip(' \t,;:-–—|')


def _title_head(title: str) -> str:
    """Часть заголовка раздачи с названиями (без технического хвоста, тегов и префикса сезона)."""
    t = (title or "").strip()

    # «Сезон 1 | Название ...» — берём часть после префикса; иначе всё после «|» это теги (озвучка и т. п.)
    parts = [p.strip() for p in t.split('|')]
    if len(parts) > 1 and parts[1] and _SEASON_PREFIX_RE.match(parts[0]):
        t = parts[1]
    else:
        t = parts[0]

    t = re.sub(r'\[[^\]]*\]?', ' ', t)          # [H.264/1080p], [2026, жанры ...] — теги
    if ' ' not in t.strip() and t.count('.') >= 2:
        t = t.replace('.', ' ')                  # Dune.Part.Three.2026.1080p
    t = re.sub(r'\s+', ' ', t.replace('_', ' ')).strip()

    return _head_before_tags(t)


def _latin_in_parens(head: str) -> str:
    """Латинское название в скобках: «Одиссея (The Odyssey) 2026» → «The Odyssey»."""
    eng_match = re.search(r'\(([^)]*[a-zA-Z][^)]*)\)', head)
    if eng_match:
        candidate = eng_match.group(1).strip()
        if len(candidate) > 2 and not _QUALITY_RE.search(candidate) and not _NOT_ORIGINAL_RE.search(candidate):
            return candidate
    return ""


def _name_candidates(title: str) -> List[str]:
    """Все названия из заголовка раздачи (части через «/» и «(Latin)» в скобках) — только для сравнения."""
    head = _title_head(title)
    names = [_clean_name_part(seg) for seg in head.split('/')]
    latin = _latin_in_parens(head)
    if latin:
        names.append(latin)
    return [n for n in names if n]


def extract_names_from_title(title: str) -> tuple:
    """
    Русское и оригинальное название из заголовка раздачи. Заголовок не изменяется,
    результат нужен только для info.name / info.originalname.
    """
    head = _title_head(title)
    segments = head.split('/')
    name = _clean_name_part(segments[0])
    originalname = ""
    if len(segments) > 1:
        originalname = _clean_name_part(segments[1])
        if len(originalname) <= 2:
            originalname = ""

    if not originalname:
        originalname = _latin_in_parens(head)

    name = _strip_series_tail(name) or name
    originalname = _strip_series_tail(originalname)
    if originalname and name and name.lower().replace(' ', '') == originalname.lower().replace(' ', ''):
        originalname = ""
    if not name:
        name = _clean_name_part(re.split(r'[|\[(]', title or "")[0])
    return name, originalname

def extract_year_from_title(title: str) -> int:
    range_match = re.search(r'(\d{4})\s*[\-\~]\s*(\d{4})', title)
    if range_match:
        try:
            year = int(range_match.group(2))
            if 1900 <= year <= 2100: return year
        except: pass
    year_match = re.search(r'\b(19|20)\d{2}\b', title)
    if year_match:
        try:
            year = int(year_match.group())
            if 1900 <= year <= 2100: return year
        except: pass
    return None

# ==================== ГЛАВНАЯ КОНВЕРТАЦИЯ ====================

def jackett_to_jackred(item: dict) -> dict:
    original_title = item.get("Title", "")
    is_jacred_format = "ffprobe" in item and "languages" in item and "info" in item
    enhanced_title = create_enhanced_title(original_title)

    if is_jacred_format:
        voices = parse_voices_from_all_sources(original_title, item)
        languages = get_languages_from_all_sources(original_title, item, voices)
        audio_info = extract_audio_info_from_all_sources(original_title, item, languages)
        video_info = extract_video_info_from_all_sources(original_title, item)
        ffprobe = item.get("ffprobe", [])
    else:
        voices = parse_voices_from_title(original_title)
        languages = get_languages_from_title(original_title, voices)
        audio_info = extract_audio_info(original_title, languages)
        video_info = extract_video_info(original_title)
        ffprobe = create_ffprobe(original_title, voices, item)

    human_readable, seasons, confidence = extract_season_info(original_title)
    name, originalname = extract_names_from_title(original_title)
    if is_jacred_format:
        # JacRed уже прислал названия — не пересчитываем их из заголовка
        source_info = item.get("info")
        if isinstance(source_info, dict):
            if source_info.get("name"):
                name = source_info["name"]
            if "originalname" in source_info and isinstance(source_info["originalname"], str):
                originalname = source_info["originalname"]
    released_year = extract_year_from_title(original_title)

    is_pack = len(seasons) > 1
    is_serial = bool(seasons) or confidence != "unknown"
    media_types = ["serial"] if is_serial else ["movie"]
    if is_pack and "pack" not in media_types: media_types.append("pack")

    size = item.get("Size", 0)
    size_gb = size / (1024 ** 3) if size else 0
    size_name = f"{size_gb / 1024:.2f} ТБ" if size_gb >= 1024 else f"{size_gb:.2f} ГБ"

    magnet = item.get("MagnetUri") or item.get("Link") or item.get("Guid")
    tracker = item.get("TrackerId") or item.get("Tracker", "").lower()

    if not is_jacred_format:
        languages = get_languages_from_title(original_title, voices)

    result = {
        "Tracker": tracker,
        "Details": item.get("Details") or item.get("Guid"),
        "Title": enhanced_title,
        "Size": size,
        "PublishDate": str(item.get("PublishDate") or "")[:19],
        "Category": item.get("Category", []),
        "CategoryDesc": item.get("CategoryDesc"),
        "Seeders": item.get("Seeders", 0),
        "Peers": item.get("Peers", 0),
        "MagnetUri": magnet,
        "ffprobe": ffprobe,
        "languages": languages,
        "info": {
            "quality": video_info.get("quality", 1080),
            "videotype": video_info.get("type", "sdr"),
            "video_source": video_info.get("source", "web"),
            "video_codec": video_info.get("codec", "h264"),
            "audio_codec": audio_info.get("codec", "aac"),
            "audio_channels": audio_info.get("channels", 2),
            "audio_layout": audio_info.get("channel_layout", "stereo"),
            "has_51": audio_info.get("has_51", False),
            "voices": voices,
            "seasons": seasons,
            "season_confidence": confidence,
            "season_human_readable": human_readable,
            "is_pack": is_pack,
            "types": media_types,
            "sizeName": size_name,
            "name": name,
            "originalname": originalname,
            "relased": released_year,
            "has_subs": any(word in original_title.lower() for word in ['sub', 'субтитр', 'сабы'])
        }
    }
    return result