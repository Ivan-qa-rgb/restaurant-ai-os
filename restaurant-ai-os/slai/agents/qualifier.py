import re

from slai.agents.date_utils import normalize_date
from slai.agents.guest_state import GuestState

PARTY_WORDS = {
    "один": 1, "одна": 1, "одного": 1, "одну": 1,
    "двое": 2, "два": 2, "две": 2, "двух": 2,
    "трое": 3, "три": 3, "трех": 3, "трёх": 3,
    "четверо": 4, "четыре": 4, "четырех": 4, "четырёх": 4,
    "пятеро": 5, "пять": 5, "пяти": 5,
    "шестеро": 6, "шесть": 6, "шести": 6,
    "семеро": 7, "семь": 7, "семи": 7,
    "восьмеро": 8, "восемь": 8, "восьми": 8,
    "девятеро": 9, "девять": 9, "девяти": 9,
    "десятеро": 10, "десять": 10, "десяти": 10,
}

_WORD_PATTERN = "|".join(
    re.escape(word)
    for word in sorted(PARTY_WORDS, key=len, reverse=True)
)

class QualifierAgent:
    def extract(self, message):
        text = message.lower()
        state = GuestState()

        party = re.search(
            r"(?<!\d)(\d{1,2})\s*(?:человек(?:а)?|чел\.?|гост(?:я|ей)?|персон(?:ы)?)(?!\w)",
            text,
        )
        if party:
            state.party_size = int(party.group(1))
        else:
            # Числительное принимаем только рядом с явным указанием на группу:
            # «нас будет четверо» или «четыре человека».
            word_party = re.search(
                rf"\bнас\s+(?:будет\s+)?({_WORD_PATTERN})\b",
                text,
            )
            if not word_party:
                word_party = re.search(
                    rf"\b({_WORD_PATTERN})\s*"
                    r"(?:человек(?:а|ов)?|гост(?:ь|я|ей)?|персон(?:а|ы))\b",
                    text,
                )
            if word_party:
                state.party_size = PARTY_WORDS[word_party.group(1)]

        time_match = re.search(
            r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)",
            text,
        )
        if time_match:
            state.time = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"

        date_match = re.search(
            r"(?<!\w)(сегодня|завтра|today|tomorrow)(?!\w)",
            text,
        )
        if date_match:
            state.date = normalize_date(date_match.group(1))
        else:
            explicit_date = re.search(
                r"\b(?:\d{1,2}\.\d{1,2}\.\d{2,4}|\d{4}-\d{2}-\d{2})\b",
                text,
            )
            if explicit_date:
                state.date = normalize_date(explicit_date.group(0))

        state.missing_fields = []
        if not state.party_size:
            state.missing_fields.append("party_size")
        if not state.date:
            state.missing_fields.append("date")
        if not state.time:
            state.missing_fields.append("time")

        return state
