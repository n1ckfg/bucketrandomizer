# Removing the LibreOffice headless round trip

Step 1 of `CONVERSION.py` converted the input `.odt` to `.docx` and back through
`soffice --headless` before extracting. This documents what that round trip was
actually doing, and the measurements behind removing it.

Follows on from `REPORT2.md`. Nick Fox-Gieg / 2026-09-01

## Result

**The output is byte-identical without it.**

```
$ ./CONVERSION.sh test.odt && diff -q sample.json reference_sample.json
Extracted 813 objects to sample.json.
                          # no output: identical
```

`sample.json` — 813 records, 171,429 characters, md5 `604df023d108a22b7af5a2230acc8630` —
matches `reference_sample.json`, which was generated *with* the round trip, exactly.

Runtime drops from **31.7s to 1.7s**, and the pipeline loses its dependency on a
LibreOffice install (`requirements.txt` was already just `odfpy`).

The stronger check: rendering **every** block in both intermediate documents, including
the ~14,000 blank paragraphs the chunker discards, gives two identical lists of 15,077
lines. The round trip changes nothing the extractor can see, not merely nothing that
survives chunking.

## What the round trip actually did to the document

Comparing the two intermediates — `test.odt` normalised only, versus `test.odt` round
tripped and then normalised:

| | normalise only | round trip | delta |
|---|---:|---:|---:|
| `content.xml` | 3,872,479 B | 5,298,668 B | +37% |
| `text:span` | 5,604 | 14,275 | **+8,671** |
| `style:style` | 3,555 | 4,415 | +860 |
| `style:background-image` | 2,290 | 0 | −2,290 |
| `style:graphic-properties` | 0 | 1,210 | +1,210 |
| `text:soft-page-break` | 302 | 0 | −302 |
| `text:list` | 34 | 33 | −1 |
| `text:list-header` | 1 | 0 | −1 |
| `text:p` | 15,024 | 15,024 | 0 |
| `text:h` | 53 | 53 | 0 |
| `text:line-break` | 128 | 128 | 0 |
| `text:s` / `text:tab` | 137 / 2 | 137 / 2 | 0 |

Two things stand out.

**The block layer is untouched.** Paragraph, heading, line-break, space and tab counts
are identical. Everything the chunker keys on survives the round trip unchanged — which
is why the section boundaries never moved.

**The span layer is rewritten, but only cosmetically.** The +8,671 spans are not new
text runs; they are wrappers. In the raw document most text sits bare inside its
paragraph:

| | text nodes bare in `p`/`h` | text nodes inside a `span` |
|---|---:|---:|
| normalise only | 4,374 | 1,273 |
| round trip | **0** | 5,496 |

The `.docx` filter cannot represent bare paragraph text, so on the way back it wraps
every run in a `<text:span>` (largely `Default_20_Paragraph_20_Font`) and mints an
automatic style for it. The characters, and their order, do not change.

## Why the extractor is immune

`render_runs` merges adjacent runs carrying the same `(bold, italic)` state into one tag
pair, so the number of spans the text is divided into cannot reach the output. Removing
that merge — emitting one tag pair per run, as the original extractor did — makes the
two intermediates disagree immediately:

| renderer | lines differing between the two intermediates |
|---|---:|
| `render_runs` (merges neighbours) | **0** |
| one tag pair per run | 4 |

```
no-LO  : 'so they can <i>“</i><i>run off stupid</i><i>”</i>'
with-LO: 'so they can <i>“run off stupid</i><i>”</i>'
```

Note the direction: the round trip *collapses* runs. That is what `MANUAL_WORKFLOW.txt`
steps 2.2-2.6 were buying, and it is what `REPORT.md` set out to reproduce. `render_runs`
now does the same collapsing in software, which makes the document round trip redundant
rather than merely unnecessary.

## Its one real contribution, and why that is gone too

Against the **old** `p`-only extractor the round trip did change exactly one record —
638 of 808:

```
 …
 which, folks, is tricky enough
 - its hard work being us -
 …
 and how difficult does this make our lives?
+- its hard work being us
```

That trailing line is the document's single `<text:list-header>`. In the raw ODT it is
wrapped in a `<text:list>`, so the old extractor — which only looked at `text:p` — never
saw it. The `.docx` filter flattens the wrapper to a plain paragraph, which is what
rescued the line.

`iter_block_lines` (see `REPORT2.md`) descends into `list` / `list-item` / `list-header`
directly, so the line is now read out of the raw ODT. Once the extractor stopped
dropping list content, the round trip's last observable effect went with it.

## Caveat

Measured against one document, `test.odt`. The claim is that the round trip is redundant
*given* run merging and list descent, and the mechanism above says why that should hold
generally — but a document that leans on the `.docx` filter for something structural
(embedded objects, tables, tracked changes) has not been tested.
