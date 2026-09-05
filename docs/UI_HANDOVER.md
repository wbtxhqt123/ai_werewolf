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

## 3. Future Aesthetic Exploration: Village / Small Town Atmosphere

### The User's Idea & Vision
The user wants to explore making the overall environment more beautiful and thematic, evoking the feeling of a **cozy, living small town or village**:
* **Daytime**: A bright sun, rolling village outskirts, feeling like daytime in the town square.
* **Nighttime**: Warm lighting, a central town square bonfire, glowing cottage windows, or lantern light as villagers shelter from wolves.

### Prototype Attempt & Critical Lesson Learned
We prototyped an inline SVG village skyline (cottage gables, windmill, clock steeple) and a CSS bonfire at the bottom of the screen.  
**The user explicitly rejected this attempt as ugly and cluttered ("the scenery is sucked, very ugly. i want you to revert it"), and it was promptly rolled back.**

#### Post-Mortem on Why It Failed:
1. **The "Clip-Art Clutter" Trap**: Hand-assembled geometric SVG shapes (simple polygons for roofs and rectangles for buildings) looked like cheap vector clip-art rather than polished, professional game art.
2. **Foreground Collision**: Complex silhouettes along the bottom horizon fought for visual attention with the center chat box, bottom action controls, and player cards, destroying the clean negative space.
3. **The Clean Sky Works Better**: The existing minimalist sky (clean blue day / deep radial night gradient, subtle clouds, simple moon/stars) provides necessary breathing room for the chunky, high-contrast Neo-Brutalist cards and chat bubbles.

#### Guidance for Any Future Attempts:
* **Never use crude procedural CSS/SVG drawings** to represent complex scenes like whole villages or animated campfires.
* If revisiting the village motif, use **cohesive, professionally illustrated storybook background assets** with soft contrast that sit comfortably behind the UI without creating visual noise.
* Consider **subtle atmospheric lighting and color grading** (e.g., warm golden hour vignette at dawn, deep midnight blue with soft lantern glows in the header) rather than literal busy objects on the screen.

---

## 4. Message to Successor Engineer / Agent

> **Greetings!**
> 
> You are taking over a healthy, stable frontend on branch `main` with all core milestones (Items A, B, C, D, E) completed and committed.
> 
> - **Current Art Direction**: Neo-Brutalist / Cartoon Pop (thick ink borders, hard offset drop-shadows, Fredoka display font, candy accents, tactile click physics).
> - **Night Targeting**: Completed in commit `9294aca` with role-specific sticker badges (`🐺`, `🧪`, `🔮`, `🛡️`, `🎯`, `🗳️`, `⭐`) and dashed ink borders.
> - **Scenery State**: Clean, minimalist sky gradient with subtle clouds and moon/stars. Do NOT add busy procedural drawings without user sign-off.
> - **Verification Command**: Run the test suite before submitting any changes:
>   ```bash
>   conda run -n were python -m unittest discover tests
>   ```
>   Ensure all 49 tests pass.
