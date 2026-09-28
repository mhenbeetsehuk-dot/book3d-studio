import re
import uuid
from collections import Counter, defaultdict
from .models import Project, Character, Location, Scene, Shot

# Conservative heuristics: it is better to miss an anchor than lock a random word
# as a persistent character/location for hundreds of shots.
STOP_NAMES = {
    "The","A","An","And","But","He","She","They","It","His","Her","Their","This","That","Then","When","Where","Chapter",
    "I","We","You","My","Your","Our","In","On","At","From","To","Of","For","With","As","If","So","No","Yes","What","Not",
    "Something","Nothing","Anything","Everything","Someone","Anyone","Everyone","First","Second","Third","Fourth","Fifth","Sixth",
    "Seventh","Eighth","Ninth","Tenth","One","Two","Three","Four","Five","Six","Seven","Eight","Nine","Ten","Whatever",
    "Suddenly","Later","Now","Here","There","Inside","Outside","Before","After","Only","Maybe","Perhaps","Because","While",
    "Signal","War","Is","Or","All","Can","Could","Had","Day","Control","Will","Would","Should","May","Might","Must","Do","Did","Does","Have","Has","Been","Being","Was","Were","Are","Am","Very","More","Most","Less","Much","Many","Few","Each","Every","Either","Neither","Also","Still","Even","Yet","Just","Again","How","Why","Probably","By","Let","Full","Couldn't","Couldnt"
}
TITLE_WORDS = {"Dr","Mr","Mrs","Ms","Commander","Captain","Officer","Chief","Professor","Detective","Doctor","General","Colonel","Major","Lieutenant","Sergeant"}
LOCATION_HINTS = [
    "room","hall","bridge","station","ship","street","house","office","lab","laboratory","base","city","forest","planet","deck",
    "corridor","chamber","hospital","school","church","warehouse","airport","hangar","bay","quarters","facility","complex","tower",
    "colony","moon","world","outpost","port","dock","cockpit","control room","command center","centre"
]
GENERIC_LOCATION_PREFIX = {"the","a","an","in","on","at","inside","outside","through","across","into","from","near","around","over","under","this","that","his","her","their","our","my","your","one","another"}


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


def split_chapters(text: str):
    pattern = re.compile(r"(?im)^\s*(chapter\s+(?:\d+|[ivxlcdm]+|[a-z]+)(?:\s*[:\-—].*)?|prologue\b.*|epilogue\b.*)\s*$")
    matches = list(pattern.finditer(text))
    if not matches:
        return [("Chapter 1", text)]
    chapters = []
    preface = text[:matches[0].start()].strip()
    if len(preface.split()) > 80:
        chapters.append(("Opening", preface))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            chapters.append((re.sub(r"\s+", " ", m.group(1)).strip(), body))
    return chapters or [("Chapter 1", text)]


def _canonical_name(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"(?:[’']s)\b", "", raw, flags=re.I)
    raw = re.sub(r"[“”\"'.,;:!?()\[\]]+$", "", raw.strip())
    raw = re.sub(r"\s+", " ", raw)
    return raw


CONTRACTION_RE = re.compile(r"\b(?:that|it|i|we|they|you|he|she|there|what|who|where|when|why|how)[’'](?:s|m|re|ve|ll|d)\b", re.I)
NON_PERSON_ENDINGS = {
    "base", "station", "center", "centre", "room", "chamber", "quarters", "ship", "planet", "world", "colony",
    "corridor", "bridge", "lab", "laboratory", "facility", "complex", "team", "chapter", "deck", "bay", "port", "outpost",
    "corporation", "company", "agency", "department", "division", "committee", "council", "group", "unit", "crew", "force", "authority"
}


def detect_characters(text: str, limit=24):
    pattern = re.compile(
        r"\b(?:(?:Dr|Mr|Mrs|Ms|Commander|Captain|Officer|Chief|Professor|Detective|Doctor|General|Colonel|Major|Lieutenant|Sergeant)\.?\s+)?"
        r"[A-Z][a-zA-Z'’-]{1,}(?:\s+[A-Z][a-zA-Z'’-]{1,}){0,2}\b"
    )
    counts = Counter()
    evidence = defaultdict(int)
    for m in pattern.finditer(text):
        raw = m.group(0)
        if CONTRACTION_RE.search(raw):
            continue
        n = _canonical_name(raw)
        words = n.replace('.', '').split()
        if not words:
            continue
        if n.isupper() or words[0].title() in STOP_NAMES or any(w.title() in STOP_NAMES for w in words):
            continue
        core = [w for w in words if w.rstrip('.').title() not in TITLE_WORDS]
        if not core:
            continue
        if core[-1].lower() in NON_PERSON_ENDINGS:
            continue
        if any(re.search(r"[’'](?:s|m|re|ve|ll|d)$", w, re.I) for w in core):
            continue

        counts[n] += 1
        before = text[max(0, m.start()-30):m.start()]
        after = text[m.end():m.end()+60]
        if len(words) >= 2 or words[0].rstrip('.').title() in TITLE_WORDS:
            evidence[n] += 4
        if re.match(r"\s*(?:said|asked|replied|whispered|shouted|called|nodded|turned|looked|stepped|walked|moved|stared|smiled|frowned|sighed|answered|murmured|ordered|reported)\b", after, re.I):
            evidence[n] += 3
        if re.search(r"[\"”’]\s*$", before):
            evidence[n] += 2

    scored = []
    for n, c in counts.items():
        words = n.replace('.', '').split()
        score = c + evidence[n]
        if len(words) == 1:
            if c < 3 or evidence[n] < 3:
                continue
        if len(words) >= 2 and c >= 2:
            score += 3
        scored.append((score, c, n))
    scored.sort(reverse=True)

    selected = []
    seen_last = set()
    for score, c, n in scored:
        last = n.replace('.', '').split()[-1].lower()
        if last in seen_last:
            continue
        selected.append(n)
        seen_last.add(last)
        if len(selected) >= limit:
            break
    return selected


def _normalize_location(x: str) -> str:
    x = re.sub(r"\s+", " ", x.strip(" ,.;:!?—-\n\t"))
    x = re.sub(r"^(?:in|on|at|inside|outside|into|from|through|across|near|around)\s+", "", x, flags=re.I)
    return x


def detect_locations(text: str, limit=18):
    hints = "|".join(sorted(map(re.escape, LOCATION_HINTS), key=len, reverse=True))
    candidates = Counter()

    proper_pat = re.compile(
        rf"\b(?:[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+){{0,2}}\s+(?i:{hints})|(?i:{hints})\s+[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+){{0,2}})\b"
    )
    for m in proper_pat.finditer(text):
        x = _normalize_location(m.group(0))
        words = x.split()
        if len(words) < 2 or words[0].lower() in GENERIC_LOCATION_PREFIX:
            continue
        if words[0].lower() in {"this","that","his","her","their","our","my","your","one","another"}:
            continue
        if any(w.lower() in {"that", "the", "and", "then", "which", "where", "when"} for w in words[1:]):
            continue
        candidates[x] += 4

    compound_pat = re.compile(
        rf"\b(?:main|upper|lower|central|medical|analysis|command|observation|crew|engineering|security|operations|control)\s+(?i:{hints})\b"
    )
    for m in compound_pat.finditer(text):
        x = _normalize_location(m.group(0))
        candidates[x.title()] += 2

    out = []
    seen = set()
    for n, c in candidates.most_common():
        key = re.sub(r"^the\s+", "", n.lower())
        if key in seen:
            continue
        if c < 4:
            continue
        seen.add(key)
        out.append(n)
        if len(out) >= limit:
            break
    return out


def _explicit_scene_sections(chapter_text: str):
    sep = re.compile(r"(?m)^\s*(?:\*\s*\*\s*\*|#{3,}|—\s*—\s*—|-{3,}|\*{3,})\s*$")
    parts = [p.strip() for p in sep.split(chapter_text) if p.strip()]
    return parts if len(parts) > 1 else None


def _group_paragraphs(text: str, target_words=650, max_words=950, min_words=220):
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        return []
    groups, current, words = [], [], 0
    for p in paras:
        pw = len(p.split())
        if current and words >= target_words and words + pw > max_words:
            groups.append("\n\n".join(current))
            current, words = [], 0
        current.append(p)
        words += pw
        if words >= max_words:
            groups.append("\n\n".join(current))
            current, words = [], 0
    if current:
        tail = "\n\n".join(current)
        if groups and len(tail.split()) < min_words:
            groups[-1] += "\n\n" + tail
        else:
            groups.append(tail)
    return groups


def scene_chunks(chapter_text: str):
    explicit = _explicit_scene_sections(chapter_text)
    if explicit:
        chunks = []
        for part in explicit:
            if len(part.split()) > 1300:
                chunks.extend(_group_paragraphs(part, target_words=750, max_words=1100))
            else:
                chunks.append(part)
        return [c for c in chunks if len(c.split()) >= 60]
    return [c for c in _group_paragraphs(chapter_text) if len(c.split()) >= 60]


def _char_present(name: str, block: str) -> bool:
    words = name.replace('.', '').split()
    keys = [words[-1]]
    if len(words) > 1:
        keys.append(" ".join(words[-2:]))
    return any(re.search(rf"\b{re.escape(k)}\b", block, re.I) for k in keys)


def make_shots(block: str, characters, location):
    dialogue_lines = re.findall(r"[\"“](.*?)[\"”]", block, flags=re.S)
    present = [c for c in characters if _char_present(c, block)]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", block)) if s.strip()]
    if len(sentences) <= 4:
        actions = sentences
    else:
        idxs = sorted(set([0, len(sentences)//3, (2*len(sentences))//3, len(sentences)-1]))
        actions = [sentences[i] for i in idxs]
    shots = []
    shot_types = ["establishing wide", "medium tracking", "close-up", "over-the-shoulder"]
    moves = ["slow push-in", "dolly", "subtle handheld", "slow orbit"]
    for i, action in enumerate(actions or [block[:240]]):
        shots.append(Shot(
            number=i+1,
            duration_s=6.0 if i == 0 else 5.0,
            shot_type=shot_types[i % len(shot_types)],
            camera_move=moves[i % len(moves)],
            action=action[:500],
            dialogue=(dialogue_lines[i].strip()[:500] if i < len(dialogue_lines) else ""),
            mood="cinematic",
            characters=present[:6],
            location=location,
            assets=[]
        ))
    return shots


def analyze(text: str, title: str, source_filename: str) -> Project:
    text = clean_text(text)
    character_names = detect_characters(text)
    location_names = detect_locations(text)
    characters = [Character(
        name=n,
        description=f"Persistent story character extracted from {title}.",
        visual_anchor=f"LOCKED CHARACTER: {n}; keep the same identity, face, proportions, hairstyle and identifying details across all scenes; wardrobe may change only when the story requires it.",
        voice_anchor=f"LOCKED VOICE: {n}; keep voice identity, accent and delivery consistent."
    ) for n in character_names]
    locations = [Location(
        name=n,
        description=f"Recurring story location extracted from {title}.",
        visual_anchor=f"LOCKED LOCATION: {n}; preserve architecture, layout, lighting logic, scale and recurring props."
    ) for n in location_names]

    scenes = []
    sidx = 1
    for chapter_name, chapter_text in split_chapters(text):
        for local_idx, block in enumerate(scene_chunks(chapter_text), start=1):
            present = [n for n in character_names if _char_present(n, block)]
            block_low = block.lower()
            loc = next((l for l in location_names if re.sub(r"^the\s+", "", l.lower()) in block_low), "Unspecified location")
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", block)) if s.strip()]
            summary = " ".join(sentences[:2])[:420]
            scenes.append(Scene(
                id=f"SC{sidx:04d}",
                chapter=chapter_name,
                title=f"Scene {local_idx}",
                summary=summary,
                characters=present[:8],
                location=loc,
                shots=make_shots(block, character_names, loc)
            ))
            sidx += 1
    return Project(
        id=uuid.uuid4().hex[:10],
        title=title,
        source_filename=source_filename,
        characters=characters,
        locations=locations,
        scenes=scenes
    )
