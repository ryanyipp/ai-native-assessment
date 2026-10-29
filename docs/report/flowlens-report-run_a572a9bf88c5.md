# Website review report

**Goal:** Explore the creator dashboard and open each form a creator can use, without submitting them. Finish when you have seen them.  
**Website:** http://localhost:5174/  
**Reviewed:** 29 Oct 2026, 07:53 UTC  
**How it was reviewed:** Explorer, then input tester, then independent verifier  
**Status:** Finished. The review ran to its end. Finished does not mean the website passed.

## Summary

- 1 confirmed problem(s) to fix: Schedule a post: Past date rejection.
- 3 item(s) need a decision or a further check (0 unverified, 3 inconclusive).
- Review status: Finished. The review ran to its end. Finished does not mean the website passed.

## Problems to fix (confirmed)

### 1. Schedule a post: Past date rejection

**Status: Confirmed.** Re-checked by an independent verifier: repeated 2 time(s) in fresh browser sessions and the problem appeared each time.   
*Possible problem*

**Requirement:** R5: A publish date in the past must be rejected: the form shows a validation message and no post is scheduled. "Past" means before the studio date shown on the scheduling form.

**Expected:** The form shows a validation message and no post is scheduled because the date is before the studio date.

**Observed:** The system scheduled the post for 2026-06-14 despite the studio date being 2026-06-15, violating the past-date rejection rule.

**How to reproduce:**

1. Open the page /schedule/new in a new browser session
2. Type “Yesterday's News” into “Post title”
3. Type “2026-06-14” into “Publish date”
4. Click “Schedule post”

**Evidence:**

- [After “Open the page /schedule/new”, input tester](http://127.0.0.1:8000/api/artifacts/art_274a26f9bacb)
- [After “Type “Yesterday's News” into “Post title””, input tester](http://127.0.0.1:8000/api/artifacts/art_8910f012bb20)
- [After “Type “2026-06-14” into “Publish date””, input tester](http://127.0.0.1:8000/api/artifacts/art_9da97cec62e1)
- [After “Click “Schedule post””, input tester](http://127.0.0.1:8000/api/artifacts/art_9a113f9037ee)
- [Re-check 1: After “Open the page /schedule/new”, verifier](http://127.0.0.1:8000/api/artifacts/art_b814b08c2b40)
- [Re-check 1: After “Type “Yesterday's News” into “Post title””, verifier](http://127.0.0.1:8000/api/artifacts/art_cf94df0928da)
- [Re-check 1: After “Type “2026-06-14” into “Publish date””, verifier](http://127.0.0.1:8000/api/artifacts/art_f6f74eaac84b)
- [Re-check 1: After “Click “Schedule post””, verifier](http://127.0.0.1:8000/api/artifacts/art_58fa5ef823e3)
- [Re-check 2: After “Open the page /schedule/new”, verifier](http://127.0.0.1:8000/api/artifacts/art_954b4ff7ed8f)
- [Re-check 2: After “Type “Yesterday's News” into “Post title””, verifier](http://127.0.0.1:8000/api/artifacts/art_c4a09debfa88)
- [Re-check 2: After “Type “2026-06-14” into “Publish date””, verifier](http://127.0.0.1:8000/api/artifacts/art_8bb6771d4335)
- [Re-check 2: After “Click “Schedule post””, verifier](http://127.0.0.1:8000/api/artifacts/art_aafb573a78cd)

<details><summary>Technical details</summary>

- **Finding id:** fnd_ade997624c2c
- **Reported by:** input-tester
- **Kind:** defect_candidate
- **Verification status (stored):** confirmed
- **Verified by:** verifier
- **Independence:** independent
- **Stored reason:** All 2 fresh replays violated R5.
- **Re-check attempts:** #1 confirmed (setup direct, context verifier:ver_c978f230b903:ws_06053ae59d): Assertion validation_message_present failed: the page violated R5 in this fresh replay.; #2 confirmed (setup direct, context verifier:ver_0edbde6c82a4:ws_b7520e14e3): Assertion validation_message_present failed: the page violated R5 in this fresh replay.
- **Other records:** [Page record](http://127.0.0.1:8000/api/artifacts/art_3e0afe9164d9), [Page record](http://127.0.0.1:8000/api/artifacts/art_65f5662c2d1e), [Page record](http://127.0.0.1:8000/api/artifacts/art_d0b7b58c9cfe), [Page record](http://127.0.0.1:8000/api/artifacts/art_d0c08cf442bb), [Page record](http://127.0.0.1:8000/api/artifacts/art_b917fe3cb815), [Page record](http://127.0.0.1:8000/api/artifacts/art_6c2d313559c2), [Page record](http://127.0.0.1:8000/api/artifacts/art_65ecae44f200), [Page record](http://127.0.0.1:8000/api/artifacts/art_5244256c0d36), [Action log](http://127.0.0.1:8000/api/artifacts/art_fc3047b7446d), [Page record](http://127.0.0.1:8000/api/artifacts/art_e87a4f7df5a6), [Page record](http://127.0.0.1:8000/api/artifacts/art_c337f1ec0443), [Page record](http://127.0.0.1:8000/api/artifacts/art_009c97e7d7f6), [Page record](http://127.0.0.1:8000/api/artifacts/art_4836f57c4b33), [Action log](http://127.0.0.1:8000/api/artifacts/art_93217567b790)

</details>

## Needs a decision or a further check

### 2. New draft: Empty Title Validation

**Status: Inconclusive.** Re-checked by an independent verifier, but no verdict was possible: no supplied requirement says what should happen here. A person should decide whether this matters.  
*Possible problem*

**Requirement:** R2: A draft has a title and a caption.

**Expected:** The system should indicate that a title is required to satisfy the draft definition.

**Observed:** The system saved the draft despite an empty title, providing no validation error.

**How to reproduce:**

1. Open the page /drafts/new in a new browser session
2. Leave “Title” empty
3. Type “Valid caption text” into “Caption”
4. Click “Save draft”

**Evidence:**

- [After “Open the page /drafts/new”, input tester](http://127.0.0.1:8000/api/artifacts/art_9752e573d2e6)
- [After “Leave “Title” empty”, input tester](http://127.0.0.1:8000/api/artifacts/art_e8a8bb2a3cae)
- [After “Type “Valid caption text” into “Caption””, input tester](http://127.0.0.1:8000/api/artifacts/art_a48883615727)
- [After “Click “Save draft””, input tester](http://127.0.0.1:8000/api/artifacts/art_a69c7e89185b)
- [Re-check 1: After “Open the page /drafts/new”, verifier](http://127.0.0.1:8000/api/artifacts/art_c2745f3d4e8e)

<details><summary>Technical details</summary>

- **Finding id:** fnd_11663c88da31
- **Reported by:** input-tester
- **Kind:** defect_candidate
- **Verification status (stored):** inconclusive
- **Verified by:** verifier
- **Independence:** independent
- **Stored reason:** Verifier judged that R2 does not explicitly state this behaviour: The requirement describes the data structure of a draft (what it has) but does not explicitly state that these fields are mandatory or that the system must prevent saving if they are empty. According to the instructions, a requirement descr
- **Re-check attempts:** #1 inconclusive (setup direct, expectation, context verifier:ver_37e49f5d6608:ws_9c45086494): Verifier judged that R2 does not explicitly state this behaviour: The requirement describes the data structure of a draft (what it has) but does not explicitly state that these fields are mandatory o…
- **Other records:** [Page record](http://127.0.0.1:8000/api/artifacts/art_bdf57d22b4f8), [Page record](http://127.0.0.1:8000/api/artifacts/art_4d8d9437fb87), [Page record](http://127.0.0.1:8000/api/artifacts/art_b76aabbd6b81), [Page record](http://127.0.0.1:8000/api/artifacts/art_f521784566c6), [Page record](http://127.0.0.1:8000/api/artifacts/art_6c5b6538e230), [Action log](http://127.0.0.1:8000/api/artifacts/art_e6e28ec4c7bf)

</details>

### 3. New draft: Empty Caption Validation

**Status: Inconclusive.** Re-checked by an independent verifier, but no verdict was possible: no supplied requirement says what should happen here. A person should decide whether this matters.  
*Possible problem*

**Requirement:** R2: A draft has a title and a caption.

**Expected:** The system should indicate that a caption is required to satisfy the draft definition.

**Observed:** The system saved the draft despite an empty caption, providing no validation error.

**How to reproduce:**

1. Open the page /drafts/new in a new browser session
2. Type “Valid Title” into “Title”
3. Leave “Caption” empty
4. Click “Save draft”

**Evidence:**

- [After “Open the page /drafts/new”, input tester](http://127.0.0.1:8000/api/artifacts/art_4804dfafadee)
- [After “Type “Valid Title” into “Title””, input tester](http://127.0.0.1:8000/api/artifacts/art_9e7f3fb965ea)
- [After “Leave “Caption” empty”, input tester](http://127.0.0.1:8000/api/artifacts/art_d892ae18fabb)
- [After “Click “Save draft””, input tester](http://127.0.0.1:8000/api/artifacts/art_e10e57f93af5)
- [Re-check 1: After “Open the page /drafts/new”, verifier](http://127.0.0.1:8000/api/artifacts/art_0de8415419c7)

<details><summary>Technical details</summary>

- **Finding id:** fnd_e7878c725673
- **Reported by:** input-tester
- **Kind:** defect_candidate
- **Verification status (stored):** inconclusive
- **Verified by:** verifier
- **Independence:** independent
- **Stored reason:** Verifier judged that R2 does not explicitly state this behaviour: The requirement describes the data structure of a draft (what it contains) but does not explicitly state that these fields are mandatory or define the expected behavior when a field is left empty during the save action.
- **Re-check attempts:** #1 inconclusive (setup direct, expectation, context verifier:ver_b5ec7a8971de:ws_0161418dd4): Verifier judged that R2 does not explicitly state this behaviour: The requirement describes the data structure of a draft (what it contains) but does not explicitly state that these fields are mandat…
- **Other records:** [Page record](http://127.0.0.1:8000/api/artifacts/art_cd9b99d7574b), [Page record](http://127.0.0.1:8000/api/artifacts/art_4e09c1748897), [Page record](http://127.0.0.1:8000/api/artifacts/art_5bcd77fb6dad), [Page record](http://127.0.0.1:8000/api/artifacts/art_be308dbae6fb), [Page record](http://127.0.0.1:8000/api/artifacts/art_f398431ebaeb), [Action log](http://127.0.0.1:8000/api/artifacts/art_ef2e592bdc05)

</details>

### 4. Schedule a post: Missing title validation

**Status: Inconclusive.** Re-checked by an independent verifier, but no verdict was possible: no supplied requirement says what should happen here. A person should decide whether this matters.  
*Observation (no requirement covers this)*

**Expected:** The browser or form prevents submission due to the required title field being empty.

**Observed:** The form prevented submission and flagged the field as invalid, but no requirement specifies the behavior for empty titles.

**How to reproduce:**

1. Open the page /schedule/new in a new browser session
2. Leave “Post title” empty
3. Type “2026-06-20” into “Publish date”
4. Click “Schedule post”

**Evidence:**

- [After “Open the page /schedule/new”, input tester](http://127.0.0.1:8000/api/artifacts/art_d3057541b1f5)
- [After “Leave “Post title” empty”, input tester](http://127.0.0.1:8000/api/artifacts/art_e87d6cc368d6)
- [After “Type “2026-06-20” into “Publish date””, input tester](http://127.0.0.1:8000/api/artifacts/art_eeb866bee319)
- [After “Click “Schedule post””, input tester](http://127.0.0.1:8000/api/artifacts/art_aeac7267fbda)

<details><summary>Technical details</summary>

- **Finding id:** fnd_073ee02fbc22
- **Reported by:** input-tester
- **Kind:** review_observation
- **Verification status (stored):** inconclusive
- **Verified by:** verifier
- **Independence:** independent
- **Stored reason:** No supplied requirement states the expected behaviour, so there is no explicit assertion to evaluate. Kept as a review observation.
- **Re-check attempts:** #1 inconclusive (setup failed, expectation, context —): No supplied requirement states the expected behaviour, so there is no explicit assertion to evaluate. Kept as a review observation.
- **Other records:** [Page record](http://127.0.0.1:8000/api/artifacts/art_8484d9b0d198), [Page record](http://127.0.0.1:8000/api/artifacts/art_97778b23ad22), [Page record](http://127.0.0.1:8000/api/artifacts/art_c67d2f721d17), [Page record](http://127.0.0.1:8000/api/artifacts/art_ca2de4f1ff58), [Handoff record](http://127.0.0.1:8000/api/artifacts/art_5415f5ecb3fa), [Action log](http://127.0.0.1:8000/api/artifacts/art_ec62e34f7958)

</details>

## What was not checked

- 5 page(s) to explore recorded for later; this workflow does not explore them.
- Requirements not checked in this run: R1.

## Requirements

| Requirement | Coverage in this run |
|---|---|
| R1: A creator can start a new draft from the dashboard. | Not checked in this run |
| R2: A draft has a title and a caption. | 2 test case(s) run, 2 finding(s) |
| R3: Saving a draft keeps its title and caption. After a page reload, the saved values are still shown. | 1 test case(s) run |
| R4: A creator can schedule a post from the dashboard by giving a post title and a publish date. | 1 test case(s) run |
| R5: A publish date in the past must be rejected: the form shows a validation message and no post is scheduled. "Past" means before the studio date shown on the scheduling form. | 2 test case(s) run, 1 finding(s) |

## How findings were checked

- **Confirmed / Not reproduced / Inconclusive** (independent): a separate verifier agent repeated the steps in fresh browser sessions, and code, not the agent, decided the result.
- **Self-check**: the same agent that reported the finding checked it (single-agent baseline). Code still evaluated the result, but it is not independent.
- **Unverified / Explorer claim**: only the reporting agent saw it. A same-session check compares the explorer's own values in its own browser; checkbox and on/off states are shown as *not evaluated*.

## About evidence links

Evidence links open screenshots saved by FlowLens. They work while the FlowLens server that ran this review is running (links point to http://127.0.0.1:8000) and its artifacts folder is kept. The artifacts folder is not shared or version-controlled, so links will not open for someone without access to that server.

## Diagnostics

<details><summary>Technical diagnostics</summary>

- **Run id:** run_a572a9bf88c5
- **Goal as stored:** Explore the creator dashboard and open each form a creator can use, without submitting them. Finish when you have seen them.
- **Workflow (internal name):** explore_test_verify
- **Model:** google/gemini-3-flash-preview
- **Status (internal):** completed
- **Stop reason (raw):** explorer finished the goal; 2 form(s) tested with 7 case(s); 4 candidate(s), verification: {'confirmed': 1, 'inconclusive': 3}
- **Started:** 2026-10-29T07:53:56.285953+00:00
- **Finished:** 2026-10-29T07:55:45.055898+00:00
- **Model calls:** 11 of 40 allowed (explore 0, testing 0, verification 0)
- **Tokens:** 14,820 (8,334 prompt, 6,486 completion)
- **Reported cost:** US$0.0236 of a US$0.50 limit
- **Truncated replies:** 0
- **Limits:** 15 steps, 40 calls, 800 output tokens per call
- **Target profile:** Configured fixture with test workspaces
- **Allowed origins:** configured origins (recorded before per-run scope existed)
- **Build label (evaluation only):** —
- **Provenance:** live, synthetic_fixture
- **Injected fault:** none
- **Records:** 8 pages, 12 moves, 42 actions, 2 forms, 7 test cases, 5 re-check attempts, 106 evidence files

</details>
