---
name: web-design-guidelines
description: Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices".
metadata:
  author: vercel
  version: "1.0.0"
  argument-hint: <file-or-pattern>
---

# Web Interface Guidelines

Review files for compliance with Web Interface Guidelines.

## How It Works

1. Read the comprehensive rules in [references/web-interface-guidelines.md](./references/web-interface-guidelines.md)
2. Read the specified UI / frontend files in the project
3. Check against all rules in the guidelines (Accessibility, Focus States, Forms, Animation, Typography, Content Handling, Images, Performance, Navigation & State, Touch & Interaction, Safe Areas & Layout, Dark Mode & Theming, Locale & i18n, Hydration Safety, Hover & Interactive States, Content & Copy, and Anti-patterns)
4. Output findings in the terse `file:line` format

## Usage

When reviewing UI files:
1. Load guidelines from `./references/web-interface-guidelines.md`
2. Audit the frontend files (e.g. `app.py`, React, Vue, HTML, CSS components)
3. Check contrast, accessibility, responsiveness, dark mode, typography, and interactive states
4. Output actionable findings grouped by file
