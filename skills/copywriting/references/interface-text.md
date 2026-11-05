# Interface text

For text that tells people what a control does or what state the app is in:
settings, toggles, sliders, field labels, helper text, buttons, menus,
status, errors, empty states. Its job is prediction: a first-time reader
knows what will happen before they act. Shorter is never the goal here.

## 1. Write the truth sentence first

Read the code that uses the control. Write one plain sentence: "When
[trigger], the app [action] [object] [value and unit]." Every label is judged
against it. A label that disagrees with the code is the best reason to
change one; a label that is only plain or a little long is not a reason.

## 2. Keep every slot

List what the old string tells the reader. Each slot must survive in the new
label, or in text that is visible at the same moment (the shown value, the
section header, helper text).

| Slot | Example words |
| --- | --- |
| Action: what the app does | mute, lock, hide, send |
| Object: what it acts on | backups, the screen, replies |
| Trigger, condition, timing | after, when, while, until, only, each, automatically |
| Value meaning and unit | how long, how many, minutes |
| Polarity: what "on" means | allow or block |

A rewrite that drops a slot or makes it vaguer is rejected, however short.
"Delay backups after the laptop wakes" (10 min) keeps all five. "Wake
buffer" and "Extra time after waking" lose the action and the object. "Wait
after waking" keeps a verb but no object, and reads as if the user waits.

## 3. Checks on the new string

Run all of them. One failure means keep the old string or try again.

- **Blind test.** From the new label, its value and its header alone, write
  what the control does. Compare with the truth sentence.
- **Label plus value.** Say "[label]: [value]" aloud with the default, the
  minimum, the maximum and any special value ("Never", "None"). Each must be
  a true statement, and it must be clear what the number measures.
- **On and off.** "[label]: on" and "[label]: off" both describe a real
  state, and they are opposites. If off is not the obvious opposite, the
  control needs two labelled options, not a better label.
- **Verb kept.** If the old string had a verb and the new one has none,
  reject it, unless the new noun is a feature people already know by name
  ("Notifications", "Language").
- **No abstract head word.** time, extra, buffer, mode, options, behaviour,
  experience, general, manage, handle. They name no action.
- **One reading.** Could the main verb mean two things here? "Reset" can mean
  restore the defaults or erase the data. Pick the verb with one reading.
- **Negations.** Phrase the on state positively: "Don't allow X" becomes
  "Block X". Never flip what "on" means; that changes behaviour and consent,
  not copy.
- **Neighbours.** The first two words tell this row apart from the rows
  around it. Sibling rows share one grammatical shape.
- **Terms.** Search the codebase for the old and the new word. One concept
  keeps one name in labels, messages, menus and docs. Use the word a user
  would say, not the name in the code.

## 4. What may be cut

Safe to cut: articles, "please", "you can", "your", instruction verbs that
fit any control (set, choose, select, manage, configure), filler ("simply",
"quickly"), and words the visible section header already says.

Never cut: the verb that names what the app does, its object, the trigger
words, the unit.

## 5. By element

- **Behaviour settings** take a verb phrase: "Lock the screen when the lid
  closes". A bare noun is only for a known feature.
- **Sliders and steppers**: the label names what the number measures and the
  value shows its unit. Do not rely on label and value forming one
  grammatical sentence; word order breaks in translation.
- **Helper text** adds a fact the label cannot hold: a condition, a
  consequence, the scope. It never restates the label, and the label must
  still work with the helper hidden.
- **Section headers** name what the group is for. Rows do not repeat them.
- **Buttons** name the outcome with a verb and, when needed, its object:
  "Delete draft", not "OK". Dialog buttons answer the dialog's title. "Save"
  only when something is stored, "Cancel" only when nothing changes.
- **Errors** say what happened and how to fix it, in the field's own words,
  next to the problem. No blame, no "invalid", no "oops".
- **Empty states** say why it is empty and how the first item gets there.
- **Status** names the specific thing: "Syncing calendar…", not "Working…".

## 6. Leave it alone when

- The string passes the checks. Plain, boring and slightly long are fine.
- It is a platform or industry standard: Back, Undo, Settings, Cancel.
- The change would only swap a synonym. Readers assume a new word means a
  new thing, and existing users have to relearn it.
- The control itself is confusing. No wording fixes that; say so in the
  handoff instead of polishing.

Match the conventions already in the codebase for capitalisation, colons,
ellipses, periods and units. Do not restyle them. Every language in the
string must pass the same checks.
