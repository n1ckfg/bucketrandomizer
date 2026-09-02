# CONVERSION.py — the heading/list elements the extractor was dropping

`CONVERSION.py` reproduced **805 of 808** records in `reference_sample.json`. This
documents the defect behind the 3 that differed, the fix, and the 8 places where the
output is now *ahead* of the reference rather than behind it.

Follows on from `REPORT.md`. Nick Fox-Gieg / 2026-09-01

## Reproducing

```bash
./CONVERSION.sh test.odt          # test.odt -> test.odt_fixed.odt -> sample.json

python3 - <<'EOF'
import json, difflib
a = [r['body'] for r in json.load(open('sample.json'))]
b = [r['body'] for r in json.load(open('reference_sample.json'))]
sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
same = sum(i2 - i1 for t, i1, i2, _, _ in sm.get_opcodes() if t == 'equal')
print(f"identical {same}/{len(b)}, records {len(a)} vs {len(b)}")
for t, i1, i2, j1, j2 in sm.get_opcodes():
    if t != 'equal':
        print(t, f"ours[{i1}:{i2}]", f"ref[{j1}:{j2}]")
EOF
```

## The defect

`extract_text_to_json` gated the whole chunker on a single tag:

```python
if tag_name == 'p':
```

`doc.text.childNodes` for `test.odt_fixed.odt` is not all paragraphs:

```
p: 15024    h: 22    list: 11    sequence-decls: 1
```

The 22 `<text:h>` and 11 `<text:list>` elements were extracted — `extract_text_from_element`
ran on every one of them — and then **silently discarded**, because the `if` had no
`else`. The three differing records were exactly the places where a line of the poem
lives in a heading or inside a numbered-list wrapper:

| ref rec | text we dropped | source element |
|---|---|---|
| 761 | `LEAN DOTAGE`, `I’ve starved before.` | 14101, 14103 — `<text:h outline-level="4">` inside nested `<text:list>` |
| 762 | the five `In Which The Poet Reveals…` lines | 14120 — one `<text:list>`, five items |
| 788 | `a strong sense of the ridiculous is a necessity` | 14653 — top-level `<text:h>` |

These are not real headings in the authored document. LibreOffice's `.docx` filter
wraps any paragraph that carries outline numbering in `<text:list><text:list-item>…`
and promotes it to `<text:h>`; the original `test.odt` has the same shape, up to
eleven levels of nesting deep:

```xml
<text:list text:continue-numbering="true" text:style-name="WWNum1">
  <text:list-item><text:list><text:list-item><text:list><text:list-item><text:list><text:list-item>
    <text:h text:style-name="P1450" text:outline-level="4">
      <text:span text:style-name="T2506">LEAN DOTAGE</text:span>
    </text:h>
  </text:list-item></text:list></text:list-item></text:list></text:list-item></text:list></text:list-item>
</text:list>
```

### The second-order bug behind it

Even once a `<text:list>` reaches `extract_text_from_element`, it renders **with no
separator between its items**:

```
'In Which The Poet RevealsIn Just Three Small LettersThe Greatest Source of…'
```

The newline between blocks never came from the renderer — it came from the caller's
`new_line += text_content + "\n"`. A list is a container of blocks, so it needs one
line per contained block, not one line for the whole element.

## The fix

`iter_block_lines(element, doc)` yields one rendered line per block-level element:
`<text:p>` and `<text:h>` are one line each, `<text:list>` descends through
`list` / `list-item` / `list-header` wrappers and yields a line per block inside, and
anything else (`<text:sequence-decls>`, …) yields nothing. The main loop iterates it
instead of testing `tag_name == 'p'`.

Result: **979 characters** of the book come back, and records 761, 762 and 788 are
correct — 762 and 788 exactly, 761 down to a single character (below).

## What still differs, and why it is not fixable here

Aligned diff is now 804/808, in 8 hunks. Every one is the *opposite* problem:
**`reference_sample.json` omits heading/list content that the source document
carries.**

| ours | element(s) | text the reference lacks |
|---|---|---|
| new record 180 | 3005 | `THE / REVOLUTION / WILL / NOT / BE / POLITICISED` |
| record 285 | 4862 | `for a flow, multiply divided beyond the bounds of one-ness` |
| new record 320 | 5569 | `In Which The Poet Boldly Attempts To Characterise…` |
| new record 444 | 7858 | `Charlie Sheen` / `'You can't process me with a normal brain'` |
| new record 485 | 8664 | `Will the hackers of tomorrow be imprisoned in Guantanamo Bays…` |
| record 541 | 9699 | `this final philosophy calls all / else in doubt` |
| new record 793 | 14666–14672 | `I slowed down and the past caught up with me ……` … `…… the future is a steamroller about to run over us` |
| record 799 | 14783, 14785 | `Because this is` / `THE TWELVE STEP ROAD TO TRUE PESSIMISM` |

**No attribute separates the blocks the reference keeps from the ones it drops.**
Every list and heading in the document was labelled against `reference_sample.json`
and diffed on list style, nesting depth, paragraph style and outline level:

- Element **14101** (`LEAN DOTAGE`) is **kept**: style `P1450`, outline-level 4,
  depth-7 `WWNum1` list, interleaved with ordinary paragraphs.
- Element **14783** (`Because this is`) is **dropped**: style `P1570`, outline-level 4,
  depth-7 `WWNum1` list, interleaved with ordinary paragraphs.

Structurally identical, opposite outcomes. The same holds for the bare headings:
14653 is kept and 14672 is dropped, and both are `text:style-name="P1546"` with
`text:outline-level="3"`. Position does not separate them either — 14101/14103 sit
between paragraphs and are kept, 14783/14785 sit between paragraphs and are dropped;
3005 stands alone and is dropped, but so is 4862, which does not.

### One character of independent evidence

Record 761 in the reference reads `I’ve starved before.` with a **curly** apostrophe —
the only one in all 808 records — while the line directly beneath it, `and i'll starve
again.`, is straight:

```
ref[761]:  "LEAN DOTAGE\n...\nI’ve starved before.\nand i'll starve again.\n…"
```

Both are curly in the source `test.odt`, and `normalize_odt_newlines` strips every `’`
from `content.xml` before extraction begins (the fixed file contains zero). So the
reference's *heading* text bypassed a normalisation its *paragraph* text went through.
That is the signature `REPORT.md` documented for its 21 records: `reference_sample.json`
is an artifact of the manual Word copy-and-paste workflow in `MANUAL_WORKFLOW.txt`, and
those 8 blocks are not reachable by any rule reading this document.

## Recommendation

The extractor is now content-complete and the reference is not. Either:

1. **Regenerate `reference_sample.json`** from the fixed pipeline. Nothing is lost and
   979 characters of the book come back. — recommended
2. Revert `iter_block_lines` and accept 805/808 with those lines missing from the site.

Note that the fix renumbers `index` from 180 onward (808 → 813 records), which matters
if anything links to a record by index.

## Latent bugs fixed alongside

All four were verified output-neutral: `sample.json` is byte-identical before and
after (`604df023d108a22b7af5a2230acc8630`).

**Chunker state leaked across sections.** `new_line` was not cleared when a section was
flushed, so a block arriving before the next arming blank would have appended to the
text already emitted. It never fired on `test.odt` (0 occurrences) but it is a live
duplication bug for any document that ends a section without trailing blanks.
`new_line` and `new_line_counter` are now reset at the flush.

**`new_line_counter` never reset on resuming content.** The counter is meant to end a
section after three *consecutive* blank paragraphs, but it accumulated across a whole
section, so blank-line gaps inside one poem counted towards the threshold. It fired
once, at element 14595, flushing after a run of 2 blanks instead of 3 — harmless there
because only blanks intervened, so the record content was the same either way. The
counter is now reset whenever content arrives.

**Filenames were split on whitespace.** `input_odt.split()[0] + "_fixed.odt"` — and the
same expression again in `__main__` — truncated any path containing a space at the
first space. `fix_formatting` now returns the path it wrote and `__main__` uses that
return value instead of re-deriving it, so the name is computed in exactly one place.
`CONVERSION.sh` also passed `$1` unquoted; it is now `"$1"`. The output name is
unchanged (`test.odt` → `test.odt_fixed.odt`).

**A failed run looked like a successful one.** `extract_text_to_json` wrapped its whole
body in `except Exception as e: print(f"An error occurred: {e}")`, so a parse failure
printed one line and exited 0 — `CONVERSION.sh` could not tell a broken run from a good
one, and `sample.json` would silently keep its previous contents. The handler is gone;
a missing input file and a missing argument both exit 1, and anything else surfaces a
traceback.

Still open, not touched: `JSON_FILE` is hardcoded, so the output always lands in
`tools/sample.json` no matter where the input `.odt` lives.
