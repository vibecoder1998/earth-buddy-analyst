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
    "note.unmeasured": "{parts} could not be measured.",
    "note.rank_points": "Each place is the NASA POWER grid cell, about 50 km across, at its NASA SEDAC centre point.",
    "note.rank_shared_cell": "{names} fall in one grid cell, so they get the same numbers and count as a tie.",
    "note.rank_more_tied": "{n} more places outside the top {top_n} are also too close to tell apart from the leader.",

    "claim.supported.headline": "**Supported.** Every part of this claim that could be measured shows a clear trend the way it says.",
    "claim.supported.student.short": "The data for {region} backs this claim. Every part that could be measured shows a clear trend the way the claim says.{unmeasured}",
    "claim.supported.student.more": "We tested each part against NASA data for {years}. Each part we could measure moved steadily the way the claim says, and none of them looks like chance. A trend says what changed, not why.",
    "claim.supported.policymaker.short": "Every part of this claim that could be measured holds for {region}.{unmeasured} The trends are clear enough to plan around.",
    "claim.supported.policymaker.more": "Each part that could be measured shows a steady change over {years} in NASA data, and each passes a check against chance findings. The data shows the change, not its cause.",
    "claim.supported.researcher.short": "{n_supported} of {n_live} measurable tests show a clear trend in the claimed direction over {years} (memory-corrected two-sided Mann-Kendall, p under {alpha}), each surviving Benjamini-Hochberg at {fdr_q}. Sen slopes per decade: {slopes}.{unmeasured}",
    "claim.supported.researcher.more": "Slopes are Sen slopes per decade with {ci_pct}% intervals, shown per test. Pettitt and a two-level fit flag a single jump; none was found for a supported part.",

    "claim.opposed.headline": "**Opposed.** Every part of this claim that could be measured shows a clear trend the other way.",
    "claim.opposed.student.short": "The data for {region} goes against this claim. Every part that could be measured changed the other way.{unmeasured}",
    "claim.opposed.student.more": "We tested each part against NASA data for {years}. Each part we could measure moved steadily, but in the opposite direction from the claim. A trend says what changed, not why.",
    "claim.opposed.policymaker.short": "Every part of this claim that could be measured runs the other way in {region}.{unmeasured} Plans based on the claim would point the wrong way.",
    "claim.opposed.policymaker.more": "Each part that could be measured shows a clear change over {years} in NASA data, opposite to the claim, and each passes a check against chance findings.",
    "claim.opposed.researcher.short": "{n_opposed} of {n_live} measurable tests show a clear trend against the claimed direction over {years} (memory-corrected two-sided Mann-Kendall, p under {alpha}), each surviving Benjamini-Hochberg at {fdr_q}. Sen slopes per decade: {slopes}.{unmeasured}",
    "claim.opposed.researcher.more": "Slopes are Sen slopes per decade with {ci_pct}% intervals, shown per test.",

    "claim.mixed.headline": "**Mixed.** Some parts of this claim hold, and some go the other way.",
    "claim.mixed.student.short": "Part of this claim is right for {region}, and part is wrong. Some things changed the way it says, and some the other way.{unmeasured}",
    "claim.mixed.student.more": "We tested each part against NASA data for {years}. Look at each row to see which parts hold. A trend says what changed, not why.",
    "claim.mixed.policymaker.short": "Some parts of this claim hold for {region}, and others run the other way. Treat the parts separately.{unmeasured}",
    "claim.mixed.policymaker.more": "Each row shows one part tested against NASA data over {years}, with a check against chance findings across the claim.",
    "claim.mixed.researcher.short": "Of {n_live} measurable tests over {years}, {n_supported} show a clear trend as claimed and {n_opposed} a clear trend against it (memory-corrected two-sided Mann-Kendall, p under {alpha}, Benjamini-Hochberg at {fdr_q}). Sen slopes per decade: {slopes}.{unmeasured}",
    "claim.mixed.researcher.more": "Slopes are Sen slopes per decade with {ci_pct}% intervals, shown per test.",

    "claim.step.headline": "**A jump, not a trend.** The record changed in one jump, not steadily.",
    "claim.step.student.short": "The data for {region} changed, but in one jump, not as a steady trend. That is a different story from the claim.{unmeasured}",
    "claim.step.student.more": "We tested each part against NASA data for {years}. The change came all at once around one year. On steady trends this check still sees a jump about {step_false_fire}% of the time, so treat it as a hint.",
    "claim.step.policymaker.short": "The change in {region} came in one jump, not steadily. Check what happened around that year before planning on a trend.{unmeasured}",
    "claim.step.policymaker.more": "A sudden jump can come from a real event or from a change in how the data was made. On steady trends this check still sees a jump about {step_false_fire}% of the time.",
    "claim.step.researcher.short": "No test is a steady trend; at least one clear change over {years} is better fit by two levels (a Pettitt change point, and a two-level fit that beats the Sen line). Sen slopes per decade: {slopes}.{unmeasured}",
    "claim.step.researcher.more": "Measured on simulated steady trends, the step check fires about {step_false_fire}% of the time. Benjamini-Hochberg at {fdr_q} across the claim.",

    "claim.unsupported.headline": "**Not supported.** The data for {region} is not clear enough to back this claim.",
    "claim.unsupported.student.short": "The data for {region} does not back this claim. Not every part shows a clear trend the way the claim says.{unmeasured}",
    "claim.unsupported.student.more": "We tested each part against NASA data for {years}. Not clear does not mean nothing is happening. It means this record cannot tell yet.",
    "claim.unsupported.policymaker.short": "The data for {region} cannot confirm this claim. It is not proof the opposite is true.{unmeasured}",
    "claim.unsupported.policymaker.more": "Not every part that could be measured shows a change the way the claim says that passes a check against chance findings over {years}. A longer record may tell.",
    "claim.unsupported.researcher.short": "{n_supported} of {n_live} measurable tests show a clear trend in the claimed direction that survives Benjamini-Hochberg at {fdr_q} over {years} (memory-corrected two-sided Mann-Kendall, p under {alpha}). Sen slopes per decade: {slopes}.{unmeasured}",
    "claim.unsupported.researcher.more": "Slopes are Sen slopes per decade with {ci_pct}% intervals, shown per test. Absence of a clear trend is not evidence of no change.",

    "claim.nothing.headline": "**Nothing to test.** {region} has no change to measure for this claim.",
    "claim.nothing.student.short": "There is nothing to measure here. The data for {region} stays the same or is too short.",
    "claim.nothing.student.more": "Snow in a hot country, for example, is zero every year. A series that never changes cannot show a trend.",
    "claim.nothing.policymaker.short": "This claim cannot be tested for {region}. The data has no change to measure.",
    "claim.nothing.policymaker.more": "Each series is constant or too short for a trend test. Try another place or a different measure.",
    "claim.nothing.researcher.short": "Every test is insufficient over {years}: each series is constant or shorter than the reliable minimum.",
    "claim.nothing.researcher.more": "No p-values were computed, so no false discovery check applies.",

    "trend.clear.headline": "{place}'s {noun} is **clearly {direction}**: about {change_per_decade} every ten years since {first_year}.",
    "trend.clear.student.short": "{place}'s {noun} is clearly {direction}. It moved steadily one way, too steadily to be chance.",
    "trend.clear.student.more": "We looked at one value per year from NASA data for {period}. The values moved steadily one way, more than the usual ups and downs explain. Next to the usual swing from year to year, the change is {size_word}. A trend says what changed, not why.",
    "trend.clear.policymaker.short": "{place}'s {noun} is clearly {direction}, by about {change_per_decade} every ten years. The trend is clear enough to plan around.",
    "trend.clear.policymaker.more": "The change holds across {n_years} years of NASA data ({period}) and passes a test that allows for runs of similar years. Next to the usual swing from year to year, it is {size_word}. The data shows the change, not its cause.",
    "trend.clear.researcher.short": "Sen slope {change_per_decade} per decade ({ci_pct}% interval {change_per_decade_95pct_range}) over {period}, n = {n_years}. Two-sided {test}, p-value {p_value}.",
    "trend.clear.researcher.more": "The test is corrected for serial correlation with a variance inflation factor. The typical swing, the scaled median absolute deviation of the residuals, is {typical_swing}. Clear means p under {alpha}.",

    "trend.likely.headline": "{place}'s {noun} is **probably {direction}**, but the record is not long enough to be sure.",
    "trend.likely.student.short": "{place}'s {noun} is probably {direction}, but we cannot be sure yet. The change could still be chance.",
    "trend.likely.student.more": "We looked at one value per year from NASA data for {period}. The values lean one way, but not steadily enough to rule out chance. A longer record may tell. A trend says what changed, not why.",
    "trend.likely.policymaker.short": "{place}'s {noun} is probably {direction}, by about {change_per_decade} every ten years, but this is not certain.",
    "trend.likely.policymaker.more": "The record for {period} leans one way without passing the usual bar for a clear trend. Treat it as an early signal, not a finding.",
    "trend.likely.researcher.short": "Sen slope {change_per_decade} per decade ({ci_pct}% interval {change_per_decade_95pct_range}) over {period}, n = {n_years}. Two-sided {test}, p-value {p_value}, under {likely} but not under {alpha}.",
    "trend.likely.researcher.more": "The test is corrected for serial correlation. The typical swing is {typical_swing}.",

    "trend.unclear.headline": "**No clear change** in {place}'s {noun} since {first_year}.",
    "trend.unclear.student.short": "We cannot see a clear change in {place}'s {noun}. That does not mean nothing is happening.",
    "trend.unclear.student.more": "We looked at one value per year from NASA data for {period}. The ups and downs are too large to tell any steady change apart from chance. Not clear does not mean nothing is happening. It means this record cannot tell yet.",
    "trend.unclear.policymaker.short": "The data for {place} shows no clear change in {noun}. It is not proof that nothing is changing.",
    "trend.unclear.policymaker.more": "Over {period} the yearly values vary more than any steady trend in them. A longer record or a larger area may tell.",
    "trend.unclear.researcher.short": "No clear trend over {period}, n = {n_years}. Sen slope {change_per_decade} per decade ({ci_pct}% interval {change_per_decade_95pct_range}), two-sided {test}, p-value {p_value}.",
    "trend.unclear.researcher.more": "Absence of a clear trend is not evidence of no change. The typical swing is {typical_swing}.",

    "trend.too_short.headline": "**Too few years** to judge.",
    "trend.too_short.student.short": "There are too few years of data to judge a trend in {place}'s {noun}. Try a longer period.",
    "trend.too_short.student.more": "This record has {n_years} yearly values. We need at least {reliable} before we call a change clear or not.",
    "trend.too_short.policymaker.short": "There is not enough data to judge a trend in {place}'s {noun}. Use a longer period before deciding anything.",
    "trend.too_short.policymaker.more": "The record has {n_years} years, under the {reliable} the test needs to be reliable.",
    "trend.too_short.researcher.short": "Only {n_years} yearly values over {period}, under the minimum of {reliable} for a reliable Mann-Kendall test. The Sen slope of {change_per_decade} per decade is for reference only.",
    "trend.too_short.researcher.more": "The p-value of {p_value} is not interpreted at this length.",

    "scan.changes.headline": "**{n_clear} of {n_tested} measures** in {region} show a clear change after the check for many tests.",
    "scan.changes.student.short": "We tested every measure we have for {region}. These changed clearly, even after the check for chance: {clear_measures}.",
    "scan.changes.student.more": "Each measure got its own trend test on NASA data for {years}. When you test many measures, some look like they change just by chance, so we ran a false discovery check across all of them. Only the ones that passed count. A trend says what changed, not why.",
    "scan.changes.policymaker.short": "{n_clear} of {n_tested} measures for {region} show a clear change over {years}: {clear_measures}.",
    "scan.changes.policymaker.more": "These changes pass a check against chance findings across every measure tested. Picking one and testing it again as a claim is a second look at the same data, so treat that result with more caution.",
    "scan.changes.researcher.short": "{n_clear} of {n_tested} series show a clear trend over {years} (memory-corrected two-sided Mann-Kendall, p under {alpha}) that survives Benjamini-Hochberg at {fdr_q} across the scan.",
    "scan.changes.researcher.more": "Rows are sorted by p and carry q-values. Slopes are Sen slopes per decade. {n_skipped} measures had no usable series here and were not tested.",

    "scan.no_change.headline": "**{n_clear} of {n_tested} measures** in {region} show a clear change after the check for many tests.",
    "scan.no_change.student.short": "We tested every measure we have for {region}, and none shows a clear change once we allow for chance.",
    "scan.no_change.student.more": "Each measure got its own trend test on NASA data for {years}. When you test many measures, some look like they change just by chance, so we ran a false discovery check across all of them. None passed. Not clear does not mean nothing is happening.",
    "scan.no_change.policymaker.short": "None of the {n_tested} measures for {region} shows a clear change over {years} after the check for many tests.",
    "scan.no_change.policymaker.more": "This is not proof that nothing is changing. A longer record or a larger area may tell.",
    "scan.no_change.researcher.short": "No series of {n_tested} shows a clear trend over {years} (memory-corrected two-sided Mann-Kendall, p under {alpha}) that survives Benjamini-Hochberg at {fdr_q}.",
    "scan.no_change.researcher.more": "Rows are sorted by p and carry q-values. {n_skipped} measures had no usable series here and were not tested.",
    "where.clear.headline": "**{n_clear} of {total} grid cells** around {place} show a clear {change} in {noun}. The strongest is {bearing}.",
    "where.clear.student.short": "Around {place}, more NASA grid cells show a clear {change} in {noun} than chance alone would give. The strongest change is {bearing}.",
    "where.clear.student.more": "We split a {box_deg}° box around {place} into NASA grid cells and tested each cell's yearly values for {period}. Chance alone would make about {by_chance} cells look clear, and more than that did. The map shows which cells changed most. A trend says what changed, not why.",
    "where.clear.policymaker.short": "{n_clear} of {total} grid cells around {place} show a clear {change} in {noun}, more than chance alone would give. The strongest change, {strongest_change} every ten years, is {bearing}.",
    "where.clear.policymaker.more": "Each cell was tested on its own over {period}. Use the map to see where the change concentrates, and read a single clear cell with care: about {by_chance} of {total} can look clear by chance. The data shows the change, not its cause.",
    "where.clear.researcher.short": "{n_clear_all} of {total} cells have p under {alpha} ({n_clear} in the dominant direction) on a two-sided Mann-Kendall test corrected for serial correlation, over {period}. Strongest Sen slope {strongest_change} per decade, {bearing}.",
    "where.clear.researcher.more": "No false-discovery correction across cells: at {alpha}, about {by_chance} of {total} cells are expected to pass by chance. Neighbouring cells share weather, so they are not independent tests. Grid cells are {cell_size}.",

    "where.chance.headline": "**Only {n_clear} of {total} grid cells** around {place} show a clear {change} in {noun}, about what chance alone gives.",
    "where.chance.student.short": "Around {place}, only a few NASA grid cells show a clear {change} in {noun}, about what chance alone gives. So we cannot point to where it is changing.",
    "where.chance.student.more": "We tested each grid cell's yearly values for {period}. With {total} cells, about {by_chance} can look clear by chance even where nothing changes. The largest change is {bearing}, but it may be chance. Not clear does not mean nothing is happening.",
    "where.chance.policymaker.short": "The data around {place} does not show where {noun} is changing: {n_clear} of {total} grid cells look clear, about what chance gives.",
    "where.chance.policymaker.more": "Over {period}, no part of the {box_deg}° box stands out from chance. A longer record or a larger area may tell.",
    "where.chance.researcher.short": "{n_clear_all} of {total} cells have p under {alpha} over {period} (two-sided Mann-Kendall, corrected for serial correlation), against about {by_chance} expected by chance. Strongest Sen slope {strongest_change} per decade, {bearing}.",
    "where.chance.researcher.more": "No false-discovery correction across cells. Neighbouring cells share weather, so they are not independent tests. Grid cells are {cell_size}.",

    "where.too_short.headline": "**Too few years** to judge where {noun} is changing around {place}.",
    "where.too_short.student.short": "There are too few years of data to judge where {noun} is changing around {place}. Try a longer period.",
    "where.too_short.student.more": "Each grid cell has at most {n_years} yearly values. We need more before we call a change clear or not.",
    "where.too_short.policymaker.short": "There is not enough data to judge where {noun} is changing around {place}. Use a longer period before deciding anything.",
    "where.too_short.policymaker.more": "Each cell has at most {n_years} years over {period}, too few for a reliable test.",
    "where.too_short.researcher.short": "At most {n_years} yearly values per cell over {period}, too few for a reliable Mann-Kendall test. The Sen slopes are for reference only.",
    "where.too_short.researcher.more": "The per-cell p-values are not interpreted at this length.",

    "rank.clear_leader.headline": "**{place}** has the {ranked_by}, and its lead is clear.",
    "rank.clear_leader.student.short": "Among {region}, {place} has the {ranked_by}. Its lead over every other place is too big to be chance.",
    "rank.clear_leader.student.more": "We measured each place with NASA data for {period} and compared each one with {place}. Every other place differed from it clearly, even after the check for chance across all the comparisons. A ranking says which place leads, not why.",
    "rank.clear_leader.policymaker.short": "Among {region}, {place} has the {ranked_by}, and the gap to every other place is clear.",
    "rank.clear_leader.policymaker.more": "{runner_up} comes second. Each comparison with the leader passes a check against chance findings. The data shows the difference, not its cause.",
    "rank.clear_leader.researcher.short": "{place} ranks first ({leader_value}, {ci_pct}% interval {leader_range}, own trend p-value {leader_p}). Each other place shows a clear gap to it ({gap_test}, Benjamini-Hochberg at {fdr_q}).",
    "rank.clear_leader.researcher.more": "{n_clear} of {n_places} places have a clear own trend after Benjamini-Hochberg at {fdr_q}. {n_skipped} places were skipped for missing or short records. Period {period}.",

    "rank.tied.headline": "**{place}** has the {ranked_by}, but {tied_others} too close to tell apart.",
    "rank.tied.student.short": "Among {region}, {place} has the {ranked_by}, but some others are so close that we cannot say which truly leads.",
    "rank.tied.student.more": "We measured each place with NASA data for {period} and compared each one with {place}. For some places the gap is small enough to be chance, so the order at the top is not settled. Not clear does not mean they are the same.",
    "rank.tied.policymaker.short": "Among {region}, {place} has the {ranked_by}, but {tied_others} too close to call. Treat the top places as one group.",
    "rank.tied.policymaker.more": "The places tied with the leader are marked in the list. A longer record may separate them. The data shows the difference, not its cause.",
    "rank.tied.researcher.short": "{place} ranks first ({leader_value}, {ci_pct}% interval {leader_range}, own trend p-value {leader_p}), but {n_tied} other places show no clear gap to it ({gap_test}, Benjamini-Hochberg at {fdr_q}).",
    "rank.tied.researcher.more": "{n_clear} of {n_places} places have a clear own trend after Benjamini-Hochberg at {fdr_q}. {n_skipped} places were skipped for missing or short records. Period {period}.",

    "rank.none.headline": "**None of these {n_places} places can be told apart.** {place} has the {ranked_by}, but not by a clear margin.",
    "rank.none.student.short": "Among {region}, {place} has the {ranked_by}, but every other place is too close to tell apart. The data cannot say which place leads.",
    "rank.none.student.more": "We measured each place with NASA data for {period} and compared each one with {place}. No gap was big enough to rule out chance. Not clear does not mean they are the same.",
    "rank.none.policymaker.short": "No place among {region} stands out on the {ranked_by}. Do not plan around this order.",
    "rank.none.policymaker.more": "{place} is first only by a margin that chance can explain. A longer record may separate the places. The data shows the difference, not its cause.",
    "rank.none.researcher.short": "{place} ranks first ({leader_value}, {ci_pct}% interval {leader_range}), but no other place shows a clear gap to it ({gap_test}, Benjamini-Hochberg at {fdr_q}).",
    "rank.none.researcher.more": "{n_clear} of {n_places} places have a clear own trend after Benjamini-Hochberg at {fdr_q}. {n_skipped} places were skipped for missing or short records. Period {period}.",

    "word.direction.rising": "rising",
    "word.direction.falling": "falling",
    "word.direction.flat": "flat",
    "word.level.clear": "clear",
    "word.level.likely": "likely, not certain",
    "word.level.unclear": "not clear",
    "word.level.too_short": "too few years",
    "word.size.small": "small",
    "word.size.moderate": "moderate",
    "word.size.large": "large",
    "word.size.none": "no change",
    "word.test.mann-kendall": "Mann-Kendall test",
    "word.test.mann-kendall-vif": "Mann-Kendall test corrected for year-to-year memory",
    "word.coin": "as unlikely by chance as {n} heads in a row",
    "word.coin_one": "as unlikely by chance as one coin landing heads",
    "word.coin_none": "not surprising by chance",
    "word.percent": "{n}%",
    "word.part.trend": "Slow trend",
    "word.part.seasonal": "Yearly cycle",
    "word.part.residual": "What is left",
    "word.cycle": "Each month, {late} against {early}",
    "month.1": "January", "month.2": "February", "month.3": "March", "month.4": "April", "month.5": "May",
    "month.6": "June", "month.7": "July", "month.8": "August", "month.9": "September", "month.10": "October",
    "month.11": "November", "month.12": "December",

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
    "word.point": "the point {lat}, {lon}",
    "word.slope": "{label} {change} ({ci_pct}% interval {range}, p-value {p})",
    "word.slope_none": "{label} not testable",
    "word.change.rise": "rise",
    "word.change.fall": "fall",
    "word.bearing.centre": "close to the centre",
    "word.bearing.north": "to the north",
    "word.bearing.north-east": "to the north-east",
    "word.bearing.east": "to the east",
    "word.bearing.south-east": "to the south-east",
    "word.bearing.south": "to the south",
    "word.bearing.south-west": "to the south-west",
    "word.bearing.west": "to the west",
    "word.bearing.north-west": "to the north-west",
    "word.per_decade": "{unit} per decade",
    "word.cell_size": "{lat}° × {lon}°",
    "word.where_chart": "{variable}: change every ten years in each grid cell",

    "word.rank_by.change.highest.up": "fastest rise in {noun}",
    "word.rank_by.change.highest.down": "slowest fall in {noun}",
    "word.rank_by.change.lowest.down": "fastest fall in {noun}",
    "word.rank_by.change.lowest.up": "slowest rise in {noun}",
    "word.rank_by.level.highest": "highest {noun} in recent years",
    "word.rank_by.level.lowest": "lowest {noun} in recent years",
    "word.rank_chart.change": "{variable}: change every ten years at each place",
    "word.rank_chart.level": "{variable}: average of recent years at each place",
    "word.gap_test.change": "Mann-Kendall test on the year-by-year difference",
    "word.gap_test.level": "Wilcoxon signed-rank test on the year-by-year difference",
    "word.group.southeast_asia_capitals": "Southeast Asian capitals",
    "word.group.cambodia_provinces": "Cambodian provinces",
    "word.group.countries": "countries",
    "word.group.places": "the named places",
    "word.group.listed": "the places you chose",
    "word.others_one": "one other place is",
    "word.others": "{n} others are",
    "word.rank_row": "{value} {unit}, {ci_pct}% interval {lo} to {hi}",

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
    "tile.clear_count.label": "Clear changes",
    "tile.clear_count.note": "After the false discovery check at {fdr_q}.",
    "tile.change.label": "Change every ten years",
    "tile.change.note": "The {ci_pct}% range is {change_per_decade_95pct_range}.",
    "tile.sure.label": "How sure",
    "tile.sure.note": "p-value {p_value}, {coin}.",
    "tile.peak_month.label": "Peak month",
    "tile.peak_month.note": "The top of the yearly cycle over the last {cycle_years} years.",
    "tile.highest_year.label": "Highest year",
    "tile.highest_year.note": "The year with the highest value in {period}.",
    "tile.clear_cells.label": "Cells with a clear {change}",
    "tile.clear_cells.note": "About {by_chance} of {total} can look clear by chance.",
    "tile.strongest.label": "Strongest change",
    "tile.strongest.note": "Every ten years, {bearing}.",
    "tile.nearest.label": "Nearest cell",
    "tile.nearest.note": "Every ten years at the cell nearest {place}, p-value {nearest_p}.",

    "tile.leader.label": "Leader",
    "tile.leader.note": "{leader_value}, {ci_pct}% interval {leader_range}.",
    "tile.tied.label": "Too close to tell from the leader",
    "tile.tied.note": "After the false discovery check at {fdr_q}.",
    "tile.ranked.label": "Places ranked",
    "tile.ranked.note": "Skipped for too little data: {n_skipped}.",

    "step.trend.title": "Trend test",
    "step.trend.did": "We fitted a Sen line to each yearly series and ran a two-sided Mann-Kendall test, corrected for year-to-year memory.",
    "step.trend.why": "A wet year tends to follow a wet year. The correction asks a trend to be steadier before it counts as clear (p under {alpha}).",
    "step.fdr.title": "False discovery check",
    "step.fdr.did": "We checked the {n_live} measurable tests in this claim together with the Benjamini-Hochberg method, at a false discovery rate of {fdr_q}.",
    "step.fdr.why": "The more parts a claim has, the more likely one shows a trend by chance. A part that fails this check counts as not supported.",
    "step.jump.title": "Step check",
    "step.jump.did": "For each clear trend we looked for one jump with the Pettitt test and compared a two-level fit with the Sen line.",
    "step.jump.why": "Some records change in one jump, not steadily. On steady trends this check still sees a jump about {step_false_fire}% of the time, so a jump is a hint, not proof.",
    "step.scan.title": "Every measure",
    "step.scan.did": "We ran a two-sided Mann-Kendall test, corrected for year-to-year memory, on each of the {n_tested} yearly series for {region} over {years}.",
    "step.scan.why": "A scan looks at everything at once, so no measure was picked after seeing its data.",
    "step.scan_fdr.title": "False discovery check",
    "step.scan_fdr.did": "We checked all {n_tested} tests together with the Benjamini-Hochberg method, at a false discovery rate of {fdr_q}.",
    "step.scan_fdr.why": "Among many tests a few show a trend by chance. A measure counts as a clear change only when its trend is clear (p under {alpha}) and it passes this check.",
    "step.live.title": "Live record",
    "step.live.did": "We read monthly NASA POWER values for {region} from {first_year} to {last_year} and made yearly values from them.",
    "step.live.why": "A point has no stored series, so it uses the longer live POWER record.",
    "step.fetched_point.title": "Live record",
    "step.fetched_point.did": "We read monthly NASA POWER values ({data_source}) at {place} for {period}.",
    "step.fetched_point.why": "A point has no stored series, so it uses the whole live POWER record, from the first year this measure exists to the last complete year.",
    "step.fetched_area.title": "Stored record",
    "step.fetched_area.did": "We read the yearly {variable} series for {place}, averaged over {cells} NASA grid cells, for {period}.",
    "step.fetched_area.why": "Stored area series cover {record}, the years every area dataset shares. A single point reaches further back through live NASA POWER data.",
    "step.yearly.title": "One value per year",
    "step.yearly.did": "We turned the monthly values into one value per year, and kept a year only when all its months were there.",
    "step.yearly.why": "A year with missing months would look wetter, drier, warmer or cooler than it was.",
    "step.seasons.title": "Seasons apart",
    "step.seasons.did": "We split the monthly record into a slow trend, a yearly cycle, and what is left, with STL.",
    "step.seasons.why": "The seasons can hide a slow change. The yearly cycle explains {seasonal_share} of the month-to-month variation.",
    "step.sen.title": "Sen line",
    "step.sen.did": "We fitted a Sen line to the {n_years} yearly values. Its slope is the median of the slopes between every pair of years.",
    "step.sen.why": "One odd year cannot pull a median the way it pulls an average.",
    "step.size.title": "How big",
    "step.size.did": "We compared the change with the typical swing from year to year, {typical_swing}.",
    "step.size.why": "A change that takes many years to move one typical swing is small, even when it is clear. This one is {size_word}.",
    "step.tested.title": "Trend test",
    "step.tested.did": "We ran a two-sided {test} on the yearly values. The p-value is {p_value}.",
    "step.tested.why": "A wet year tends to follow a wet year. The correction asks a trend to be steadier before it counts as clear (p under {alpha}), or likely (p under {likely}), and it needs at least {reliable} years.",
    "step.not_clear.title": "What the level means",
    "step.not_clear.did": "We call this change {certainty}.",
    "step.not_clear.why": "No clear change never means nothing is happening. It means this record cannot tell a change apart from chance.",
    "step.grid.title": "NASA grid around the place",
    "step.grid.did": "We read monthly NASA POWER values ({data_source}) for every grid cell in a {box_deg}° box around {place}: {total} cells of {cell_size}, for {period}.",
    "step.grid.why": "One point can hide what happens next to it. A box of cells shows where the change is strongest.",
    "step.cell_trend.title": "Trend in each cell",
    "step.cell_trend.did": "In each cell with at least {min_years} years, we fitted a Sen line and ran a two-sided Mann-Kendall test, corrected for year-to-year memory.",
    "step.cell_trend.why": "A cell counts as clear when its p-value is under {alpha}. The map colours each cell by its change every ten years and outlines the clear ones.",
    "step.no_fdr.title": "Many cells, some by chance",
    "step.no_fdr.did": "We did not correct for testing {total} cells at once.",
    "step.no_fdr.why": "With {total} cells, about {by_chance} can look clear by chance even where nothing changes. Read one clear cell with care; a cluster of them means more.",
    "step.rank_data.title": "Same years for every place",
    "step.rank_data.did": "We read the yearly {variable} series for {n_places} places, {period}.",
    "step.rank_data.why": "Every place gets the same measure and the same years, so the ranking compares like with like.",
    "step.rank_change.title": "Change at each place",
    "step.rank_change.did": "We fitted a Sen line to each place's yearly values and ran a two-sided Mann-Kendall test, corrected for year-to-year memory.",
    "step.rank_change.why": "Places rank by their change every ten years. The line around each dot is its {ci_pct}% range.",
    "step.rank_level.title": "Recent level at each place",
    "step.rank_level.did": "We took each place's average over its last {level_years} years, with a {ci_pct}% interval.",
    "step.rank_level.why": "An average of several years is steadier than any one year.",
    "step.rank_fdr.title": "False discovery check",
    "step.rank_fdr.did": "We checked the {n_places} trend tests together with the Benjamini-Hochberg method, at a false discovery rate of {fdr_q}.",
    "step.rank_fdr.why": "Among many places a few show a trend by chance. A place's own trend counts as clear only when it is clear (p under {alpha}) and passes this check.",
    "step.rank_gap_change.title": "Is the lead real?",
    "step.rank_gap_change.did": "We compared each place with {place} on the year-by-year difference between their two series, with a Mann-Kendall test, and checked those comparisons together with Benjamini-Hochberg at {fdr_q}.",
    "step.rank_gap_change.why": "When the difference has no clear trend, this record cannot tell the two rates of change apart.",
    "step.rank_gap_level.title": "Is the lead real?",
    "step.rank_gap_level.did": "We compared each place with {place} on the differences between their two series over the last {level_years} years, with a Wilcoxon signed-rank test, and checked those comparisons together with Benjamini-Hochberg at {fdr_q}.",
    "step.rank_gap_level.why": "When the differences do not lean clearly one way, this record cannot tell the two levels apart.",
    "step.rank_cells.title": "Shared grid cells",
    "step.rank_cells.did": "Each place is the NASA POWER grid cell, about 50 km across, at its NASA SEDAC centre point.",
    "step.rank_cells.why": "Two names in one grid cell get the same numbers, so we count them as a tie.",
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
        segs = [Seg(t=piece.format_map(facts), hl=i % 2 == 1) for i, piece in enumerate(pieces) if piece]
        segs[0].t = _capitalize_first(segs[0].t)
        return segs

    def tile(self, id: str, value: str, **vars: Fact) -> Tile:
        return Tile(id=id, label=self(f"tile.{id}.label", **vars), value=value, note=self(f"tile.{id}.note", **vars))

    def step(self, id: str, **vars: Fact) -> Step:
        return Step(title=self(f"step.{id}.title", **vars), did=self(f"step.{id}.did", **vars),
                    why=self(f"step.{id}.why", **vars))

    def template(self, verdict_key: str, audience: Audience, facts: dict[str, Fact]) -> tuple[str, str]:
        """(short, more) from "<key>.<audience>.short|more"; falls back to student, then to EN."""
        base = f"{verdict_key}.{audience}" if self.has(f"{verdict_key}.{audience}.short") else f"{verdict_key}.student"
        return _capitalize_first(self(f"{base}.short", **facts)), _capitalize_first(self(f"{base}.more", **facts))


def _capitalize_first(s: str) -> str:
    return s[:1].upper() + s[1:]
