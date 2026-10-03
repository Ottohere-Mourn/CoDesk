# Task Domain Matrix V1

This matrix records the workflow-by-software coverage. A software may be a fixture dependency even when it is not the actor's primary target application.

| ID | Family | Actor A domain / operation | Actor B domain / operation | Additional required app(s) |
|---|---|---|---|---|
| F-01 | Focus | Writer / whole-document rewrite | Calc / scalar cell entry | — |
| F-04 | Focus | Calc / rectangular fill | Writer / paragraph edit | — |
| F-02 | Focus | Writer / anchored comment | Browser / form transaction | — |
| F-N1 | Focus | Writer / document-A paragraph edit | Writer / document-B paragraph edit | — |
| F-05 | Focus | Writer / Find-Replace | Calc / formula entry | — |
| F-06 | Focus | Browser / multi-field submit | Terminal / command edit+execute | — |
| F-07 | Focus | Writer / character styling | Calc / range fill | — |
| C-01 | Clipboard | Writer / paragraph text transfer | Calc / scalar text transfer | — |
| C-03 | Clipboard | Calc / range copy-paste | Writer / paragraph copy-paste | — |
| C-02 | Clipboard | Writer / hyperlink object | Browser / URL submit | — |
| C-N1 | Clipboard | Writer / rich table paste | Browser / URL submit | — |
| C-04 | Clipboard | Calc / hyperlink formula | Calc / rectangular range transfer | Browser URL source |
| C-05 | Clipboard | Writer / destination table | Writer / paragraph copy-paste | Calc range source |
| C-06 | Clipboard | Browser / search submit | Browser / text copy-paste | Terminal output source |
| A-01 | App Context | Browser / tab-A form | Browser / tab-B form | — |
| A-N1 | App Context | Browser / SPA route A | Browser / SPA route B | — |
| A-03 | App Context | Calc / Sheet A cell | Calc / Sheet B cell | — |
| A-04 | App Context | Browser / filter A result edit | Browser / filter B result edit | — |
| A-05 | App Context | Writer / section A edit | Writer / section B edit | — |
| A-02 | Selection | Browser / record A selection/edit | Browser / record B selection/edit | — |
| S-01 | Selection | Calc / active-cell entry | Calc / second cell entry | — |
| S-N1 | Selection | Writer / range-A formatting | Writer / range-B formatting | — |
| S-02 | Selection | Calc / selected rectangle fill A | Calc / selected rectangle fill B | — |
| S-03 | Selection | Writer / select+replace phrase A | Writer / select+replace phrase B | — |
| S-04 | Selection | Browser / select rows+bulk update A | Browser / select rows+bulk update B | — |
| U-01 | Undo | Calc / temporary value edit+undo | Calc / independent cell edit | — |
| U-N1 | Undo | Writer / paragraph edit+undo | Writer / independent paragraph edit | — |
| U-02 | Undo | Writer / character style+undo | Writer / paragraph edit+recovery | — |
| U-03 | Undo | Calc / formula edit+undo | Calc / value edit+recovery | — |
| U-04 | Undo | Browser / rich editor edit+undo/recovery | Browser / rich editor edit | — |

The five software-operation taxonomies and the first-wave audit are in `TASK_OPERATION_TAXONOMY_V1.md`.
