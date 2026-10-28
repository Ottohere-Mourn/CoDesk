# Data-to-Deck Lite v2.1 (CDD-LITE-002)

## User request and workflow

The manager needs one West Q3 operating-profit conclusion in a one-slide brief. A verifies the signed Q3-minus-Q2 change in Calc and saves an evidence-bearing workbook. B may inspect the slide while A works, then uses A's saved result and message to finish the brief in Impress. Both run concurrently. Shared places both agents on one desktop without input arbitration; Isolated gives each a separate desktop and the same saved-file bridge and collaboration tools.

## Public fixture and outputs

The public workbook has one visible `West_Finance` sheet with two quarter rows, a stated operating-profit definition, and blank B6/D6 output cells. The one-slide draft has a title and one unfinished conclusion text box. Both editable output copies are already open. A writes `outputs/agent_A/verified_analysis.ods`; B writes `outputs/agent_B/final_management_brief.odp`. Raw inputs are read-only. Peer output copies are read-only in Isolated. Gold and Oracle are evaluator-side only.

## Success and experimental boundary

The artifact Oracle derives the expected signed change from the source cells, checks A's numerical value, input-cell evidence and source preservation, and checks B's direction, amount/unit, citation, title and consistency with A. It accepts equivalent wording. A separate trace audit checks that B's final save followed a real A saved revision and message. A citation string alone is not proof of handoff.

The intended scripted path is 13 GUI calls total: A selects B6, enters a formula, selects D6, enters the input range and saves (7 calls); B finds and replaces the one conclusion text, then saves (6 calls). Find/Replace makes the scripted control robust to LibreOffice notification banners that shift the slide canvas; model Actors may edit the visible box directly. Publish, messaging and revision verification are collaboration-tool events, not GUI calls. The task has no forced simultaneous click and no Shared-specific obstacle. It removes v1's second KPI, multiple sheets, four text replacements and digest footer. The role budget of 25 desktop calls is a safety allowance, not a target or a hard task-step claim.

## v2.1 scorer correction

This version has the same public task, base role instructions, deterministic
fixture bytes, Gold and GUI actions as Lite v2.0.0. Its Adapter uses the
version-specific Guest root `/tmp/codesk-data-to-deck-lite-v2-1`; that path is
appended equally to both topology prompts. Its independent Oracle additionally accepts
`11 USD thousands` as an equivalent financial-report unit expression for
`11 thousand USD` or `$11k`. The numeric amount, direction, saved-analysis
consistency, source citation and other checks are unchanged. Old v2.0.0
run results and frozen scores remain untouched. Re-scoring them under v2.1 is
retrospective evidence, not a new model episode.
