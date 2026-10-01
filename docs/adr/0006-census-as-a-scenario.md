# 6. The census (check every licensed location) is analyzed as a scenario, not adopted

Status: accepted (2026-09-30); amended by [ADR 0007](0007-two-implementations-one-regime.md) (2026-10-01): the evidence and the "default plan unchanged" guidance stand, the framing becomes two implementations of one regime and the next step becomes a staged learning pilot

## Context
The team asked what it would mean to check every distinct licensed location in a year, and whether that captures more than absolute random sampling.
At 345 distinct retail locations the work is small (about 28 team-days) and cheap in marginal terms (about $27,000 in the base case).

## Decision
Keep the census as a documented scenario (`tobacco-inspect census`, notebook 03, memo 04), separate from the recommended pipeline. Do not change the default
budget or the monthly targeted plan on its strength.

## Why
- A single undercover purchase is a coin flip with probability p_i. At equal numbers of checks a census detects the same violations per check as any random scheme and
  fewer than model targeting. Its edge over "absolute" random draws (about 14% more distinct violators) disappears against simple random sampling without repeats.
- What a census uniquely provides is coverage of every store (including the riskiest), a precise city base rate (standard error about 2.3 points vs 4.4 for Synar's n = 100),
  and a first unselected label for the roughly half of stores never inspected. Those are measurement and legitimacy benefits, not violations per dollar.
- Cost inputs are largely assumed; funding and authority (FDA contract targets) are unresolved.

## Consequences
- A one-time census or stratified half-census to learn the base rate and label all stores, followed by a return to the targeted randomized list, is the option worth testing.
- Revisit if DOH confirms the funding path, purchaser availability and actual unit costs.
