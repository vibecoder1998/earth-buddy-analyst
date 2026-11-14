"""Every sentence the server writes, in English and Khmer, keyed by verdict key or id. Plus digit handling."""
import re

from .types import Audience, Fact, Lang, Seg, Step, Tile

# Keys: "<verdict>.headline", "<verdict>.<audience>.short|more", "tile.<id>.label|note",
#       "step.<id>.title|did|why", "note.<id>", "word.<id>", "month.<1-12>".
# **bold** in a headline marks Seg.hl. Placeholders fill from facts only.
EN: dict[str, str] = {
    "note.second_look": "You changed this after seeing results. A second look at the same data finds patterns by chance more often.",
    "note.synthetic": "Synthetic data, not NASA.",
    "note.doubt": "{label}: a clear trend this way may come from the instrument, not the ground.",

    "claim.supported.headline": "**Supported.** Every part of this claim shows a clear trend the way it says.",
    "claim.supported.student.short": "The data for {region} backs this claim. Every part shows a clear trend the way the claim says.",
    "claim.supported.student.more": "We tested each part against NASA data for {years}. Each one moved steadily the way the claim says, and none of them looks like chance. A trend says what changed, not why.",
    "claim.supported.policymaker.short": "All {n_tests} parts of this claim hold for {region}. The trends are clear enough to plan around.",
    "claim.supported.policymaker.more": "Each part shows a steady change over {years} in NASA data, and each passes a check against chance findings. The data shows the change, not its cause.",
    "claim.supported.researcher.short": "All {n_tests} tests show a clear trend in the claimed direction over {years} (memory-corrected two-sided Mann-Kendall, p under {alpha}). Each survives Benjamini-Hochberg at {fdr_q} across the claim.",
    "claim.supported.researcher.more": "Slopes are Sen slopes per decade with {ci_pct}% intervals, shown per test. Pettitt and a two-level fit flag a single jump; none was found for a supported part.",

    "claim.opposed.headline": "**Opposed.** Every part of this claim shows a clear trend the other way.",
    "claim.opposed.student.short": "The data for {region} goes against this claim. Every part changed the other way.",
    "claim.opposed.student.more": "We tested each part against NASA data for {years}. Each one moved steadily, but in the opposite direction from the claim. A trend says what changed, not why.",
    "claim.opposed.policymaker.short": "All {n_tests} parts of this claim run the other way in {region}. Plans based on the claim would point the wrong way.",
    "claim.opposed.policymaker.more": "Each part shows a clear change over {years} in NASA data, opposite to the claim, and each passes a check against chance findings.",
    "claim.opposed.researcher.short": "All {n_tests} tests show a clear trend against the claimed direction over {years} (memory-corrected two-sided Mann-Kendall, p under {alpha}). Each survives Benjamini-Hochberg at {fdr_q}.",
    "claim.opposed.researcher.more": "Slopes are Sen slopes per decade with {ci_pct}% intervals, shown per test.",

    "claim.mixed.headline": "**Mixed.** Some parts of this claim hold, and some go the other way.",
    "claim.mixed.student.short": "Part of this claim is right for {region}, and part is wrong. Some things changed the way it says, and some the other way.",
    "claim.mixed.student.more": "We tested each part against NASA data for {years}. Look at each row to see which parts hold. A trend says what changed, not why.",
    "claim.mixed.policymaker.short": "Some parts of this claim hold for {region}, and others run the other way. Treat the parts separately.",
    "claim.mixed.policymaker.more": "Each row shows one part tested against NASA data over {years}, with a check against chance findings across the claim.",
    "claim.mixed.researcher.short": "Of {n_tests} tests over {years}, {n_supported} show a clear trend as claimed and {n_opposed} a clear trend against it (memory-corrected two-sided Mann-Kendall, p under {alpha}, Benjamini-Hochberg at {fdr_q}).",
    "claim.mixed.researcher.more": "Slopes are Sen slopes per decade with {ci_pct}% intervals, shown per test.",

    "claim.step.headline": "**A jump, not a trend.** The record changed in one jump, not steadily.",
    "claim.step.student.short": "The data for {region} changed, but in one jump, not as a steady trend. That is a different story from the claim.",
    "claim.step.student.more": "We tested each part against NASA data for {years}. The change came all at once around one year. On steady trends this check still sees a jump about {step_false_fire}% of the time, so treat it as a hint.",
    "claim.step.policymaker.short": "The change in {region} came in one jump, not steadily. Check what happened around that year before planning on a trend.",
    "claim.step.policymaker.more": "A sudden jump can come from a real event or from a change in how the data was made. On steady trends this check still sees a jump about {step_false_fire}% of the time.",
    "claim.step.researcher.short": "No test is a steady trend; at least one clear change over {years} is better fit by two levels (a Pettitt change point, and a two-level fit that beats the Sen line).",
    "claim.step.researcher.more": "Measured on simulated steady trends, the step check fires about {step_false_fire}% of the time. Benjamini-Hochberg at {fdr_q} across the claim.",

    "claim.unsupported.headline": "**Not supported.** The data for {region} shows no trend clear enough to back this claim.",
    "claim.unsupported.student.short": "The data for {region} does not back this claim. The changes are not clear enough to tell from chance.",
    "claim.unsupported.student.more": "We tested each part against NASA data for {years}. Not clear does not mean nothing is happening. It means this record cannot tell yet.",
    "claim.unsupported.policymaker.short": "The data for {region} cannot confirm this claim. It is not proof the opposite is true.",
    "claim.unsupported.policymaker.more": "No part shows a change clear enough to pass a check against chance findings over {years}. A longer record may tell.",
    "claim.unsupported.researcher.short": "None of the {n_tests} tests shows a clear trend in the claimed direction that survives Benjamini-Hochberg at {fdr_q} over {years} (memory-corrected two-sided Mann-Kendall, p under {alpha}).",
    "claim.unsupported.researcher.more": "Slopes are Sen slopes per decade with {ci_pct}% intervals, shown per test. Absence of a clear trend is not evidence of no change.",

    "claim.nothing.headline": "**Nothing to test.** {region} has no change to measure for this claim.",
    "claim.nothing.student.short": "There is nothing to measure here. The data for {region} stays the same or is too short.",
    "claim.nothing.student.more": "Snow in a hot country, for example, is zero every year. A series that never changes cannot show a trend.",
    "claim.nothing.policymaker.short": "This claim cannot be tested for {region}. The data has no change to measure.",
    "claim.nothing.policymaker.more": "Each series is constant or too short for a trend test. Try another place or a different measure.",
    "claim.nothing.researcher.short": "Every test is insufficient over {years}: each series is constant or shorter than the reliable minimum.",
    "claim.nothing.researcher.more": "No p-values were computed, so no false discovery check applies.",

    "word.claim.supported": "Supported",
    "word.claim.opposed": "Opposed",
    "word.claim.mixed": "Mixed",
    "word.claim.step": "A jump, not a trend",
    "word.claim.unsupported": "Not supported",
    "word.claim.nothing": "Nothing to test",
    "word.outcome.supported": "Yes",
    "word.outcome.opposed": "Opposite way",
    "word.outcome.step": "A jump, not a trend",
    "word.outcome.unsupported": "No clear trend",
    "word.outcome.insufficient": "Nothing to measure",
    "word.amount": "{n} {unit}",
    "word.range": "{lo} to {hi} {unit}",
    "word.n_of": "{n} of {total}",
    "word.one_point": "One point",

    "tile.verdict.label": "Verdict",
    "tile.verdict.note": "Decided by code from the trend tests.",
    "tile.parts.label": "Parts that hold",
    "tile.parts.note": "Clear trends the way the claim says.",
    "tile.years.label": "Years tested",
    "tile.years.note": "One value per year.",
    "tile.cells.label": "Grid cells",
    "tile.cells.note": "NASA grid cells averaged over {region}.",
    "tile.point.label": "Where",
    "tile.point.note": "Live NASA POWER data at one point.",

    "step.trend.title": "Trend test",
    "step.trend.did": "We fitted a Sen line to each yearly series and ran a two-sided Mann-Kendall test, corrected for year-to-year memory.",
    "step.trend.why": "A wet year tends to follow a wet year. The correction asks a trend to be steadier before it counts as clear (p under {alpha}).",
    "step.fdr.title": "False discovery check",
    "step.fdr.did": "We checked the {n_tests} tests in this claim together with the Benjamini-Hochberg method, at a false discovery rate of {fdr_q}.",
    "step.fdr.why": "The more parts a claim has, the more likely one shows a trend by chance. A part that fails this check counts as not supported.",
    "step.jump.title": "Step check",
    "step.jump.did": "For each clear trend we looked for one jump with the Pettitt test and compared a two-level fit with the Sen line.",
    "step.jump.why": "Some records change in one jump, not steadily. On steady trends this check still sees a jump about {step_false_fire}% of the time, so a jump is a hint, not proof.",
    "step.live.title": "Live record",
    "step.live.did": "We read monthly NASA POWER values for {region} from {first_year} to {last_year} and made yearly values from them.",
    "step.live.why": "A point has no stored series, so it uses the longer live POWER record.",
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
        return self._text(key).format_map(vars)

    def _text(self, key: str) -> str:
        return (KM if self.lang == "km" else {}).get(key) or EN[key]

    def has(self, key: str) -> bool:
        return key in EN

    def headline(self, verdict_key: str, facts: dict[str, Fact]) -> list[Seg]:
        """Split the template on ** FIRST, then fill each piece, so a place name cannot inject bold."""
        pieces = self._text(f"{verdict_key}.headline").split("**")
        return [Seg(t=piece.format_map(facts), hl=i % 2 == 1) for i, piece in enumerate(pieces) if piece]

    def tile(self, id: str, value: str, **vars: Fact) -> Tile:
        return Tile(id=id, label=self(f"tile.{id}.label", **vars), value=value, note=self(f"tile.{id}.note", **vars))

    def step(self, id: str, **vars: Fact) -> Step:
        return Step(title=self(f"step.{id}.title", **vars), did=self(f"step.{id}.did", **vars),
                    why=self(f"step.{id}.why", **vars))

    def template(self, verdict_key: str, audience: Audience, facts: dict[str, Fact]) -> tuple[str, str]:
        """(short, more) from "<key>.<audience>.short|more"; falls back to student, then to EN."""
        base = f"{verdict_key}.{audience}" if self.has(f"{verdict_key}.{audience}.short") else f"{verdict_key}.student"
        return self(f"{base}.short", **facts), self(f"{base}.more", **facts)
