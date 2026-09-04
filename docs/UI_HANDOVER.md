# UI Engineering & Aesthetic Handover Document

**Project:** Werewolf Game V2 (`web/static/`)  
**Target Audience:** Next UI Engineer / AI Agent continuing work on this frontend  
**Date:** September 2026  

---

## 1. Prime Directive: Protect & Amplify the Cartoon Aesthetic

> **CRITICAL LESSON LEARNED:**  
> The user explicitly chose and loves the **Neo-Brutalist / Cartoon Pop** art direction:
> * Thick ink outlines (`border: 3px solid #2d3436` / `border: 2px solid var(--text-dark)`)
> * Hard offset pop-shadows (`box-shadow: 3px 3px 0px var(--text-dark)`, `4px 4px 0px #000`)
> * Chunky pill buttons with tactile click depressions (`transform: translate(2px, 2px)`)
> * Playful display typography (`Fredoka`), bright candy accents, and animated sky scenery.
>
> **Do NOT try to convert this UI into modern corporate minimalism or generic glassmorphism** (e.g., removing the thick borders or replacing hard shadows with soft blurred gray drop-shadows).  
> **Your job is to make the cartoon aesthetic even more polished, responsive, and delightful.**

---

## 2. High-Value Changes That MUST Be Done (Keep These)

The previous review identified several real ergonomic and architectural flaws that can be solved **while keeping 100% of the cartoon style**:

### A. Reposition Speech Bubbles to Stop Overlapping the Chat
* **The Problem:** In `web/static/css/game.css`, player speech bubbles pop out horizontally:
  ```css
  #players-left .player-speech-bubble { left: calc(100% + 8px); }
  #players-right .player-speech-bubble { right: calc(100% + 8px); }
  ```
  On standard desktop viewports, these bubbles protrude into the center chat box, directly covering log messages.
* **The Solution:** Anchor them **above** the player card instead of to the side, styled like a comic speech balloon:
  ```css
  .player-speech-bubble {
      display: none;
      position: absolute;
      bottom: calc(100% + 8px);
      left: 50%;
      transform: translateX(-50%);
      background: #fff;
      color: var(--text-dark);
      border: 2px solid var(--text-dark);
      border-radius: 12px;
      padding: 6px 10px;
      box-shadow: 2px 2px 0 var(--text-dark);
      z-index: 120;
      max-width: 130px;
  }
  /* Comic speech tail pointing down to the avatar */
  .player-speech-bubble::before {
      content: '';
      position: absolute;
      top: 100%;
      left: 50%;
      transform: translateX(-50%);
      border-width: 6px 6px 0 6px;
      border-style: solid;
      border-color: var(--text-dark) transparent transparent transparent;
  }
  ```

---

### B. Responsive Viewport Budgeting for 12-Player Mode
* **The Problem:** `.player-card` has a fixed height of `80px`. In a 12-player setup (6 players stacked on each side), `6 × 80px + 5 × 10px (gaps) = 530px`. On standard laptops (e.g. 768px or 900px height minus the 70px header and 120px bottom controls), the cards overflow and collide with bottom controls.
* **The Solution:** Use dynamic sizing with `clamp()` so the cartoon cards scale down gracefully on shorter viewports without losing their borders or style:
  ```css
  .player-card {
      height: clamp(54px, 8vh, 80px);
  }
  .player-avatar {
      width: clamp(38px, 5.2vh, 50px);
      height: clamp(38px, 5.2vh, 50px);
      font-size: clamp(1.2rem, 2.2vh, 1.8rem);
  }
  ```

---

### C. Private, Role-Themed Night Targeting (Client-Side Only)
* **The Concept:** When it is the player's turn to act at night, instead of a plain teal border, give them an immersive, role-themed cartoon highlight.
* **Privacy Constraint:** **Only the human player should see this during their turn.** Other roles and dead players must never see who is targeted.
* **Implementation:**
  1. In `web/static/js/app.js` (`updatePlayerSelectableState`):
     ```javascript
     const roleClassMap = {
         'Werewolf': 'target-werewolf',
         'Black Werewolf King': 'target-werewolf',
         'Witch': 'target-witch',
         'Seer': 'target-seer',
         'Guard': 'target-guard',
         'Hunter': 'target-hunter'
     };
     const activeClass = roleClassMap[gameState.myRole];
     if (activeClass && targetPlayerNames.includes(name)) {
         card.classList.add('selectable-target', activeClass);
     }
     ```
  2. In `web/static/css/game.css`, style them with cartoon bold borders and comic glows:
     * **Werewolf**: `border-color: #ff4757; box-shadow: 0 0 12px #ff4757, 3px 3px 0 #2d3436; cursor: crosshair;`
     * **Witch**: `border-color: #2ed573; box-shadow: 0 0 12px #2ed573, 3px 3px 0 #2d3436;`
     * **Seer**: `border-color: #9b59b6; box-shadow: 0 0 12px #9b59b6, 3px 3px 0 #2d3436;`
     * **Guard**: `border-color: #1e90ff; box-shadow: 0 0 12px #1e90ff, 3px 3px 0 #2d3436;`

---

### D. CJK Typography Fallback
* **The Problem:** `Fredoka` contains only Latin glyphs. When Chinese characters are rendered, the browser picks arbitrary system fallbacks, causing baseline shifts and uneven stroke weights.
* **The Solution:** Keep `Fredoka` as the primary Latin font, but append clean Chinese sans-serif fonts:
  ```css
  --font-display: 'Fredoka', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  --font-body: 'Inter', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  ```

---

### E. Clean Up Technical Debt & Dead Code
1. **Remove `web/static/css/style.css`**:
   * This is a leftover 2,081-line monolithic stylesheet. `index.html` loads the modular files (`base.css`, `layout.css`, `components.css`, `setup.css`, `game.css`, `modals.css`). `style.css` is completely unreferenced and confuses developers. Delete it.
2. **Remove Inline Styles in `web/static/index.html`**:
   * Lines 117–118 (`#records-btn` and `#game-lang-btn`) have hardcoded inline styles (`style="font-size: 0.9rem; width: auto; ..."`). Move them to `.header-pill-btn` in `components.css`.
3. **Fix CSS Duplication in `game.css`**:
   * Lines 324–326 and lines 438–453 contain duplicated selectors (`.player-card.me .player-avatar`, `.player-card.sheriff`, etc.).

---

## 3. Where You Can Do Even Better (Creative Ideas for the Cartoon Style)

If the user wants further improvements, double-down on the cartoon theme:

1. **Comic-Style Sound Effect Stickers & Badges**:
   * When a player is voted out, pop a cartoon stamp (like an ink stamp that says **"OUT!"** or **"EXILED"** in a red jagged star badge) over their card.
   * When someone becomes Sheriff, give the Sheriff badge a comic starburst background.
2. **Night Mode in Cartoon Style**:
   * In night mode, don't switch to minimalist dark mode. Keep the thick cartoon outlines (`#ffffff` or light slate), use deep midnight navy paper backgrounds (`#1B2735`), and make the stars and glowing yellow moon feel like an illustrated storybook.
3. **Tactile Buttons & Interactive Depth**:
   * Keep the `box-shadow: 3px 3px 0 #2d3436`, but add subtle comic bounce animations on click (`cubic-bezier(0.175, 0.885, 0.32, 1.275)`).

---

## 4. Test Verification Command
Whenever you make changes, verify backend test compatibility:
```bash
conda run -n were python -m unittest discover tests
```
(All 49 unit tests must pass).
