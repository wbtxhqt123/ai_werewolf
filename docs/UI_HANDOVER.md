# UI Engineering & Aesthetic Handover Document

**Project:** Werewolf Game V2 (`web/static/`)  
**Target Audience:** Next UI Engineer / AI Agent continuing work on this frontend  
**Date:** September 2026  
**Status:** Items A, B, C, D, E Completed & Verified

---

## 1. Prime Directive: Protect & Amplify the Cartoon Aesthetic

> **CRITICAL LESSON LEARNED:**  
> The user explicitly chose and loves the **Neo-Brutalist / Cartoon Pop** art direction:
> * Thick ink outlines (`border: 3px solid #2d3436` / `border: 2px solid var(--text-dark)`)
> * Hard offset pop-shadows (`box-shadow: 3px 3px 0px var(--text-dark)`, `4px 4px 0px #000`)
> * Chunky pill buttons with tactile click depressions (`transform: translate(2px, 2px)`)
> * Playful display typography (`Fredoka`), bright candy accents, and animated sky scenery.
>
> **Do NOT try to convert this UI into modern corporate minimalism, cyberpunk neon glows, or generic glassmorphism.**  
> (e.g., do NOT add blurry neon `box-shadow` glows or standard thin OS crosshair cursors — the user found them ugly!).  
> **Your job is to make the cartoon aesthetic tactile, playful, responsive, and delightful.**

---

## 2. Completed Foundation Work

The following high-priority refactors and fixes have been completed and verified against all 49 unit tests:

* [x] **Item E: Technical Debt & Dead Code Cleanup** (Commit `002bb0c`)
  - Deleted obsolete 2,081-line monolith `web/static/css/style.css`.
  - Moved hardcoded inline styles on `#records-btn` and `#game-lang-btn` in `index.html` to `.icon-btn.header-pill-btn` in `components.css`.
  - Consolidated duplicate selectors for player cards and avatars in `game.css`.
* [x] **Item D: CJK Typography Fallback** (Commit `950ff51`)
  - Appended `PingFang SC`, `Hiragino Sans GB`, and `Microsoft YaHei` to `--font-display` and `--font-body` in `base.css` to prevent font-metric jitter in Chinese text.
* [x] **Item A: Reposition Speech Bubbles Above Player Cards** (Commit `d28cbb4`)
  - Anchored speech bubbles to `bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%);` with a comic balloon tail.
  - Eliminated horizontal protrusion that previously covered the center chat box.
* [x] **Item B: Responsive Viewport Budgeting for 12-Player Mode** (Commit `9591723`)
  - Converted `.player-card` height to `clamp(54px, 8vh, 80px)` and avatar dimensions to `clamp(38px, 5.2vh, 50px)`.
  - Scaled side column gap with `clamp(4px, 1vh, 10px)` to prevent vertical collision with bottom controls on ≤900px laptop screens.
* [x] **Item C: Private Cartoon Pop Night & Vote Targeting**
  - Implemented role-aware targeting badges and framing per `docs/CARTOON_TARGETING_PROPOSAL.md`.
  - Replaced blurry neon glows and system crosshairs with chunky **dashed ink borders** (`border: 3px dashed <accent>`), comic drop-shadows (`4px 4px 0 var(--text-dark)`), and tactile click depressions.
  - Attached physical cartoon sticker badges (`::after`) with entrance pop & subtle idle bob animations (`🐺` Werewolf, `🧪` Witch poison, `🔮` Seer lens, `🛡️` Guard shield, `🎯` Hunter bullseye, `🗳️` Vote, `⭐` Sheriff badge).
  - Soft recession for non-target cards (`opacity: 0.65; transform: scale(0.96); filter: saturate(70%); pointer-events: none;`) preserving ink lines and color rather than muddy grayscale.
  - Client-side privacy preserved: targeting state only renders during the human player's active input prompt.

---

## 3. Your Immediate Next Task: Implement Cartoon Night Targeting (Item C)

### What Happened in the Previous Attempt
An initial implementation of role-themed targeting was tested using colored solid borders, blurry neon `box-shadow: 0 0 14px <color>` glows, and OS `cursor: crosshair`.  
**The user explicitly rejected this as ugly**, because neon blurry glows and sterile CAD crosshairs break the comic book aesthetic. That change was rolled back to maintain a clean codebase.

### The Approved Path Forward
Read **[`docs/CARTOON_TARGETING_PROPOSAL.md`](CARTOON_TARGETING_PROPOSAL.md)** for the complete design specification and implementation blueprint.

#### Key Directives for the Implementation:
1. **Physical Props & Floating Stickers**:
   - Instead of a blurry box-shadow, attach a **chunky cartoon sticker badge** to the corner of valid target cards using CSS pseudo-elements (`::after`):
     - 🐺 **Werewolf / Wolf King**: Candy-crimson pawprint stamp (`🐺`) or claw mark.
     - 🧪 **Witch**: Emerald bubbling poison flask (`🧪`) or candy-pink heart antidote.
     - 🔮 **Seer**: Violet magnifying lens sticker (`🔮`).
     - 🛡️ **Guard**: Sturdy riveted iron shield badge (`🛡️`).
     - 🏹 **Hunter**: Pop-art suction-cup bullseye arrow (`🎯`).
2. **Cartoon Framing**:
   - Give active target cards a thick **dashed ink border** (`border: 3px dashed <accent>`) on a clean warm-paper card fill, with hard comic drop-shadow (`box-shadow: 4px 4px 0 var(--text-dark)`).
3. **Cartoon Hover Physics**:
   - On hover, tilt cards with spring physics (`transform: translateY(-6px) scale(1.04) rotate(-1.5deg);` using `cubic-bezier(0.34, 1.56, 0.64, 1)`).
4. **Inactive Player De-emphasis**:
   - Do NOT turn inactive cards into dreary 50% grayscale mud. Simply use `opacity: 0.65; transform: scale(0.96); filter: saturate(70%);` so the board stays colorful and cohesive.
5. **Strict Client-Side Secrecy Constraint**:
   - Target styles must **only** be visible on the human player's browser when `updatePlayerSelectableState(targets)` is triggered for their private turn. AI turns and dead players must never leak target eligibility.

---

## 4. Message to Successor Engineer / Agent

> **Greetings!**
> 
> You are taking over a healthy, stable frontend on branch `main` with 0 uncommitted regressions.
> 
> - **Primary Reference**: Review `docs/CARTOON_TARGETING_PROPOSAL.md` before writing code for night targeting.
> - **CSS Architecture**: Work within the modular stylesheets:
>   - `web/static/css/game.css` for card states and targeting animations.
>   - `web/static/js/app.js` (`updatePlayerSelectableState`) for client-side class toggling based on `gameState.myRole`.
> - **Verification Command**: Run the test suite before submitting:
>   ```bash
>   conda run -n were python -m unittest discover tests
>   ```
>   Ensure all 49 tests pass.
