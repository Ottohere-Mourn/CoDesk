# Second-Wave Workflow Plan

The first 15 workflow definitions remain unchanged in purpose and are treated as the prototype snapshot. The selected second wave adds 15 operation graphs; all are offline CODE_READY only until real Guest gates run.

## Selected candidates

| ID / family | A application + independent goal | B application + independent goal | Shared state / stale assumption | Expected interference / recovery | Oracle / difficulty | Nearest existing workflow; distinction |
|---|---|---|---|---|---|---|
| F-05 Focus | Writer exact Find/Replace once | Calc formula entry | foreground window/input target | formula keystrokes may land in Writer; reobserve/refocus | ODF phrase + formula; medium | F-01; replace+formula graph differs from rewrite+scalar |
| F-06 Focus | Browser two-field transaction | Terminal command edit/run to exact file | foreground target | input directed to wrong application; return to task and verify | Browser private state + exact output; high | F-02; command execution is a separate operation |
| F-07 Focus | Writer exact phrase formatting | Calc rectangular fill | foreground target | range/value action routed to peer app; reselect target | ODF style + exact range/guards; medium | F-04; style+fill differs from range fill+paragraph edit |
| C-04 Clipboard | Copy Browser URL and create Calc hyperlink | Copy distinct Calc range to destination | X11 clipboard payload/generation | URL/range overwrite; recopy correct payload | formula/href + range ODF; medium | C-02/C-03; URL→formula plus grid transfer |
| C-05 Clipboard | Copy Calc range into Writer table | Copy Writer paragraph into separate target | X11 structured payload | rich table replaced by text or paragraph payload; recopy | exact table shape/cells + paragraph; medium | C-03/C-N1; Calc source and Writer table destination |
| C-06 Clipboard | Select Terminal output, paste into Browser search | Copy Browser token to separate destination | X11 clipboard payload | output/token overwrite; reselect and recopy | exact browser fields and output; high | C-01; terminal-selected output/search graph |
| A-03 App Context | Edit named Sheet A cell | Edit named Sheet B cell | active Calc worksheet | stale sheet assumption after sheet switch; reselect sheet/cell | sheet-scoped ODF cells; medium | A-01; internal spreadsheet sheet context, not browser tab |
| A-04 App Context | Filter and update record set A | Filter and update record set B | active query/filter/result set | stale filter maps action to other result set; restore filter and verify | route/filter revision + exact records; medium | A-N1; query result context differs from route navigation |
| A-05 App Context | Navigate to Writer section A and edit | Navigate to Writer section B and edit | active document section/Navigator context | cursor remains in prior section; navigate and verify | ODF heading/paragraph state; medium | A-01; same Writer document section context |
| S-02 Selection | Select/fill assigned Calc rectangle | Select/fill disjoint rectangle | active selected range | second selection replaces first; reselect range before fill | exact cell matrix + guards; low | S-01; range-level fill rather than scalar entry |
| S-03 Selection | Select/replace exact phrase A | Select/replace exact phrase B | caret/text selection | caret/selection changes to peer phrase; find/reselect and verify | exact ODF text/guards; medium | S-N1; replacement consumes selected range |
| S-04 Selection | Select assigned Browser rows and bulk-update | Select disjoint rows and bulk-update | global selected-row set | peer selection changes bulk target; reselect and verify rows | row statuses + selection/bulk event; medium | S-01; set-valued selection and bulk action |
| U-02 Undo | Temporarily style Writer range, then Undo after B | Insert paragraph and restore after shared Undo | document undo stack | Undo consumes B's latest edit; B reobserves/re-enters | ODF style/text + action order; high | U-N1; character-style operation and peer recovery |
| U-03 Undo | Enter Calc formula then Undo after B | Set Calc value and restore after Undo | Calc document history | Undo reverts peer cell value; B restores it | ODF formula/value + Ctrl-Z chronology; high | U-01; formula/value recovery graph |
| U-04 Undo | Rich-editor insert, Undo peer history, restore both phrases | Insert independent rich-editor phrase | contenteditable history | Ctrl-Z removes latest peer insertion; reinsert and verify | exact editor text + commit/history events; high | U-N1; Browser editor history, not document paragraph edit |

## Candidate pool decisions

- Selected: F-05/F-06/F-07; C-04/C-05/C-06; A-03/A-04/A-05; S-02/S-03/S-04; U-02/U-03/U-04.
- Reserve: Browser file upload + Writer attachment review (F); image/object clipboard (C); Browser authentication-session context (A); Calc chart/object selection (S); Browser navigation-history recovery (U). These need stable, inspectable native state first.
- Rejected/merged: another plain-text transfer, another tab switch, another scalar cell edit, and an extra Writer paragraph replacement. They alter payload labels or targets without changing the operation graph.

All Solo, MA-ID, and MA-SD plans share fixture, goals, budget, evaluator, and schedule identifier. MA-ID uses equivalent initialized fixtures on isolated desktops; MA-SD shares one live desktop. This report makes no real-GUI execution claim.
