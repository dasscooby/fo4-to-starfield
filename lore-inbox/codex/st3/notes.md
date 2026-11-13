## Current priority-batch completion

102/102 checked/corrected; 43 primary, 59 as-reported. No IDs removed. Prior counts below are historical. StopA still requires the Commonwealth queue.

## Current eighth-pass checkpoint

93/102 checked/corrected; 34 primary, 59 as-reported. Prior counts below are historical. No IDs removed; StopA incomplete.

## Current seventh-pass checkpoint

90/102 checked/corrected; 32 primary, 58 as-reported. Prior counts below are historical. Current raw snapshot comparison still required before fold-in; StopA incomplete.

## Current sixth-pass checkpoint

71/102 checked/corrected; 20 primary, 51 as-reported. Prior counts below are historical. No rows removed. StopA incomplete; current raw snapshot comparison required before fold-in.

# st3 second read — first 12 unchecked entries

## Scope and provenance

Pinned input: `research/lore-inbox/store/build/lore.json`, built `2026-10-24T17:20:34Z`, SHA-256 content hash `49e9df39b23185f0b82e578eb401af7f2a9c63cdfbfe62cc1e86a269d788ac00`, 3,844 entries. Selected the first 12 entries with `added.batch == "st3"` and `check == "unchecked"` in original export order. The local `data/entries` mirror is incomplete and contains only `gwe`; this output is pinned review input, not a canonical rebuild. The current raw batch is absent. Folding requires comparison with the current lore-thread batch; this file does not claim current-store completeness.

## Reviewed IDs

ST-MT-0001, ST-MT-0002, ST-MT-0003, ST-MT-0004, ST-MT-0005, ST-MT-0006, ST-MT-0007, ST-MT-0008, ST-MT-0009, ST-NE-0001, ST-NV-0001, ST-NV-0002

## Corrections

- **ST-MT-0002**: The transcript says he was born in Montana and worked coal mines from fifteen; it does not say he grew up there or locate the mines. The wiki background's Montana-mines claim was not retained.
- **ST-MT-0003**: The dialogue identifies a guitar and a gun from his father but does not establish these were the only things his father left; removed the exhaustive 'only' claim.
- **ST-MT-0004**: The cited responses say he may not have felt he belonged back home and ask about finding a job; they do not say he is tired of wandering.
- **ST-MT-0006**: Narrowed the text to the dialogue record. The claim that the exchange jokes about the Courier fathering a child is an interpretation and was removed from this entry.
- **ST-MT-0008**: The inspected dialogue record supports the line and named bunker, but the inspected source does not establish the original claim that it was unused or never heard; narrowed to the record's content.
- **ST-MT-0009**: The inspected dialogue record attributes the statement to Patrocolus, but does not establish the original claim that the line was unused; narrowed to the inspected record.

## Unsupported / left unchecked

- **ST-MT-0007** — the cited Sawyer/Formspring statement is represented through a fan-wiki page; no original developer post was inspected. No primary-source verification.
- **ST-NE-0001** — cited TV dialogue is transcribed on a fan wiki; no episode primary artifact was inspected.
- **ST-NV-0001** — game setting/map summary is wiki-reported; no primary game map or in-game evidence inspected.
- **ST-NV-0002** — sign/slogan is wiki-reported; no primary game image or in-game evidence inspected.

These four rows retain their original fields and `check: unchecked`; labels were not upgraded. No other row was reviewed in this pass.

## Exact stopping point

Stopped after the first 12 originally unchecked `st3` entries, ending at **ST-NV-0002**. No later `st3` entries were reviewed. No current raw batch was available for fold comparison.

## Evidence

Targeted transcript sections only were inspected and cached privately at the private local source cache:

- `lonesome-drifter-dialogue-topics.json`, revision 4820252, Topics section; matched cited FNV dialogue topic IDs for ST-MT-0001–0006.
- `montana-bunker-background.json`, revision 5136003, Background passage; matched Fallout 3 dialogue record `CitElderLyonsMealBlessing1` for ST-MT-0008–0009. This passage does not substantiate the claim that the record was unused.

Ledger additions for these targeted reads are in adjacent `sources.jsonl` with partial coverage. No broad ledger page refresh was performed. New evidence excerpts stay in the private evidence folder; no long dialogue was reproduced in this inbox note.

Parent QA: cached dialogue and military note excerpts rechecked, no refetch. ST-MT-0008/0009 corrected from the older export’s tier3 to owner-required tier2/hold for cut content; playability unresolved. ST-MT-0003 note now acknowledges the approximate “just about the only thing” wording. Local store inbox is the working copy; original helper output retained outside it.

VALIDATION LIMITATION: the old PC tools/lore.py still maps cut to tier3 and rejects the two owner-required tier2 corrections. Unmodified validation reports2problems, exclusively this stale policy table. The source tool was not changed. A read-only in-memory check with cut/cancelled allowed in tier2 passes; this is not a claim the original validator passed. Retained other unchecked rows may still contain older-policy classifications and require the current lore-thread migration at fold-in.


## Second bounded pass - 2026-10-28

Authoritative input was the parent's reconciled `store/inbox/codex/st3/verified-1.jsonl`, not the older helper output or export. All 102 rows, their original order, all prior edits, every unassigned row and all coordinates are preserved. Input SHA-256: `1b319a1fe5094edfea548e4b628407900eeee44e90e68d87cf588b6a757da6d8`.

Attempted exactly 20 previously unattempted IDs: ST-NV-0003, ST-NV-0004, ST-NV-0005, ST-NV-0006, ST-NV-0007, ST-NV-0008, ST-NV-0009, ST-NV-0010, ST-NV-0011, ST-NV-0012, ST-NV-0013, ST-NV-0014, ST-NV-0015, ST-NV-0016, ST-NV-0017, ST-NV-0018, ST-NV-0019, ST-NV-0020, ST-NV-0021, ST-NV-0022. Result: 15 checked, 5 corrected; 18 remain as-reported and 2 are verified-source (ST-NV-0010 note transcript, ST-NV-0021 terminal transcript). Only ST-NV-0021 was newly promoted. Each entry has its specific evidence and limitation in check_note.

Corrections:
- ST-NV-0008: narrowed to the source-supported plant/fruit aid-item relationship.
- ST-NV-0013: changed unsupported plural billboards to the one described billboard.
- ST-NV-0016: bumper was hammered and sharpened, not described as cut.
- ST-NV-0018: identified the first citation as wiki geography prose rather than blueprint text.
- ST-NV-0019: removed the unsupported 2241 start date; the quoted earlier crime-family control is undated.

No assigned row is left unchecked after these bounded corrections. Primary proof remains limited: 18 checked/corrected entries retain as-reported, including ST-NV-0022, whose cited Nevada page explicitly makes the limited inscription claim. Its primary inscription transclusion returned empty content twice; this is not primary verification. Attributed dialogue excerpts were checked on the Nevada citation page without upgrading their labels. No coordinates were inferred or independently reverified.

Stopped at ST-NV-0022 (the 20th assigned entry). Next untouched entry: ST-NV-0023. Current raw lore-thread batch is still absent; comparison with it remains required before folding. Original export provenance above still applies; this is no claim of current-store completeness.

Private proof: the private local source cache contains the authoritative input snapshots, once-cached targeted sections with revisions, empty-transclusion receipts, review-audit.json, validation-original.txt and validation-audit.json. First-pass evidence was not changed. Nine partial source-ledger records were appended; no full source coverage is claimed and no new long quotations were placed in the inbox.

Validation ran from the store using `python tools/lore.py validate inbox/codex/st3/verified-1.jsonl`. The unmodified validator reports exactly two existing stale-policy errors for ST-MT-0008/0009 (cut at owner-required tier 2). All other validator fields pass; 102 unique IDs, row order, preserved unassigned rows and unchanged coordinates independently checked. No source tool or canon policy was changed.


## Third bounded pass - 2026-10-28

Used the parent's reconciled working batch, reported published head `1efb0d42`; input SHA-256 `653b14b78572b2b00103683f710288161d86a823220c02e6285ca9e59c5881f4`. Did not restore the older export/helper output. All 102 rows, IDs and order remain; 82 unassigned rows and every coordinate are unchanged. The October 24 export provenance above still applies. Current raw store/queue recovery is pending; no canonical rebuild or completeness claim.

Attempted exactly 20 next untouched rows: ST-NV-0023, ST-NV-0024, ST-NV-0025, ST-NV-0026, ST-NV-0027, ST-NV-0028, ST-NV-0029, ST-NV-0030, ST-NV-0031, ST-NV-0032, ST-NV-0033, ST-NV-0034, ST-NV-0035, ST-NV-0036, ST-NV-0037, ST-NV-0038, ST-NV-0039, ST-NH-0001, ST-NJ-0001, ST-NJ-0002. Result: **4 checked, 8 corrected, 8 left unchecked**. The 12 completed rows comprise 4 primary-transcript verifications (ST-NV-0023 through 0026) and 8 as-reported compound claims. No new verified-source promotion. ST-NV-0029 was downgraded to as-reported because the primary note does not independently establish its editorially supplied identity/location context.

Corrections: ST-NV-0023 now distinguishes treaty negotiations from signing; ST-NV-0026 removes the unsupported monument construction date; ST-NV-0027 narrows branch location to the inspected Silver Rush context; ST-NV-0029 distinguishes primary text from wiki context; ST-NV-0039 describes the fictional town's real-world basis; ST-NH-0001 omits uninspected logo-placement detail; ST-NJ-0001 uses trait and removes unsupported pre-war dating; ST-NJ-0002 removes the generic 2102 chronology. Each row's check_note records the actual evidence and limitations.

Unresolved: **ST-NV-0031, ST-NV-0032, ST-NV-0033, ST-NV-0034, ST-NV-0035, ST-NV-0036, ST-NV-0037, ST-NV-0038**. The 2011 Sawyer compilation metadata is revision 5712589 and exposes only a single large List section. A narrowly targeted Nellis-pods search returned a truncated answer without a complete dated post. The whole 684 KB page/List was not fetched. None of the eight original posts or full relevant transcriptions was inspected; their dates, full compound claims and the proposed 25x distance rule remain unverified. They stay unchecked with detailed notes; their inherited verified-source labels are earlier-reader metadata, not second-read endorsements.

Evidence: frozen second-pass Nevada cache reused for three exact bullets; newly inspected sections/revisions and exclusions are recorded in twelve appended partial source-ledger rows. The developer-page metadata/search-only probe is recorded in private proof, not claimed as a completed source read. No new long quotations are included here. First/second-pass caches were read-only. Private third-pass proof contains input snapshots, once-cached API responses, request manifest, preservation audit and validator output.

Stopped at **ST-NJ-0002**, the 20th assigned row; next untouched row **ST-NJ-0003**. Full-batch validation with the unmodified tool reports the same two stale cut/tier-2 mapping errors for ST-MT-0008 and ST-MT-0009. All other validator checks pass; IDs are unique and all unassigned row values/order/coordinates were independently compared. Owner cut/cancelled tier-2 hold policy and validator source were preserved. Fold-in still requires comparison with the recovered current lore-thread batch.


## Parent reconciliation of third pass

Parent checked the cached Kimball transcript and Unaccounted Blood note, state/Jean/NH&M/Hoboken sections and exact already-cached Nevada bullets. ST-NV-0031–0038 remain unchecked; no full developer-compilation reread. All 12 newly completed checks retain the recorded evidence limits; inherited real-world anchors are not new in-game positions or independently verified coordinates.

Cumulative completed checks: 40/102; new this pass: 12. All rows/IDs retained. Missing current raw snapshot still prevents fold-in.

## Parent reconciliation of fourth pass

Completed 18 additional checks; cumulative 58/102. All IDs/order retained, no rows removed. Newly completed: ST-NJ-0003, ST-NJ-0004, ST-NJ-0005, ST-NM-0001, ST-NM-0002, ST-NM-0003, ST-NM-0006, ST-NY-0001, ST-NY-0002, ST-NY-0003, ST-NY-0004, ST-NY-0005, ST-NY-0006, ST-NY-0007, ST-NY-0008, ST-NY-0009, ST-NY-0010, ST-NY-0011.

Method correction: the helper fetched whole-page wikitext, not only targeted sections, and did not perform the required ledger check first. Its original report and responses are preserved privately. Revisions were inherited or missing in its output; parent obtained metadata afterwards (latest revision timestamps precede capture), not a body refetch. They are retrospectively supported rather than response-pinned. This is not a new full-coverage reading.

Eight of those pages were already marked FULL: Albany, Albuquerque, Federal Reserve, New Jersey, New Mexico, New York, Niagara Sabotage and Rochester. That refetch violated the owner read-once rule; the earlier unsubmitted claim of no wholesale reread was wrong. Future helpers are cache-only, with any needed targeted fetch controlled by the parent. Corrected note-versus-wiki-link attribution, guessed dates, exact Federal Reserve coordinates, speaker inference and the cancelled Van Buren tier2/HOLD classification. ST-NM-0004/0005 remain unchecked.

Remaining unchecked IDs: ST-MT-0007, ST-NE-0001, ST-NV-0001, ST-NV-0002, ST-NV-0031, ST-NV-0032, ST-NV-0033, ST-NV-0034, ST-NV-0035, ST-NV-0036, ST-NV-0037, ST-NV-0038, ST-NM-0004, ST-NM-0005, ST-NY-0012, ST-NY-0013, ST-NY-0014, ST-NY-0015, ST-NY-0016, ST-NY-0017, ST-NY-0018, ST-NY-0019, ST-NC-0001, ST-NC-0002, ST-NC-0003, ST-NC-0004, ST-NC-0005, ST-NC-0006, ST-OH-0001, ST-OH-0002, ST-OH-0003, ST-OH-0004, ST-OH-0005, ST-OH-0006, ST-OH-0007, ST-OH-0008, ST-OH-0009, ST-OH-0010, ST-OH-0011, ST-OH-0012, ST-OH-0013, ST-OH-0014, ST-OK-0001, ST-OK-0002.

Current raw batch and exact Commonwealth queue still await recovery from Claude; no fold-in or Stop A completion claim. Existing real-world anchors are inherited context, not independently verified in-game positions. See per-entry notes and the validation report for limits.

## Fifth parent-only pass — ST-NY-0012 through ST-NY-0019

Eight further checks complete; cumulative66/102. Three newly inspected primary transcripts establish what Broadhurst heard, the Capitol Post report, and Grath's conditional accusation. The other five remain as-reported. Corrected hearsay versus observation, the July26 disbandment/July27 report distinction, already-ongoing Resource Wars, hypothetical saving versus a nuclear-payload claim, unsupported date bounds, and cut-setting tier2/HOLD policy. No new geography or coordinates invented.

Used existing city/state caches and parent-controlled exact sections only; no new whole-page fetch. Five fresh transcript/background sources returned their revisions; the full-ledger Adirondacks page was accessed only for the existing cited Background claim. Metadata-only section discovery and original request hashes are retained privately. Current old validator has three prior st3 cut/cancelled-policy errors plus ST-NY-0017; no validator code was changed.

Remaining unchecked IDs: ST-MT-0007, ST-NE-0001, ST-NV-0001, ST-NV-0002, ST-NV-0031, ST-NV-0032, ST-NV-0033, ST-NV-0034, ST-NV-0035, ST-NV-0036, ST-NV-0037, ST-NV-0038, ST-NM-0004, ST-NM-0005, ST-NC-0001, ST-NC-0002, ST-NC-0003, ST-NC-0004, ST-NC-0005, ST-NC-0006, ST-OH-0001, ST-OH-0002, ST-OH-0003, ST-OH-0004, ST-OH-0005, ST-OH-0006, ST-OH-0007, ST-OH-0008, ST-OH-0009, ST-OH-0010, ST-OH-0011, ST-OH-0012, ST-OH-0013, ST-OH-0014, ST-OK-0001, ST-OK-0002. Next untouched row ST-NC-0001; earlier skipped rows still need review. Current raw batches/64-page queue recovery remains pending; no fold-in or StopA completion.

## Sixth pass, parent reconciliation

Five North Carolina checks completed. Museum placard and Penelope terminal inspected as primary text. Charlotte expulsion and manufacturing-facility inferences narrowed. Poster/sign and company-artwork associations remain as-reported. ST-NC-0006 has only section metadata in cache: the cited Sawyer answer itself was not re-read, so it remains unchecked. Initial metadata cache was mistakenly treated as wikitext, raising KeyError; no content or source edit resulted.

Remaining unchecked IDs: ST-MT-0007, ST-NE-0001, ST-NV-0001, ST-NV-0002, ST-NV-0031, ST-NV-0032, ST-NV-0033, ST-NV-0034, ST-NV-0035, ST-NV-0036, ST-NV-0037, ST-NV-0038, ST-NM-0004, ST-NM-0005, ST-NC-0006, ST-OH-0001, ST-OH-0002, ST-OH-0003, ST-OH-0004, ST-OH-0005, ST-OH-0006, ST-OH-0007, ST-OH-0008, ST-OH-0009, ST-OH-0010, ST-OH-0011, ST-OH-0012, ST-OH-0013, ST-OH-0014, ST-OK-0001, ST-OK-0002.

## Seventh pass, parent reconciliation

Nineteen more checks completed: Ohio14, Oklahoma2, Nebraska1, cancelled Reservation design1 and Nevada sign1. Primary dialogue/plaque/note text supports12; seven remain as-reported. Removed the Cincinnati abduction-location inference, clarified advertised vacancies versus free accommodation, and used the design document's actual Los Alamos Nuclear Testing Facility name. Cancelled/noncanon HOLD rulings remain. Parent verified all4 helper excerpts and5 cache hashes. Nine other Nevada checks remain unresolved because complete relevant sources were not in inspected caches; no full Sawyer List was fetched. Reservation section2 included nested layouts/timeline, which were not comprehensively read or used for new lore. AllIDs/order retained, no rows removed.

Remaining unchecked IDs: ST-MT-0007, ST-NV-0001, ST-NV-0031, ST-NV-0032, ST-NV-0033, ST-NV-0034, ST-NV-0035, ST-NV-0036, ST-NV-0037, ST-NV-0038, ST-NM-0005, ST-NC-0006.

## Eighth pass, source-gap checks

Three checks completed. Dedicated dated developer tables supplied the full Cazador naming and carbine/Nellis question-and-answer pairs without fetching the2011List. The Nevada map description now acknowledges adjoining states and remains as-reported, with infobox/prose and native-map limits explicit. Other targeted discovery sections and search results did not establish the remaining dated posts; these stay unchecked. No Fandom result used as verification. Current raw snapshot/64-page queue still absent from observed mirror/default-branch code search; an unconfirmed lore-inbox remote ref returned404, which is not proof that Claude cannot recover it. No repeated recovery request or assumption of lost work.

Remaining unchecked IDs: ST-MT-0007, ST-NV-0031, ST-NV-0032, ST-NV-0033, ST-NV-0034, ST-NV-0036, ST-NV-0037, ST-NV-0038, ST-NC-0006.

## Final priority-entry checks, 2026-10-28

All 102 states entries now second-read. The actual canonical ledger marks the 2011 Sawyer compilation PARTIAL, not FULL; earlier handoffs were mistaken. A single pinned retrieval supported eight complete dated Q&As for the final nine entries, independently checked from cache. Four corrections narrow the Montana ruling, remove an unsupported Desert Rangers synonym, prevent treating 25x as a calibrated map transform, and scope tabletop advice to 2011. Other cited claims are confirmed. No whole-compilation coverage claim; source remains PARTIAL. Inherited coordinates and game-year context were not newly surveyed. Canonical data remains untouched; raw-snapshot reconciliation is still required before fold-in.
