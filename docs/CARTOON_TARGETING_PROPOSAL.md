# Cartoon Pop UI: Night Targeting & Interactive Mechanics Proposal

**Project:** Werewolf Game V2  
**Document:** `docs/CARTOON_TARGETING_PROPOSAL.md`  
**Date:** September 2026  
**Status:** Design Proposal & Technical Blueprint  

---

## 1. Post-Mortem: Why the Previous Attempt Felt "Ugly"

In Step 5, we tested a common developer instinct for targeting: adding colored `box-shadow` glows (`box-shadow: 0 0 14px <color>`) and changing the card border color. The result felt jarring and cheap for four specific reasons:

1. **The "Cyberpunk Glow" Trap**: Soft, blurred neon drop-shadows belong in dark sci-fi or cyberpunk interfaces. In a Neo-Brutalist / Cartoon Pop art style (thick ink outlines, hard offset drop-shadows, candy colors), blurred colored glows look like a rendering artifact or an unstyled CSS glow from 2012.
2. **Muddy Border Tinting**: Simply recoloring the outer 2px card border muddies the card's crisp ink silhouette (`border: 2px solid var(--text-dark)`), making cards look dirty rather than emphasized.
3. **OS System Crosshair Ruined the Immersion**: The browser's default `cursor: crosshair` is a razor-thin, sterile technical cross from 1990s CAD/desktop software. It completely broke the soft, bubbly, tactile feel of the UI.
4. **Drab Grayscale De-emphasis**: Applying `filter: grayscale(50%); opacity: 0.45;` to non-targetable players washed the vibrant board out with drab, depressing gray blocks.

---

## 2. Core Art Direction: The Comic Pop Playbook

To make night actions feel **delightful, physical, and authentically cartoon**, we adhere strictly to three visual principles:

### A. Physical Props & Stickers (Instead of Box Shadows)
In comic books and games like *Brawl Stars*, *Cuphead*, or *Mario Party*, special actions are represented by **physical cartoon objects**—stickers, badges, stamps, and floating props with thick ink borders and clean paper drop-shadows.

### B. Cartoon Physics (Squash, Stretch & Spring)
Instead of linear fades:
* **Hover wobble**: Cards tilt slightly (`rotate(-1.5deg)`) with a playful bounce.
* **Spring timing**: Use spring curves (`cubic-bezier(0.34, 1.56, 0.64, 1)` or `cubic-bezier(0.175, 0.885, 0.32, 1.275)`) that make interactive elements feel rubbery and responsive.

### C. Hand-Drawn Marching Dashes & Halftones
Instead of solid neon borders, active selectable cards use **chunky cartoon dashed outlines** or **comic starburst decals** that feel sketched with an ink pen.

---

## 3. Role-by-Role Thematic Targeting Concepts

Here is the role-by-role design matrix for night targeting:

```
┌──────────────────────┬──────────────────────────────────┬──────────────────────────────────────┐
│ Role                 │ Visual Prop / Badge              │ Animation & Micro-interaction        │
├──────────────────────┼──────────────────────────────────┼──────────────────────────────────────┤
│ 🐺 Werewolf / King   │ Comic Red Pawprint / Claw Stamp  │ Gentle "Thump-thump" heartbeat scale │
│ 🧙‍♀️ Witch (Poison)   │ Bubbly Emerald Skull Flask       │ Floating cork bob + tiny pop bubbles │
│ 🧙‍♀️ Witch (Antidote) │ Sparkling Pink Heart Elixir      │ Gentle golden sparkle pulse          │
│ 🔮 Seer              │ Cartoon Magnifying Lens Badge    │ Detective searchlight tilt & wobble  │
│ 🛡️ Guard             │ Riveted Brass-Trim Shield Brooch │ Reassuring "Anchor" downward bob     │
│ 🏹 Hunter (Shot)     │ Pop-Art Suction Cup Bullseye     │ Rubber-band stretch crosshair        │
└──────────────────────┴──────────────────────────────────┴──────────────────────────────────────┘
```

---

### Detailed Role Specifications

#### 1. 🐺 Werewolf: "The Night Stalker"
* **Badge**: A chunky red cartoon pawprint badge or claw scratch sticker pinned to the top-right corner of the target's avatar.
  * Border: `2px solid #2d3436`
  * Background: Candy Crimson (`#ff4757`)
  * Drop shadow: `2px 2px 0 #2d3436`
* **Card Frame**: The card gets a thick, jaunty **dashed ink border** (`border: 3px dashed #ff4757`).
* **Hover Interaction**: On hover, the target card tilts slightly (`rotate(-2deg) scale(1.05)`), and the pawprint sticker gives a playful comic jiggle.
* **Cursor**: Instead of the OS crosshair, use a cute SVG pawprint or circular cartoon reticle:
  ```css
  cursor: url("data:image/svg+xml,..."), pointer;
  ```

#### 2. 🧙‍♀️ Witch: "The Alchemist's Potions"
* **Poison Mode (Harm)**:
  * **Badge**: A bubbly purple-and-green potion flask with a wooden cork sticker attached to the target card.
  * **Card Frame**: Lime-green dashed ink border (`border: 3px dashed #2ed573`).
  * **Motion**: Tiny cartoon bubble specks gently float upward and pop.
* **Antidote Mode (Save)**:
  * **Badge**: A sparkling heart elixir flask with a soft candy-pink gloss.
  * **Card Frame**: Warm gold dashed border (`border: 3px dashed #f1c40f`).
  * **Motion**: A warm, reassuring heartbeat bounce.

#### 3. 🔮 Seer: "The Inspector's Gaze"
* **Badge**: A retro cartoon magnifying glass or glowing eye sticker sitting over the avatar's shoulder.
* **Card Frame**: Mystical violet dashed border (`border: 3px dashed #9b59b6`).
* **Motion**: The magnifying glass badge tilts back and forth as if scanning (`transform: rotate(10deg)` ↔ `rotate(-10deg)`).
* **Hover Interaction**: On hover, the lens "focuses" (briefly zooms in with a cartoon pop sound or visual spring).

#### 4. 🛡️ Guard: "The Iron Watch"
* **Badge**: A chunky blue comic shield badge with visible metallic rivets and a white star in the center.
* **Card Frame**: Royal blue dashed border (`border: 3px dashed #1e90ff`).
* **Motion**: Gentle protective bobbing (vertical hover float of 3px).
* **Hover Interaction**: When hovered, the shield badge snaps to the center of the card like armor plating being equipped.

#### 5. 🏹 Hunter: "The Bullseye Reckoning"
* **Badge**: A playful cartoon dartboard / red suction-cup bullseye arrow stuck to the card corner.
* **Card Frame**: Coral amber dashed border (`border: 3px dashed #ff7f50`).
* **Motion**: The suction-cup arrow wobbles as if freshly landed (`spring-wiggle` keyframe).

---

## 4. Polished Card State Architecture

### A. Active Targetable Cards (`.selectable-target`)
Instead of ugly blurred glows:
```css
/* Tactile Cartoon Targetable Card */
.player-card.selectable-target {
    cursor: pointer;
    border: 3px dashed var(--role-accent-color, #ff4757) !important;
    background: #fffdf7 !important; /* Soft warm paper tone */
    box-shadow: 4px 4px 0px var(--text-dark) !important;
    transform: translateY(-2px);
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1),
                box-shadow 0.2s ease;
}

/* Playful Comic Hover */
.player-card.selectable-target:hover {
    transform: translateY(-6px) scale(1.04) rotate(-1.5deg);
    box-shadow: 6px 6px 0px var(--text-dark) !important;
    background: #ffffff !important;
}

/* Active Press */
.player-card.selectable-target:active {
    transform: translateY(0px) scale(0.98);
    box-shadow: 2px 2px 0px var(--text-dark) !important;
}
```

### B. Clean Non-Target Cards (`.non-target`)
Instead of turning them into ugly gray ghosts:
```css
.player-card.non-target {
    opacity: 0.65;
    transform: scale(0.96);
    filter: saturate(70%); /* Softly muted, but retains friendly color */
    pointer-events: none;
    transition: opacity 0.3s ease, transform 0.3s ease;
}
```
* Cards retain their crisp borders and cheerful avatar colors, but recede naturally into the background so the valid targets pop forward.

---

## 5. Lightweight Implementation Strategy

To keep the DOM clean without injecting dozens of HTML nodes:

1. **CSS Pseudo-Elements for Badges**:
   * Use `.player-card.selectable-target::after` for the comic badge sticker.
   * Store the role emoji / sticker in a CSS variable or content property:
     ```css
     .player-card.target-werewolf::after {
         content: '🐺';
         position: absolute;
         top: -8px;
         right: -6px;
         width: 28px;
         height: 28px;
         border-radius: 50%;
         background: #ff4757;
         border: 2px solid var(--text-dark);
         box-shadow: 2px 2px 0 var(--text-dark);
         display: flex;
         align-items: center;
         justify-content: center;
         font-size: 0.9rem;
         animation: stickerBounce 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
     }
     ```
2. **Zero Backend Changes**:
   * Uses existing `updatePlayerSelectableState(validTargets)` triggers.
   * Completely client-side and private to the human player's active turn.

---

## 6. Summary: Comparison

| Attribute | Previous Step 5 (Discarded) | Proposed Cartoon Pop Approach |
| :--- | :--- | :--- |
| **Silhouette** | Thin colored solid border | Chunky **dashed ink border** + warm paper fill |
| **Depth** | Blurry neon `box-shadow: 0 0 14px` | Hard comic drop-shadow (`4px 4px 0 #2d3436`) |
| **Identity** | Border color swap only | **Floating cartoon sticker badge** (`🐺`, `🧪`, `🔮`, `🛡️`) |
| **Motion** | Rigid linear pulse | **Springy comic wobble & tactile click depression** |
| **Inactive Cards** | 50% grayscale mud | Clean 65% opacity recession with crisp lines |
| **Cursor** | Sterile OS crosshair | Thematic pointer with friendly tactile feedback |
