---
name: Nocturne Dining
colors:
  surface: '#121316'
  surface-dim: '#121316'
  surface-bright: '#38393c'
  surface-container-lowest: '#0d0e11'
  surface-container-low: '#1b1b1f'
  surface-container: '#1f1f23'
  surface-container-high: '#292a2d'
  surface-container-highest: '#343538'
  on-surface: '#e3e2e6'
  on-surface-variant: '#d4c4b0'
  inverse-surface: '#e3e2e6'
  inverse-on-surface: '#2f3034'
  outline: '#9d8f7c'
  outline-variant: '#504535'
  surface-tint: '#fabc4d'
  primary: '#ffc665'
  on-primary: '#432c00'
  primary-container: '#e5a93c'
  on-primary-container: '#5e4000'
  inverse-primary: '#7e5700'
  secondary: '#ffb95f'
  on-secondary: '#472a00'
  secondary-container: '#ee9800'
  on-secondary-container: '#5b3800'
  tertiary: '#afd2ff'
  on-tertiary: '#003258'
  tertiary-container: '#79b8fe'
  on-tertiary-container: '#00487b'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdead'
  primary-fixed-dim: '#fabc4d'
  on-primary-fixed: '#281900'
  on-primary-fixed-variant: '#604100'
  secondary-fixed: '#ffddb8'
  secondary-fixed-dim: '#ffb95f'
  on-secondary-fixed: '#2a1700'
  on-secondary-fixed-variant: '#653e00'
  tertiary-fixed: '#d1e4ff'
  tertiary-fixed-dim: '#9ecaff'
  on-tertiary-fixed: '#001d36'
  on-tertiary-fixed-variant: '#00497d'
  background: '#121316'
  on-background: '#e3e2e6'
  surface-variant: '#343538'
typography:
  display-lg:
    fontFamily: Newsreader
    fontSize: 48px
    fontWeight: '400'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Newsreader
    fontSize: 32px
    fontWeight: '400'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Newsreader
    fontSize: 32px
    fontWeight: '400'
    lineHeight: 40px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Newsreader
    fontSize: 26px
    fontWeight: '400'
    lineHeight: 34px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Newsreader
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  headline-sm:
    fontFamily: Newsreader
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
  label-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.02em
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.04em
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.06em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-sm: 1rem
  margin: 3rem
  margin-sm: 1.25rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

The design system embodies the sensory intimacy of candlelit hospitality, curated dining guides, and bespoke concierge services. Tailored for discerning diners, urban explorers, and gastronomy enthusiasts seeking tailored recommendations without the visual clutter of commercial review portals.

The visual style merges **Editorial Elegance** with **Restrained Modernism**:
- **Tone:** Quiet luxury, authoritative, discreet, and deeply tactile.
- **Atmosphere:** An ambient evening room. Dimmed baseline luminance, deliberate focal glows, and deliberate negative space emulate looking over a bespoke tasting menu under low pendant lights.
- **Imagery Rule:** Strictly typographic and spatial hierarchy. Zero stock food photography, cartoonish dish icons, or generic clip art. Trust is cultivated through pristine typography, micro-details, precision layout, and amber-illuminated cues.

## Colors

The palette reproduces the chromatic temperature of low-light dining: deep carbon foundations, warm-tinted dark charcoal surfaces, and candle-flame amber accents.

- **Background Canvas (`#121316`):** The foundational substrate across all viewports.
- **Surface Elevation 1 (`#1C1E24`):** Cards, panels, and floating navigation bars.
- **Surface Elevation 2 (`#242731`):** Hover states, nested lists, active inputs, and interactive surfaces.
- **Delicate Warm Border (`rgba(229, 169, 60, 0.12)` / `#2C2B28`):** Restrained separation lines with an undertone of raw brass.
- **Primary Accent (`#E5A93C` / `#F59E0B`):** Strictly governed. Reserved exclusively for primary conversion CTAs, star rating indicators, active state pill selectors, and verified badge insignias. It must never be applied to generic text or decorative borders.
- **Primary Typography (`#F3F4F6`):** High-legibility off-white with low glare.
- **Secondary & Muted Typography (`#9CA3AF`):** Muted warm slate for metadata, tags, and secondary narratives.

## Typography

The pairing creates intentional friction between classic culinary literature and sharp contemporary technology:

- **Editorial Headings (Newsreader):** Used for venue titles, narrative questions from the AI recommender, and curated collection headings. The font carries an organic, literary cadence that evokes private dining room menus and culinary journalism. Italicized cuts may be applied sparingly for neighborhood descriptors or cuisine subheadings.
- **System Interface (Plus Jakarta Sans):** Governs interface mechanics, metadata grids, filter tags, AI prompt suggestions, and navigational elements. Crisp, legible, and balanced against deep dark backgrounds without blooming.

## Layout & Spacing

The layout is structured around an airy fluid-grid philosophy that preserves intimate readability:

- **Max Content Width:** Constrained to `1200px` for discovery grids and `780px` for conversational recommendation streams and restaurant profiles, maintaining focused sightlines.
- **Desktop (>= 1024px):** 12-column layout with `margin: 3rem` and `gutter: 1.5rem`. Asymmetrical splits (e.g., 5-column conversational context pane, 7-column recommendation feed).
- **Tablet (768px - 1023px):** 8-column layout with `margin: 2rem` and `gutter: 1.25rem`.
- **Mobile (< 768px):** 4-column layout with `margin: 1.25rem` and `gutter: 1rem`. Full edge-to-edge interactive drawers with preserved top-and-bottom safe clearances.
- **Rhythm:** Generous card interiors (`space-lg` to `space-xl`) grant items room to breathe, eliminating the cramped density standard in utility aggregators.

## Elevation & Depth

Visual hierarchy uses tonal surface layering combined with faint ambient radiance rather than harsh physical drop shadows:

- **Base Layer (Canvas):** Pure `#121316`. No shadows or ambient lighting.
- **Level 1 (Card Surfaces):** Background `#1C1E24`, framed with a single 1px hairline border of `rgba(229, 169, 60, 0.12)`. Subtle diffused drop shadow: `0 8px 32px -4px rgba(0, 0, 0, 0.4)`.
- **Level 2 (Popovers, Active Focus, Overlays):** Background `#242731`, framed with `rgba(229, 169, 60, 0.24)`. Shadow: `0 16px 48px -8px rgba(0, 0, 0, 0.6)`.
- **Candlelight Glow (Hover & Selection):** When a recommendation card or budget toggle receives active selection, it gains an ambient underglow: `box-shadow: 0 0 24px 0 rgba(229, 169, 60, 0.08)`.

## Shapes

The geometric personality features softened structural rectangles balancing architectural precision with tactile warmth:

- **Standard Elements (Cards, Panels, Modals):** Formed at `16px` border radii (`rounded-lg`).
- **Interactive Controls (Inputs, Form Elements):** Defined at `12px` border radii (`rounded`).
- **Pills, Chips, and Badges:** Fully circular (`rounded-full` / 9999px) to contrast against structural card geometry.

## Components

### Buttons
- **Primary CTA:** Background `#E5A93C`, text color `#121316` (medium-weight bold for contrast compliance), border radius `12px`, padding `12px 24px`. Hover state shifts to `#F59E0B` with subtle ambient bloom.
- **Secondary CTA:** Background transparent, border `1px solid rgba(229, 169, 60, 0.25)`, text `#F3F4F6`. Hover triggers background `#1C1E24` and border color intensification to `rgba(229, 169, 60, 0.5)`.
- **Tertiary / Ghost:** No border or fill. Muted text `#9CA3AF`, shifting to `#F3F4F6` on interaction.

### Chips & Budget Selectors
- **Default State:** Pill shape (`rounded-full`), background `#1C1E24`, border `1px solid #2C2B28`, text `#9CA3AF`, padding `6px 16px`.
- **Active / Selected State (e.g., "$$$", "Intimate", "Late Night"):** Background `rgba(229, 169, 60, 0.1)`, border `1px solid #E5A93C`, text `#E5A93C`.

### Cards (Restaurant Recommendations)
- Background `#1C1E24`, border `1px solid rgba(229, 169, 60, 0.12)`, radius `16px`, padding `24px`.
- Card Header: Restaurant title in `headline-sm` (Newsreader, `#F3F4F6`), neighborhood and price level in `body-sm` (`#9CA3AF`).
- AI Match Rationale: Styled in a nested `#15161A` inset panel with subtle italicized secondary text highlighting dietary or vibe alignment.
- Rating Badge: Pill badge featuring amber star icon, numeric value in bold off-white, and review density in muted gray.

### Inputs & Conversational Prompts
- Background `#16171D`, border `1px solid #2C2B28`, border radius `12px`, padding `14px 18px`.
- Focus State: Border transitions to `#E5A93C` with an amber focus ring `0 0 0 1px #E5A93C`. Placeholder text `#4B5563`.

### Lists & Key-Value Details
- Divided by 1px rules colored `#242731`. Left-aligned semantic labels in `#9CA3AF`, right-aligned values in `#F3F4F6`.
- Distance/Transit Indicators: Monospaced numerical values using `Plus Jakarta Sans` with tight letter spacing for table alignment.