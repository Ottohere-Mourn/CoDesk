# Task Domain and Operation Matrix V1

This matrix covers every frozen workflow across five families and four software domains. An additional software shown after a semicolon is a fixture/source dependency, not an extra actor role. Operation classes and first-wave coverage rationale are expanded in `TASK_OPERATION_TAXONOMY_V1.md`.

| ID | Family | Actor A application / operation | Actor B application / operation | Shared hidden state | Operation graph | Oracle type |
|---|---|---|---|---|---|---|
| F-01 | Focus | Writer / whole-document rewrite | Calc / scalar cell entry | foreground window + keyboard target | rewrite document → set cell | ODF paragraphs + cell |
| F-04 | Focus | Calc / rectangular fill | Writer / paragraph edit | foreground window + keyboard target | select/fill rectangle → edit paragraph | ODF range + paragraph |
| F-02 | Focus | Writer / anchored comment | Browser / form transaction | foreground window + input target | select anchor/comment → fill and submit form | ODF annotation + private form state |
| F-N1 | Focus | Writer / document-A paragraph edit | Writer / document-B paragraph edit | foreground document/window | edit first doc → activate/edit second doc | per-document ODF content |
| F-05 | Focus | Writer / exact Find-Replace | Calc / formula entry | foreground window + keyboard target | replace phrase → enter formula | ODF exact text + formula |
| F-06 | Focus | Browser / two-field submit | Terminal / command edit+execute | foreground window + keyboard target | fill transaction → edit/run command | private form record + exact output file |
| F-07 | Focus | Writer / character formatting | Calc / rectangular fill | foreground window + keyboard target | select/style phrase → fill range | ODF style + cell matrix/guards |
| C-01 | Clipboard | Writer / paragraph copy-paste | Calc / text copy-paste | X11 selection/payload generation | copy A → copy B → resume/paste A | ODF target + clipboard event log |
| C-03 | Clipboard | Calc / range copy-paste | Writer / paragraph copy-paste | X11 selection/payload generation | copy matrix → copy text → paste destinations | ODF range + paragraph/table |
| C-02 | Clipboard | Writer / hyperlink object | Browser / URL submit | clipboard object payload | copy link object → independent URL transaction | exact ODF label/href + Browser URL |
| C-N1 | Clipboard | Writer / rich HTML table paste | Browser / URL submit | clipboard MIME payload | rich table copy/paste → URL submit | ODF table dimensions/cells + MIME/event evidence |
| C-04 | Clipboard | Calc / hyperlink formula from Browser URL | Calc / rectangular range transfer | X11 clipboard payload/generation | copy URL → insert hyperlink formula; copy/paste range | formula/href + exact range/guards |
| C-05 | Clipboard | Writer / destination table (Calc source) | Writer / paragraph copy-paste | X11 structured payload | copy Calc rectangle → paste table; copy paragraph → paste target | ODF table shape/cells + paragraph |
| C-06 | Clipboard | Browser / search submit (Terminal source) | Browser / text copy-paste | X11 clipboard payload/generation | select terminal output → paste/search; copy Browser token → paste destination | Browser fields + selected output |
| A-01 | App Context | Browser / tab-A form | Browser / tab-B form | active tab/page context | submit two tab-specific forms in one top-level window | tab/context event + per-form value |
| A-N1 | App Context | Browser / SPA route-A edit | Browser / SPA route-B edit | route + record revision | change route → edit route-keyed record | route/revision + record values |
| A-03 | App Context | Calc / Sheet A cell edit | Calc / Sheet B cell edit | active worksheet | switch sheet → edit sheet-scoped cell | named-sheet ODF cells |
| A-04 | App Context | Browser / filter-A result edit | Browser / filter-B result edit | active filter/result set | change filter → edit exact result | filter/context events + record values |
| A-05 | App Context | Writer / section-A edit | Writer / section-B edit | active section/Navigator target | navigate section → edit heading-scoped paragraph | ODF heading/paragraph structure |
| A-02 | Selection | Browser / select and edit record A | Browser / select and edit record B | active record selection | select row → edit record fields | private record table state |
| S-01 | Selection | Calc / active-cell entry A | Calc / active-cell entry B | selected cell/caret | select target cell → enter value | ODF exact cells |
| S-N1 | Selection | Writer / range-A formatting | Writer / range-B formatting | text range/caret | select phrase → apply style | ODF span/style and untouched ranges |
| S-02 | Selection | Calc / select/fill rectangle A | Calc / select/fill rectangle B | selected cell range | select rectangle → fill pattern | ODF cell matrix + guard cells |
| S-03 | Selection | Writer / select/replace phrase A | Writer / select/replace phrase B | caret/text selection | find/select phrase → replace exact text | ODF target text + untouched paragraphs |
| S-04 | Selection | Browser / select rows+bulk status A | Browser / select rows+bulk status B | global selected-row set | select row set → bulk apply status | row statuses + selection/bulk event log |
| U-01 | Undo/Redo | Calc / temporary cell edit+Undo | Calc / independent cell edit | document undo stack | edit A → edit B → Undo A | ODF cell state + action chronology |
| U-N1 | Undo/Redo | Writer / temporary paragraph edit+Undo | Writer / independent paragraph edit | document undo stack | edit A → edit B → Undo/recover | ODF text + action chronology |
| U-02 | Undo/Redo | Writer / character style+Undo | Writer / paragraph edit+recovery | Writer document undo stack | style A → edit B → Undo → restore B if reverted | ODF style/text + Ctrl-Z/action order |
| U-03 | Undo/Redo | Calc / formula edit+Undo | Calc / value edit+recovery | Calc document history | formula A → value B → Undo → restore peer value | ODF formula/value + Ctrl-Z/action order |
| U-04 | Undo/Redo | Browser / rich-editor insertion+Undo/recovery | Browser / independent rich-editor insertion | contenteditable history | insert A → insert B → Undo → restore both phrases | exact editor state + commit/history events |

The rows describe intended operation/evaluator bindings, not real Guest validation. See `SECOND_WAVE_IMPLEMENTATION_REPORT.md` for evidence level and per-workflow CODE_READY status.
