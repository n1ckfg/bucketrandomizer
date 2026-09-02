# CONVERSION.py — the 21 records that still differ

`CONVERSION.py` reproduces **756 of 777** records in `testing_sample.json` exactly
(97.3%). This documents the 21 that do not, why each differs, and the evidence that
they are not derivable from the ODT the automated pipeline produces.

Nick Fox-Gieg / 2026-08-27

## Reproducing

```bash
./CONVERSION.sh test.odt          # test.odt -> test.odt_fixed.odt -> sample.json

python3 - <<'EOF'
import json
a = json.load(open('sample.json'))
b = json.load(open('testing_sample.json'))
d = [i for i in range(len(b)) if a[i] != b[i]]
print(f"matching {len(b)-len(d)}/{len(b)}", d)
EOF
```

Expected output:

```
matching 756/777 [49, 63, 157, 167, 220, 265, 304, 320, 347, 350, 376, 408,
                  444, 475, 496, 512, 590, 623, 677, 687, 715]
```

Every one of the 21 has the correct **text** and the correct **line count**. All 21
differ only in where `<b>`/`<i>` tags open and close, or in a single space.

## Root cause

`testing_sample.json` was produced by the manual workflow in `MANUAL_WORKFLOW.txt`,
whose steps 2.2–2.4 route the text through **Microsoft Word** via copy and paste.
`CONVERSION.py` automates the same round trip with LibreOffice headless.

Both produce the same *text*, but they do not produce the same *run structure*.
Word's clipboard paste splits and merges character runs differently from
LibreOffice's `.docx` filter, and the old extractor emitted one tag pair per
`<text:span>` — so the published JSON records Word's run boundaries, not
LibreOffice's. That difference is what the 21 records are made of.

## The four classes

### Class A — run boundary kept vs. merged (9 records)

`49, 63, 157, 265, 350, 376, 408, 677, 715`

The expected output keeps two adjacent tag pairs where we emit one. Same text, same
formatting, different tag placement.

| rec | ours | expected |
|-----|------|----------|
| 49 | `<i>insides of a house </i>` | `<i>insides of a </i><i>house </i>` |
| 63 | `<i>only unexpectedly stumbling across its </i>` | `<i>only unexpectedly stumbling across</i><i> its </i>` |
| 157 | `uurrrRRaaARRURAARRAOW<b>WWWW</b>` | `uurrrRRaaARRURAARRAOW<b>WW</b><b>WW</b>` |
| 265 | `<i>now become vitriol</i>` | `<i>now become </i><i>vitriol</i>` |
| 350 | `<i>stood mute with the home support</i>` | `<i>stood mute </i><i>with the home support</i>` |
| 376 | `<i>Worked Out What Caused The Big Bang. </i>` | `<i>Worked Out What Caused The Big Bang.</i><i> </i>` |
| 408 | `<i>to sweet sweet, self-love...</i>` | `<i>to sweet sweet, </i><i>self-love...</i>` |
| 677 | `<i>of a day undone, a day unmet </i>` | `<i>of a day undone, a day unmet</i><i> </i>` |
| 715 | `<b>The 8th Century Chinese monks who invented gunpowder </b>` | `<b>The 8</b><b>th</b><b> Century Chinese monks who invented gunpowder </b>` |

Source for 715, which is representative — three spans, the middle one superscript,
all three bold:

```xml
<text:p text:style-name="P8" loext:marker-style-name="T2393">
  <text:span text:style-name="T2394">The 8</text:span>
  <text:span text:style-name="T2395">th</text:span>
  <text:span text:style-name="T2394"> Century Chinese monks who invented gunpowder </text:span>
</text:p>
```

**Why not simply stop merging?** Because merging is right in the overwhelming
majority of cases. Rendering one tag pair per span raises the total from 21 to 66
differing records — it introduces 45 *spurious* splits, mostly mid-word artefacts of
the LibreOffice filter (`<i>ever</i><i>ything you've learnt so far</i>`,
`<i>to st</i><i>rain at the chains</i>`) that Word's paste had already collapsed.

**Is there a rule?** No. Every same-formatting run boundary in the document was
labelled against `testing_sample.json`:

```
183 boundaries total:  173 merged   10 split
```

Then the two `<style:text-properties>` sets at each boundary were diffed
attribute by attribute. No attribute separates the groups — every attribute that
appears at a split boundary also appears at many merged ones:

| attribute differing across the boundary | split | merged |
|---|---:|---:|
| `style:text-underline-style` | 5 | 35 |
| `fo:letter-spacing` | 5 | 37 |
| `fo:color` | 4 | 26 |
| `style:text-position` (super/subscript) | 2 | 4 |
| `fo:font-style` | 0 | 17 |

The boundaries the manual file preserves are not a function of anything in *our*
document.

### Class B — emphasis we emit, expected omits (10 records)

`167, 220, 304, 320, 347, 350, 475, 496, 590, 687`

The style chain in `test.odt_fixed.odt` says italic or bold; `testing_sample.json`
has the line plain.

| rec | ours | expected | source of the emphasis |
|-----|------|----------|------------------------|
| 167 | `<i>and yet all became</i>` (+5 more lines) | plain | `T491` = `fo:font-style="italic"` |
| 220 | `<b>THE TEN DEMANDMENTS</b>` | plain | `T634` = `fo:font-weight="bold"` |
| 304 | `<b><i>…</i></b>` | `…` | `T909` = bold + italic |
| 320 | `<b>…</b>` | `…` | `T280` = bold |
| 347 | `<i>If nobody's making anything</i>` (+3 more) | plain | `P10` → `No_20_Spacing` = italic |
| 350 | `<i>… </i>` | `… ` | `T20` = italic |
| 475 | `<i>… </i>` | `… ` | `T1607` = italic |
| 496 | `<i>well there's more and more questions</i>` (+3 more) | plain | `T154` = italic |
| 590 | `<i>"Isn't it a bit early to be hammered Angus?"</i>` | plain | `T20` = italic |
| 687 | `<b>...</b>` | `...` | `Strong_20_Emphasis` |

**Record 590 proves these are unreachable.** One paragraph, two runs, *the same
style name* on both:

```xml
<text:p text:style-name="P151" loext:marker-style-name="T191">
  <text:span text:style-name="T20">"Isn't it a bit early to be hammered Angus?"</text:span>
  <text:span text:style-name="T191"><text:line-break/>and Angus replies<text:line-break/>"</text:span>
  <text:span text:style-name="T20">Yes Jem, that might be true</text:span>
</text:p>
```

`testing_sample.json` renders the first `T20` run plain and the second one italic:

```
"Isn't it a bit early to be hammered Angus?"
and Angus replies
"<i>Yes Jem, that might be true</i>
```

Identical style, identical paragraph, opposite outcomes. No extractor reading this
file can produce both.

**A rule that nearly works, and why it was rejected.** Eight of these ten sit in
paragraphs containing `<text:line-break/>`. Suppressing all emphasis in any
paragraph that contains a line break fixes 167, 347, 496 and 687 — and breaks
record 263, stripping genuine italics that the expected output keeps:

```
ours (with the rule):  And manky low-end drugs at that: "Got any tammies?"
expected:              And manky low-end drugs at that: "<i>Got any tammies?"</i>
```

Net −3 records, at the cost of a rule that is demonstrably wrong. Not applied.

### Class C — opening quote in its own tag pair (2 records)

`444, 512`

`CONVERSION.py` already moves a line-leading `“` outside the emphasis tags — that
normalisation alone fixes 24 records. These two want the quote in its *own* tag pair
instead:

| rec | ours | expected |
|-----|------|----------|
| 444 | `“it's cool, it screens out all the wimps”` | `<i>“</i>it's cool, it screens out all the wimps”` |
| 512 | `“<i>you laugh at me because i'm different</i>` | `<i>“</i><i>you laugh at me because i'm different</i>` |

In both, our source has the quote inside a single `Emphasis` span with the rest of
the line, so there is no boundary to split on:

```xml
<text:p text:style-name="P8">
  <text:span text:style-name="Emphasis">
    <text:span text:style-name="T1728">“you laugh at me because i'm different</text:span>
  </text:span>
</text:p>
```

This is Class A wearing a different hat: Word had the smart quote as a separate run
(an autocorrect artefact), LibreOffice does not.

### Class D — whitespace (2 records)

`220, 623`

**623** — the paragraph ends with `<text:span text:style-name="T2071"><text:tab/></text:span>`.
The expected output renders that tab as a single space; we drop it, as the original
extractor did.

```
ours:      <i>have banquets with less than this...</i>
expected:  <i>have banquets with less than this... </i>
```

Rendering `<text:tab/>` as a space fixes 623 and breaks 743, where the expected
output drops it. Net zero, so tabs are still dropped.

**220** — three lines carry a trailing space we keep and the expected output strips:

```
ours:      'EVERYTHING HAS BEEN THOUGHT AND '
expected:  'EVERYTHING HAS BEEN THOUGHT AND'
```

There is no general rule here either: trailing spaces are preserved throughout the
rest of the file (record 9's `'in the greenery round Roslyn Abbey '`, record 64's
`'This is a crappy ass world. '`), and in 220 the space is literal text inside the
span, not a `<text:s/>` element.

## Alternative pipelines tested

All measured against the same 777 records.

| intermediate | differing records |
|---|---:|
| `odt → docx → odt` (LibreOffice) — **current** | **21** |
| `odt → doc → odt` (LibreOffice) | 21 |
| `odt → docx → odt → docx → odt` (LibreOffice) | 21 |
| `odt → docx → odt` with **real Microsoft Word** for the first leg (AppleScript, open + save-as) | 299 |

The three LibreOffice variants land on the *exact same 21 records*, so the residual
is not an artefact of the chosen intermediate format. Driving Word itself is much
worse: the manual workflow does not open the ODT in Word, it pastes clipboard
content into a blank document, and Word's ODF import filter behaves nothing like its
clipboard paste.

## What would close the gap

Only one of three things:

1. **Automate the actual clipboard paste** — script Word to receive a paste from
   LibreOffice, as a human does in `MANUAL_WORKFLOW.txt` steps 2.2–2.4. Fragile
   (GUI scripting, Accessibility permissions, no headless mode) and unverified.

2. **Regenerate `testing_sample.json`** from the current pipeline and accept the
   21 records as the new baseline. The output is arguably *more* faithful to
   `test.odt` than the manual one — records 590 and 263 show the manual path
   dropping emphasis the source document actually carries.

3. **Hand-patch the 21** as a fixture on top of the generated output.

Nothing else in the extractor is left to fix: the remaining differences are
properties of the intermediate document, not of the extraction logic.
