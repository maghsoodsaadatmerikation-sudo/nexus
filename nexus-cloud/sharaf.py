"""Bounded conversational routing for Studio. Routes describe a reply, never a person."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata

VERSION = "sharaf-0.2"


class Route(Enum):
    EMERGENCY = "emergency"
    CLARIFY = "safety_clarification"
    CARE_ENGAGED = "emergency_care_engaged"
    GROUND = "grounded_support"
    MEDICATION = "medication_decision"
    ASSESSMENT = "individual_assessment"
    EDUCATION = "health_information"
    SHAME = "shame_and_responsibility"
    REPAIR = "relational_repair"
    REFLECT = "emotional_support"
    IDENTITY = "identity_exploration"
    MEANING = "values_and_meaning"


class Subject(Enum):
    SELF = "self"
    OTHER = "other"
    BOTH = "both"


@dataclass(frozen=True)
class Decision:
    route: Route
    subject: Subject = Subject.SELF


def rule(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# Keep clauses separate so a qualifier cannot hide a different current assertion.
CLAUSE = rule(
    r"[.!?؟؛;\n]+|\b(?:but|however|اما|ولی)\b"
    r"|(?:[,،]\s*|[\"”»]\s*(?=(?:and|و)\s))(?=(?:and\s+)?(?:i\b|in real life\b|(?:the )?paramedics\b)"
    r"|(?:و\s+)?(?:من\s|در واقعیت\s|تیم اورژانس\s))"
    r"|\b(?:and\s+(?=(?:the )?paramedics\b)|و\s+(?=تیم اورژانس\s))"
)
HISTORICAL = rule(r"\b(?:years? ago|last year|in the past|when i was a child|used to)\b|سال(?: ها)? پیش|سال گذشته|در گذشته|قبلا")
FICTION = rule(r"\b(?:my (?:fictional )?character|in (?:my|the) (?:novel|script|story)|fictional character|translate this quote)\b|در (?:داستان|فیلمنامه)|شخصیت داستان")
FICTION_REQUEST = rule(r"\b(?:edit|rewrite|translate|scene|dialogue)\b|ویرایش|ترجمه|دیالوگ|صحنه")
NEGATED = rule(r"\b(?:i|he|she|they) (?:don't|do not|doesn't|won't|will not|didn't|did not|never|no longer) (?:want to |plan to |feel like |think about )?(?:kill|hurt|harm|overdose|take|die)\b|(?:نمی خوام|نمی خواهم|قصد ندارم) (?:به خودم آسیب|خودکشی)|قرص زیادی نخوردم")
UNCERTAIN_INTENT = rule(r"\b(?:i don't know if|i am not sure if|i'm not sure if)\b|نمی (?:دونم|دانم)|مطمئن نیستم|یا نه$")
NEGATED_INTENT = rule(r"\b(?:i|he|she|they) (?:am |is |are )?(?:not |no longer )going to (?:kill|hurt|harm)\b")
MEDICINE_OBJECT = (
    r"(?:pills?|tablets?|capsules?|meds|(?:of )?(?:my |the )?medication|"
    r"(?:of )?(?:my |the )?(?:sertraline|lithium|fluoxetine|venlafaxine|clozapine))\b"
)
INGESTION = (
    r"(?:overdosed\b|(?:took|taken|swallowed) (?:too (?:much|many)|[1-9]\d{1,2}) "
    + MEDICINE_OBJECT + r")"
)
SELF_EVENT = rule(
    r"\bi(?: have |'ve | )(?:just |already |think i |may have )?" + INGESTION
    + r"|\bi cut myself and (?:can't stop|am bleeding)"
    r"|(?:قرص|دارو)(?: های)? (?:خیلی )?(?:زیاد|بیش از حد) (?:خوردم|مصرف کردم)"
    r"|(?:اوردوز|اور دوز) کردم"
)
DENIED_REPORT = rule(r"\bi (?:never|didn't|did not) (?:say|said|report|reported) (?:that )?i\b")
OTHER_EVENT = rule(
    r"\b(?:he|she|they|my [\w ]{1,30}) (?:just |already |may have )?" + INGESTION
    + r"|(?:دوستم|خواهرم|برادرم|همسرم).{0,40}(?:اوردوز کرد|قرص زیاد خورد)"
)
SELF_IMMEDIATE = rule(r"\bi(?:'m| am) (?:about to|going to) (?:kill myself|end my life|hurt myself)|\bi (?:will|plan to) (?:kill myself|end my life|hurt myself).{0,32}\b(?:now|tonight|today)\b|الان می خوام (?:خودکشی کنم|به خودم آسیب بزنم)|(?:امشب|همین الان) (?:خودکشی می کنم|به خودم آسیب می زنم|خودمو می کشم)")
OTHER_IMMEDIATE = rule(r"\b(?:he|she|they|my [\w ]{1,30}) (?:is |are )?(?:about to|going to) (?:kill (?:himself|herself|themselves)|end (?:his|her|their) life)|\bi(?:'m| am) about to (?:kill|seriously hurt) (?:him|her|them|someone)|(?:دوستم|خواهرم|برادرم|همسرم).{0,35}(?:الان|همین الان).{0,25}خودکشی")
SELF_CONCERN = rule(r"\b(?:i want to die|i (?:don't|do not) want to live(?: anymore)?|i wish i (?:were|was) dead|i(?:'m| am| feel) suicidal|i (?:want to|might) (?:kill myself|hurt myself|end my life)|i (?:keep thinking|thought|think) about (?:suicide|killing myself|hurting myself)|i (?:can't|cannot) (?:keep myself safe|go on))\b|دلم می خواد بمیرم|دیگه نمی خوام زنده باشم|کاش (?:مرده بودم|بمیرم)|(?:فکر|افکار) خودکشی (?:دارم|می کنم)|به خودکشی فکر (?:می کنم|کردم)|نمی دونم.{0,80}به خودم آسیب|ممکنه.{0,40}به خودم آسیب")
OTHER_CONCERN = rule(r"\b(?:he|she|they|my [\w ]{1,30}) (?:said (?:he|she|they) )?(?:wants? to die|feels? suicidal|might kill (?:himself|herself|themselves))|(?:دوستم|خواهرم|برادرم).{0,35}(?:می خواد بمیره|فکر خودکشی)")
THIRD_PARTY_SPEECH = rule(
    r"\b(?:my (?:friend|partner|sister|brother)|he|she|they) (?:just )?"
    r"(?:said|told me)[:, ]+[‘“\"']?(?P<english>i\b.*)"
    r"|(?:دوستم|همسرم|خواهرم|برادرم|مادرم|پدرم) (?:بهم |به من )?گفت[ :،,«\"“]+(?P<persian>.+)"
)
TOOK_THEM = rule(r"^i (?:just |already )?took them\b")
RECENT_NEGATED_CONCERN = rule(r"\bi (?:didn't|did not) think about (?:hurting myself|killing myself|suicide)\b")
RECENT_CONTRAST = rule(r"^i did (?:last night|yesterday)\b")
CURRENT = rule(r"\b(?:now|today|tonight|just now)\b|همین الان|امشب")
SAFE_NOW = rule(r"\bi am safe now and (?:i )?(?:have no intention|do not intend|don't intend) to (?:hurt|harm) myself\b|الان در امانم و قصد ندارم به خودم آسیب بزنم")
CARE_PREFIX = rule(r"^(?:and |now |the |و |الان )+")
PRIORITY_ROUTES = frozenset({Route.EMERGENCY, Route.CLARIFY, Route.CARE_ENGAGED})
PILLS = rule(r"\b(?:pills|medication|overdose|tablets)\b|(?:قرص|دارو)")
SELF_CARE = rule(r"\b(?:paramedics|emergency clinicians|emergency doctors) (?:are with me|are treating me)\b|(?:تیم اورژانس|پزشکان اورژانس) (?:کنارم هستند|دارند درمانم می کنند)")
OTHER_CARE = rule(r"\b(?:paramedics|emergency clinicians|emergency doctors) (?:are with|are treating) (?:them|him|her|my friend)\b|تیم اورژانس کنار دوستم است")
GROUND = rule(r"\b(?:voices (?:are )?(?:telling|commanding) me|i hear voices no one else|hidden messages.{0,25}(?:for me|to me)|i (?:barely|hardly) slept.{0,50}(?:nights|days)|i haven't slept (?:in|for) (?:two|three|four|several|[2-9]) (?:nights|days))\b|صداها بهم می گن|پیام های مخفی.{0,20}برای من|(?:سه|چند) شب.{0,25}(?:نخوابیدم|کم خوابیدم)")
MEDICATION = rule(r"\b(?:should|can) i (?:stop|start|change|taper|increase|decrease|double|halve|skip) (?:my |taking |the )?(?:[^.?!]{1,65}\s)?(?:medication|antidepressant|sertraline|lithium|dose|fluoxetine|venlafaxine|clozapine|ssri|benzodiazepine)\b|(?:می تونم|می توانم|باید).{0,40}(?:دارو|دوز|سرترالین|لیتیوم).{0,35}(?:قطع|کم|زیاد|عوض|دو برابر)")
ASSESSMENT = rule(r"\b(?:do i have|am i experiencing|diagnose me with) (?:clinical )?(?:depression|anxiety|bipolar disorder|ptsd|psychosis|ocd)|آیا.{0,30}(?:افسردگی|اضطراب|وسواس|اختلال دوقطبی) دارم")
EDUCATION = rule(r"\b(?:what is|what are the symptoms of|what does|what does a diagnosis of) (?:clinical )?(?:depression|anxiety|panic|bipolar disorder|ptsd|psychosis|ocd)\b|(?:افسردگی|اضطراب|وسواس|روان پریشی|اختلال دوقطبی) (?:چیه|چیست|یعنی چی)")
SHAME = rule(r"\bi (?:feel|am) (?:broken|worthless|ashamed)|\bi hate myself\b|احساس بی ارزشی|احساس شرم|از خودم متنفرم")
REPAIR = rule(r"\bhow (?:can|do) i (?:make amends|apologize|repair (?:our|the) relationship)\b|چطور (?:عذرخواهی کنم|جبران کنم|رابطه را ترمیم کنم)")
REFLECT = rule(r"\bi (?:feel|am) (?:depressed|overwhelmed|so lonely|hopeless|grieving)|احساس افسردگی|خیلی تنهام|احساس ناامیدی|از دست دادن.{0,30}سخته")
IDENTITY = rule(r"\bi don't know who i am\b|نمی دونم کی هستم|نمی دانم کی هستم")
MEANING = rule(r"\b(?:how can i make sense of my pain|what is the meaning of my suffering)\b|چطور به رنجم معنا بدم|معنای رنجم چیه")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).translate(str.maketrans({
        "ي": "ی", "ك": "ک", "ى": "ی", "\u200c": " ", "’": "'", "\u0640": "",
    }))
    return " ".join("".join(c for c in value if unicodedata.category(c) != "Mn").split())


def decide(turns: list[str]) -> Decision | None:
    """Replay only user-authored turns from the supplied branch; keep no gateway history."""
    open_concerns: dict[Subject, Route] = {}
    recent_pills = False
    care_engaged = None
    for turn in turns:
        care_engaged = None
        clauses = [normalize(part) for part in CLAUSE.split(turn)]
        # A fictional frame applies to its own text. Later explicit first-person
        # disclosures in the same message still go through the checks below.
        framed_fiction = any(FICTION.search(part) for part in clauses)
        fiction_task = framed_fiction and any(FICTION_REQUEST.search(part) for part in clauses)
        for index, part in enumerate(clauses):
            if FICTION.search(part):
                continue
            if fiction_task and part.startswith(('"', '“', '«')):
                continue
            if (HISTORICAL.search(part) and not CURRENT.search(part)) or DENIED_REPORT.search(part):
                continue
            if SAFE_NOW.search(part) and open_concerns.get(Subject.SELF) is Route.CLARIFY:
                open_concerns.pop(Subject.SELF)
            report = THIRD_PARTY_SPEECH.search(part)
            if report:
                speech = report[report.lastgroup]
                if (SELF_EVENT.search(speech)
                    or SELF_IMMEDIATE.search(speech) and not UNCERTAIN_INTENT.search(speech)
                    or recent_pills and TOOK_THEM.search(speech)):
                    open_concerns[Subject.OTHER] = Route.EMERGENCY
                elif ((SELF_CONCERN.search(speech) or SELF_IMMEDIATE.search(speech))
                      and not NEGATED.search(speech)
                      and open_concerns.get(Subject.OTHER) is not Route.EMERGENCY):
                    open_concerns[Subject.OTHER] = Route.CLARIFY
                part = part[:report.start(report.lastgroup)]
            care_statement = CARE_PREFIX.sub("", part)
            for subject, pattern in ((Subject.SELF, SELF_CARE), (Subject.OTHER, OTHER_CARE)):
                if pattern.match(care_statement) and open_concerns.pop(subject, None) is not None:
                    care_engaged = subject
            recent_contrast = (index > 0 and RECENT_CONTRAST.search(part)
                               and RECENT_NEGATED_CONCERN.search(clauses[index - 1]))
            for subject, event, immediate, concern in (
                (Subject.SELF, SELF_EVENT, SELF_IMMEDIATE, SELF_CONCERN),
                (Subject.OTHER, OTHER_EVENT, OTHER_IMMEDIATE, OTHER_CONCERN),
            ):
                if event.search(part) or (immediate.search(part) and not UNCERTAIN_INTENT.search(part)):
                    open_concerns[subject] = Route.EMERGENCY
                elif ((concern.search(part) or immediate.search(part) or (subject is Subject.SELF and recent_contrast))
                      and not (NEGATED.search(part) or NEGATED_INTENT.search(part))
                      and open_concerns.get(subject) is not Route.EMERGENCY):
                    open_concerns[subject] = Route.CLARIFY
        recent_pills = any(PILLS.search(part) for part in clauses)
    for route in (Route.EMERGENCY, Route.CLARIFY):
        subjects = [subject for subject, concern in open_concerns.items() if concern is route]
        if subjects:
            if route is Route.EMERGENCY and len(subjects) == 2:
                return Decision(route, Subject.BOTH)
            return Decision(route, subjects[0])
    if care_engaged is not None:
        return Decision(Route.CARE_ENGAGED, care_engaged)
    current = normalize(turns[-1])
    if FICTION.search(current) and FICTION_REQUEST.search(current):
        return None
    for pattern, route in (
        (GROUND, Route.GROUND), (MEDICATION, Route.MEDICATION),
        (ASSESSMENT, Route.ASSESSMENT), (EDUCATION, Route.EDUCATION),
        (SHAME, Route.SHAME), (REPAIR, Route.REPAIR), (REFLECT, Route.REFLECT),
        (IDENTITY, Route.IDENTITY), (MEANING, Route.MEANING),
    ):
        if pattern.search(current):
            return Decision(route)
    return None


REPLIES = {
    Route.CARE_ENGAGED: (
        "Help is with you now. Tell the emergency team what happened and follow their instructions.",
        "تیم اورژانس کنارت است. آنچه اتفاق افتاده را به تیم بگو و راهنمایی آن‌ها را دنبال کن.",
    ),
    Route.EMERGENCY: (
        "This may be an emergency. Call your local emergency services now or ask someone nearby to call. If you can safely reach a trusted person, ask them to stay with you.",
        "ممکن است وضعیت اورژانسی باشد. همین حالا با اورژانس محل تماس بگیر یا از کسی که نزدیکت است بخواه تماس بگیرد. اگر می‌توانی با فرد امن و قابل اعتمادی تماس بگیری، از او بخواه کنارت بماند.",
    ),
    Route.CLARIFY: (
        "I’m glad you told me. Are you in immediate danger or do you think you might act on these thoughts soon? If either is true, call your local emergency services now. If you can do so safely, tell someone you trust what is happening.",
        "ممنون که گفتی. آیا الان در خطر فوری هستی یا فکر می‌کنی ممکن است به‌زودی به خودت آسیب بزنی؟ اگر بله، همین حالا با اورژانس محل تماس بگیر. اگر برایت امن است، به فردی که به او اعتماد داری بگو چه اتفاقی افتاده.",
    ),
    Route.GROUND: (
        "This may feel unsettling or intense. I can help you think through how it is affecting your sleep, daily life, or safety. If this is new, getting stronger, or making daily life difficult, reach out to a mental health professional for support. Are you able to stay safe right now?",
        "این تجربه ممکن است فشار زیادی به تو بیاورد. می‌توانیم به تأثیرش بر خواب، زندگی روزمره یا ایمنی‌ات توجه کنیم. اگر تازه شروع شده، شدت گرفته یا زندگی روزمره را دشوار کرده، با یک متخصص سلامت روان تماس بگیر. آیا الان می‌توانی خودت را در امان نگه داری؟",
    ),
    Route.MEDICATION: (
        "Ask your prescriber or pharmacist before changing how you take this medication. It may help to tell them the medication name, prescribed dose, and what prompted the question, such as a side effect or a missed dose.",
        "پیش از تغییر شیوهٔ مصرف دارو با پزشک تجویزکننده یا داروساز صحبت کن. نام دارو، دوز تجویزشده و دلیل پرسشت، مثلاً یک عارضه یا فراموشی مصرف، می‌تواند به آن‌ها کمک کند.",
    ),
    Route.ASSESSMENT: (
        "A clinician can assess what these experiences mean by looking at when they began, how they affect your life, and your wider health history. You could write down when you first noticed them and one example of how they affect your day.",
        "متخصص می‌تواند با بررسی زمان شروع، تأثیر تجربه‌ها بر زندگی و سابقهٔ سلامتت ارزیابی کند. می‌توانی بنویسی اولین بار چه زمانی متوجه‌شان شدی و یک نمونه از تأثیرشان بر روزت را یادداشت کنی.",
    ),
    Route.EDUCATION: (
        "For general information about symptoms and care, see the NHS mental health conditions guide: https://www.nhs.uk/mental-health/conditions/",
        "برای اطلاعات عمومی دربارهٔ نشانه‌ها و مراقبت، راهنمای سلامت روان NHS به زبان انگلیسی در این نشانی در دسترس است: https://www.nhs.uk/mental-health/conditions/",
    ),
    Route.SHAME: (
        "That sounds painful. It may help to separate what happened from the conclusion you drew about yourself. If you want to talk through it, start with the moment that felt hardest.",
        "به نظر می‌رسد تجربهٔ دردناکی بوده. شاید کمک کند آنچه اتفاق افتاده را از نتیجه‌ای که دربارهٔ خودت گرفتی جدا کنی. اگر دوست داشتی درباره‌اش حرف بزنی، از سخت‌ترین لحظه شروع کن.",
    ),
    Route.REPAIR: (
        "Start with the specific action you want to take responsibility for. You can draft an apology privately. Before sending it, consider whether contact would be welcome and safe for both of you.",
        "از رفتار مشخصی شروع کن که می‌خواهی مسئولیتش را بپذیری. می‌توانی ابتدا یک عذرخواهی برای خودت بنویسی. پیش از فرستادن، فکر کن آیا تماس برای هر دو نفر امن و پذیرفتنی است.",
    ),
    Route.REFLECT: (
        "That sounds heavy. If it would help, we can stay with what you’re feeling or look for one next step that feels manageable.",
        "به نظر می‌رسد بار سنگینی است. اگر کمک می‌کند، می‌توانیم دربارهٔ همین احساسی که داری صحبت کنیم یا یک قدم کوچک و شدنی پیدا کنیم.",
    ),
    Route.IDENTITY: (
        "You can leave the question open. Try writing down two roles or values that feel like yours today. You can revise the list whenever it stops fitting.",
        "می‌توانی فعلاً این پرسش را باز بگذاری. دو نقش یا ارزش را بنویس که امروز حس می‌کنی به تو نزدیک‌اند. هر وقت دیگر با تجربه‌ات جور نبودند، می‌توانی فهرست را عوض کنی.",
    ),
    Route.MEANING: (
        "You can leave the meaning open for now. If you want a place to start, consider what matters to you today and one small action that would honor it.",
        "می‌توانی فعلاً دربارهٔ معنایش به نتیجه نرسی. اگر دنبال نقطهٔ شروع هستی، به چیزی فکر کن که امروز برایت مهم است و یک کار کوچک که با آن هماهنگ باشد.",
    ),
}

OTHER_REPLIES = {
    Route.CARE_ENGAGED: (
        "Tell the emergency team what you know about what happened. Follow their instructions and give them room to help.",
        "آنچه دربارهٔ اتفاق می‌دانی به تیم اورژانس بگو. راهنمایی آن‌ها را دنبال کن و اجازه بده کمک کنند.",
    ),
    Route.EMERGENCY: (
        "This may be an emergency. Call emergency services where the person is, if you can, and tell them what you know. If someone nearby can safely reach them, alert that person while help is being arranged.",
        "ممکن است وضعیت اورژانسی باشد. اگر می‌توانی با اورژانس محل حضور آن فرد تماس بگیر و آنچه می‌دانی بگو. اگر کسی نزدیک اوست و می‌تواند بدون خطر به او برسد، در حین هماهنگی کمک به آن فرد هم خبر بده.",
    ),
    Route.CLARIFY: (
        "Do you know whether the person is in immediate danger or might act on these thoughts soon? If so, contact emergency services where they are and alert a trusted person nearby if it is safe to do so.",
        "آیا می‌دانی آن فرد الان در خطر فوری است یا ممکن است به‌زودی به خودش آسیب بزند؟ اگر بله با اورژانس محل حضور او تماس بگیر و در صورت امکان و ایمن بودن، فرد مورد اعتمادی در نزدیکی او را خبر کن.",
    ),
}


def render(decision: Decision, current: str, locale: str | None) -> str:
    if locale is None:
        locale = "fa" if re.search(r"[\u0600-\u06ff]", current) else "en"
    if decision.subject is Subject.BOTH:
        return (
            "Call local emergency services now. Tell them both you and another person may need urgent help and where each of you is, if you know. Ask someone nearby to help you make the call if safe.",
            "همین حالا با اورژانس محل تماس بگیر. بگو تو و فرد دیگری ممکن است به کمک فوری نیاز داشته باشید و اگر می‌دانی، محل هر دو نفر را بگو. اگر بی‌خطر است، از کسی که نزدیکت است برای تماس کمک بگیر.",
        )[locale == "fa"]
    table = OTHER_REPLIES if decision.subject is Subject.OTHER else REPLIES
    return table[decision.route][locale == "fa"]
