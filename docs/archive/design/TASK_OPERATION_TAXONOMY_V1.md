# CoDesk Task-Operation Taxonomy V1

Status: offline design/implementation taxonomy. A listed class is not evidence of successful Guest execution. V1 uses Writer, Calc, Browser, and Desktop Terminal only.

## Operation classes

| Software | Distinct GUI operation graphs represented | Second-wave additions |
|---|---|---|
| Writer | Whole-document rewrite; exact paragraph replacement; find/replace; anchored comment; character formatting; text-range replacement; hyperlink insertion; structured table paste; section navigation/edit; text/style undo | find/replace, character formatting, structured table paste, section navigation, selection replacement, cross-actor undo |
| Calc | Scalar cell entry; formula entry; rectangular range fill; source/destination range copy; hyperlink formula insertion; worksheet switching; range selection/fill; formula/value undo | formula entry, hyperlink formula, sheet context, rectangular fill/selection, peer-history undo |
| Browser | Form transaction/submit; tab/page switching; same-page route change; filter/result-set change; row selection/bulk update; hyperlink/text copy; rich editor insertion/undo | multi-field transaction, filter/result context, multi-row selection, text transfer, rich editor |
| Desktop Terminal | Command entry/edit/execute; output inspection; selected-output copy | command edit/execute; output-to-browser transfer |

Text, seed, entity label, window coordinates, and repeat number are instance/run parameters, never operation classes.

## Current 15-workflow coverage

| ID | Family | Actor A operation | Actor B operation | Oracle surface |
|---|---|---|---|---|
| F-01 | Focus | Writer whole-document rewrite | Calc scalar cell entry | ODF document/cell |
| F-04 | Focus | Calc rectangular fill | Writer paragraph edit | ODF range/paragraph |
| F-02 | Focus | Writer anchored comment | Browser form submit | ODF comment + private form state |
| F-N1 | Focus | Writer document A paragraph edit | Writer document B paragraph edit | per-document ODF |
| C-01 | Clipboard | Writer text copy/paste | Calc text copy/paste | exact ODF targets + clipboard events |
| C-03 | Clipboard | Calc range copy/paste | Writer paragraph copy/paste | ODF range/table/text |
| C-02 | Clipboard | Writer hyperlink object | Browser URL submit | ODF href + Browser state |
| C-N1 | Clipboard | Browser rich HTML table paste | Browser URL submit | HTML structure/MIME + ODF |
| A-01 | App Context | Browser tab A form | Browser tab B form | tab/context event log + submissions |
| A-N1 | App Context | SPA route A edit | SPA route B edit | route/revision oracle |
| A-02 | Selection | Browser record selection/edit | Browser independent record edit | selected record state |
| S-01 | Selection | Calc active-cell entry | Calc second cell entry | ODF cell values |
| S-N1 | Selection | Writer range formatting A | Writer range formatting B | ODF range style |
| U-01 | Undo/Redo | Calc edit then Undo | Calc independent cell edit | ODF + action history |
| U-N1 | Undo/Redo | Writer paragraph edit then Undo | Writer independent paragraph edit | ODF + action history |

## Operation coverage audit

- Dense: scalar/cell editing, text transfer, form submission, and paragraph edits recur in the first wave.
- Meaningful gaps selected for the second wave: formula entry, range-level fill, find/replace, structured range-to-table transfer, same-sheet context changes, filtered result-set context, multi-row active selection, contenteditable history, terminal command/output operations, and Writer section navigation.
- Rejected as duplicate axes: another plain text paste; another tab switch; another single-cell edit; more paragraph-only replace cases.
- Reserve-only classes: image clipboard payloads, chart-object selection, file upload/download workflow, authentication/session context. These need stronger stable GUI oracles before selection.

Family distribution in the frozen final suite: Focus 7; Clipboard 7; Application Context 5; Selection/Active Object 6; Undo/Redo History 5.
