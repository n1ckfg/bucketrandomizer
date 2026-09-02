# CONVERSION.py — automating the ODT-to-JSON pipeline

---

## What was being automated

`MANUAL_WORKFLOW.txt` describes a hand process: run an extractor over the author's
`.odt`, and — when the formatting comes out wrong — first launder the document by
copying all of its text in LibreOffice, pasting it into a blank Word document, saving
as `.docx`, reopening that in LibreOffice, saving as `.odt`, and doing a find-and-replace
on newlines. Then extract again and upload the JSON.

`CONVERSION.py` automates both halves: a formatting-fix step, and an extraction step
that walks the ODF tree with `odfpy` and emits `[{index, body}, …]`, with `<b>` and
`<i>` reconstructed from the style cascade and paragraphs grouped into sections by runs
of blank lines.

The through-line of everything below is **run boundaries** — where one `<text:span>`
ends and the next begins. Almost every difficulty in this project turned out to be
about them, and the resolution was to stop caring about them.

---

## Act 1 — chasing Word's clipboard

*(`REPORT.md`, against `testing_sample.json`, 777 records)*

The first automated pipeline replaced the manual Word laundering with a LibreOffice
headless round trip: `odt → docx → odt` via `soffice --headless`, then a newline and
curly-apostrophe pass over `content.xml`. It reproduced **756 of 777** published
records exactly.

All 21 stragglers had the right text and the right line count. They differed only in
where `<b>`/`<i>` opened and closed, or by a single space:

| | ours | expected |
|---|---|---|
| rec 49 | `<i>insides of a house </i>` | `<i>insides of a </i><i>house </i>` |
| rec 715 | `<b>The 8th Century Chinese monks…</b>` | `<b>The 8</b><b>th</b><b> Century Chinese monks…</b>` |

The cause: the published JSON records **Word's** run boundaries, not LibreOffice's.
Word's clipboard paste splits and merges character runs differently from LibreOffice's
`.docx` filter, and the extractor of the day emitted one tag pair per `<text:span>`.

Two findings closed the investigation:

- **There is no rule.** All 183 same-formatting run boundaries in the document were
  labelled against the published file — 173 merged, 10 split — and the two
  `<style:text-properties>` sets at each boundary diffed attribute by attribute. Every
  attribute appearing at a split boundary also appears at many merged ones.
- **The intermediate format is irrelevant.** `odt → doc → odt` and a double round trip
  land on the *exact same 21 records*. Driving real Microsoft Word by AppleScript is far
  worse (299 records), because the manual workflow pastes clipboard content into a blank
  document — it never opens the ODT in Word, and Word's ODF import filter behaves
  nothing like its clipboard paste.

What did help was to **merge adjacent runs carrying the same `(bold, italic)` state**
into a single tag pair, rather than emitting one pair per span. Rendering per-span
raised the differing count from 21 to 66 — 45 spurious mid-word splits like
`<i>ever</i><i>ything you've learnt so far</i>` that Word's paste had already collapsed.
Merging is right in the overwhelming majority of cases.

That change is the hinge of the whole story, though it did not look like it at the time.
It was adopted to *imitate* Word's collapsed runs. Its real effect was to make the
extractor blind to run structure altogether — which is what Act 3 cashes in.

`REPORT.md` closed with three options: script the actual clipboard paste, regenerate the
reference, or hand-patch. None was taken immediately.

---

## Act 2 — the extractor was dropping content

*(`REPORT2.md`, against `reference_sample.json`, 808 records)*

Against a newer 808-record reference the pipeline scored **805 of 808**, and the three
misses were a different kind of problem entirely — not tag placement, but missing text.

### The defect

`extract_text_to_json` gated its whole state machine on one tag:

```python
if tag_name == 'p':
```

The top level of `office:text` is not all paragraphs:

```
p: 15024    h: 22    list: 11    sequence-decls: 1
```

The 22 `<text:h>` and 11 `<text:list>` elements were extracted —
`extract_text_from_element` ran on every one — and then **silently discarded**, because
the `if` had no `else`. The three differing records were exactly where a line of the
poem lives in a heading or a list:

| ref rec | text dropped | source |
|---|---|---|
| 761 | `LEAN DOTAGE`, `I've starved before.` | elements 14101, 14103 |
| 762 | the five `In Which The Poet Reveals…` lines | element 14120 |
| 788 | `a strong sense of the ridiculous is a necessity` | element 14653 |

These are not headings the author wrote. Any paragraph carrying outline numbering gets
wrapped in nested `<text:list><text:list-item>` and promoted to `<text:h>` — up to
eleven levels deep in this document:

```xml
<text:list text:continue-numbering="true" text:style-name="WWNum1">
  <text:list-item><text:list><text:list-item><text:list><text:list-item><text:list><text:list-item>
    <text:h text:style-name="P1450" text:outline-level="4">
      <text:span text:style-name="T2506">LEAN DOTAGE</text:span>
    </text:h>
  </text:list-item></text:list></text:list-item></text:list></text:list-item></text:list></text:list-item>
</text:list>
```

A second bug sat behind the first: a `<text:list>` passed to
`extract_text_from_element` renders **with no separator between its items** —
`'In Which The Poet RevealsIn Just Three Small Letters…'` — because the newline between
blocks came from the caller's `new_line += text_content + "\n"`, not from the renderer.

### The fix

`iter_block_lines(element, doc)` yields one rendered line per block: `<text:p>` and
`<text:h>` are one line each; `<text:list>` descends through `list` / `list-item` /
`list-header` and yields a line per contained block; anything else yields nothing. The
main loop iterates it instead of testing `tag_name == 'p'`.

**979 characters** of the book came back.

### And then the reference was the thing that was wrong

The fix left 804/808 in 8 hunks — every one now the *opposite* problem: the reference
omitted heading and list content that the source document carries, including
`THE / REVOLUTION / WILL / NOT / BE / POLITICISED`, the Charlie Sheen quote, and
`THE TWELVE STEP ROAD TO TRUE PESSIMISM`.

No attribute separates the blocks the reference kept from the ones it dropped:

- Element **14101** (`LEAN DOTAGE`) — style `P1450`, outline-level 4, depth-7 `WWNum1`
  list, interleaved with paragraphs — is **kept**.
- Element **14783** (`Because this is`) — style `P1570`, outline-level 4, depth-7
  `WWNum1` list, interleaved with paragraphs — is **dropped**.

Structurally identical, opposite outcomes; likewise headings 14653 and 14672, which
share `text:style-name="P1546"` and `text:outline-level="3"`.

One character settled it. Reference record 761 read `I’ve starved before.` with a
**curly** apostrophe — the only one in all 808 records — while the line directly beneath
it, `and i'll starve again.`, was straight. Both are curly in the source `test.odt`, and
`normalize_odt_newlines` strips every `’` from `content.xml` before extraction begins.
So the reference's *heading* text had bypassed a normalisation its *paragraph* text went
through: the same manual-workflow signature `REPORT.md` had documented for its 21
records. The reference was an artifact of the hand process, and no rule reading this
document could reproduce it.

**Resolution:** `reference_sample.json` was regenerated from the fixed pipeline on
2026-09-01 — Act 1's second option, finally taken. It is now the 813-record output, and
`sample.json` matches it byte for byte. Note that this renumbered `index` from 180
onward, which matters to anything linking to a record by index.

### Four latent bugs, fixed alongside

All verified output-neutral — `sample.json` byte-identical before and after.

- **Chunker state leaked across sections.** `new_line` was not cleared at a flush, so a
  block arriving before the next arming blank would append to text already emitted.
  Never fired on `test.odt`; a live duplication bug for any document that ends a section
  without trailing blanks. Buffer and counter now reset at the flush.
- **`new_line_counter` never reset on resuming content.** It is meant to end a section
  after three *consecutive* blanks, but accumulated across a whole section, so gaps
  inside one poem counted towards the threshold. Fired once, at element 14595, harmlessly.
  Now reset whenever content arrives.
- **Filenames were split on whitespace.** `input_odt.split()[0] + "_fixed.odt"`, twice,
  truncated any path containing a space. `fix_formatting` now returns the path it wrote
  and `__main__` uses that return value, so the name is derived in one place.
  `CONVERSION.sh` now quotes `"$1"`.
- **A failed run looked like a successful one.** `extract_text_to_json` wrapped its body
  in `except Exception as e: print(…)`, exiting 0 on a parse failure and leaving the
  previous `sample.json` in place. The handler is gone; missing argument and missing file
  exit 1, anything else raises.

---

## Act 3 — the round trip was doing nothing

*(`REPORT3.md`)*

With the reference regenerated, the LibreOffice round trip could finally be measured
against a baseline it had itself produced. It was removed, and:

**the output is byte-identical.** 813 records, 171,429 characters, md5
`604df023d108a22b7af5a2230acc8630`. Runtime falls from **31.7s to 1.7s**, and the
pipeline loses its dependency on a LibreOffice install.

Not merely identical after chunking: rendering *every* block in both intermediate
documents, including the ~14,000 blank paragraphs the chunker discards, gives two
identical lists of 15,077 lines.

### What it was actually doing

| | normalise only | round trip |
|---|---:|---:|
| `content.xml` | 3,872,479 B | 5,298,668 B (+37%) |
| `text:span` | 5,604 | **14,275** |
| `style:style` | 3,555 | 4,415 |
| `style:background-image` | 2,290 | 0 |
| `text:soft-page-break` | 302 | 0 |
| `text:list-header` | 1 | 0 |
| `text:p` / `text:h` / `line-break` / `s` / `tab` | — | **all identical** |

The block layer — everything the chunker keys on — survives untouched. The span layer is
rewritten, but only cosmetically:

| | text nodes bare in `p`/`h` | text nodes inside a `span` |
|---|---:|---:|
| normalise only | 4,374 | 1,273 |
| round trip | **0** | 5,496 |

The `.docx` filter cannot represent bare paragraph text, so on the way back it wraps
every run in a `<text:span>` — largely `Default_20_Paragraph_20_Font` — and mints an
automatic style for it. Same characters, same order, 2.5× the spans.

### Why the extractor is immune

Because of Act 1. `render_runs` merges adjacent runs with the same `(bold, italic)`
state, so how the text is divided into spans cannot reach the output. Removing that
merge — one tag pair per run, as the original extractor did — makes the two
intermediates disagree at once:

| renderer | lines differing between the two intermediates |
|---|---:|
| `render_runs` (merges neighbours) | **0** |
| one tag pair per run | 4 |

```
no round trip: 'so they can <i>“</i><i>run off stupid</i><i>”</i>'
round trip   : 'so they can <i>“run off stupid</i><i>”</i>'
```

Note the direction: the round trip *collapses* runs. That is exactly what the Word paste
in `MANUAL_WORKFLOW.txt` was buying, and what Act 1 set out to reproduce. `render_runs`
now does the same collapsing in software, which makes the document round trip redundant
rather than merely unnecessary.

### Its one real contribution, also gone

Against the old `p`-only extractor the round trip did change exactly one record —
638 of 808 — by appending a trailing `- its hard work being us`. That line is the
document's single `<text:list-header>`; in the raw ODT it sits inside a `<text:list>`,
so a `p`-only extractor never saw it, and the `.docx` filter flattening the wrapper to a
plain paragraph is what rescued it. `iter_block_lines` now reads it straight out of the
raw ODT. Once the extractor stopped dropping list content, the round trip's last
observable effect went with it.

---

## Where it stands

```bash
./CONVERSION.sh test.odt      # test.odt -> test.odt_fixed.odt -> sample.json, ~1.7s
```

Step 1 copies the input and normalises newlines and curly apostrophes in `content.xml`.
Step 2 walks `office:text` with `iter_block_lines`, resolves bold/italic up the style
parent chain, renders runs with same-format neighbours merged, and groups blocks into
sections on runs of three or more consecutive blank lines. Pure Python; `odfpy` is the
only dependency.

Output: 813 records, byte-identical to `reference_sample.json`.

**Open:**

- `JSON_FILE` is hardcoded, so output always lands in `tools/sample.json` regardless of
  where the input `.odt` lives.
- Act 3 is measured against one document. The mechanism argues the round trip is
  redundant generally, but a document leaning on the `.docx` filter for something
  structural — embedded objects, tables, tracked changes — has not been tested.
- The `index` renumbering from the regenerated reference is live; anything linking to a
  record by index needs re-checking.
