"""Every sentence the server writes, in English and Khmer, keyed by verdict key or id. Plus digit handling."""
import re

from .types import Audience, Fact, Lang, Seg, Step, Tile

# Keys: "<verdict>.headline", "<verdict>.<audience>.short|more", "tile.<id>.label|note",
#       "step.<id>.title|did|why", "note.<id>", "word.<id>", "month.<1-12>".
# **bold** in a headline marks Seg.hl. Placeholders fill from facts only.
EN: dict[str, str] = {
    "note.second_look": "You changed this after seeing results. A second look at the same data finds patterns by chance more often.",
    "note.synthetic": "Synthetic data, not NASA.",
    # TODO rows 6-7: claim.* and trend.* headlines, student/policymaker/researcher templates, tiles, steps
}
KM: dict[str, str] = {}   # a missing key falls back to EN (row 13 fills it)

HAS_DIGIT = re.compile(r"[0-9០-៩０-９]")
_TO_ASCII = str.maketrans("០១២៣៤៥៦៧៨៩０１２３４５６７８９", "01234567890123456789")


def ascii_digits(s: str) -> str:
    return s.translate(_TO_ASCII)


def number_tokens(s: str) -> set[str]:
    """Number tokens after ascii_digits; U+2212 and '-' before a digit are a sign, a decimal comma becomes '.';
    a hyphen right after a digit is a range dash, not a minus. Used on facts AND on model text."""
    out = set()
    for sign, num in _NUMBER.findall(ascii_digits(s)):
        num = num.replace(",", ".")
        if "." in num:
            num = num.rstrip("0").rstrip(".")
        out.add(("-" if sign else "") + num)
    return out


_NUMBER = re.compile(r"(?:(?<![0-9])([−-]))?([0-9]+(?:[.,][0-9]+)?)")


class Words:
    """All server prose for one language. Passed to every analysis as `w`."""

    def __init__(self, lang: Lang):
        self.lang = lang

    def __call__(self, key: str, **vars: Fact) -> str:
        """KM -> EN fallback, then format_map. An unknown key or missing placeholder raises KeyError (a test failure)."""
        text = (KM if self.lang == "km" else {}).get(key) or EN[key]
        return text.format_map(vars)

    def has(self, key: str) -> bool:
        return key in EN

    def headline(self, verdict_key: str, facts: dict[str, Fact]) -> list[Seg]:
        """Split the template on ** FIRST, then fill each piece, so a place name cannot inject bold."""
        raise NotImplementedError

    def tile(self, id: str, value: str, **vars: Fact) -> Tile:
        raise NotImplementedError

    def step(self, id: str, **vars: Fact) -> Step:
        raise NotImplementedError

    def template(self, verdict_key: str, audience: Audience, facts: dict[str, Fact]) -> tuple[str, str]:
        """(short, more) from "<key>.<audience>.short|more"; falls back to student, then to EN."""
        raise NotImplementedError
