---
task: Deep research on accessing real 3DS enrollment data
slug: 20260319-120000_3ds-enrollment-data-research
effort: extended
phase: complete
progress: 18/18
mode: interactive
started: 2026-03-19T12:00:00-05:00
updated: 2026-03-19T12:08:00-05:00
---

## Context

The Bin-Intelligence platform currently guesses 3DS support using heuristics (country + brand = probably has 3DS). This is unreliable. The user needs comprehensive research on how to access ACTUAL 3DS enrollment data for BINs from authoritative sources: card scheme directory servers, PSP APIs, 3DS server vendors, and published BIN range programs.

### Risks
- Directory Server access is gated behind acquirer/issuer licensing -- may not be accessible to independent operators
- PSP APIs may only expose 3DS data within payment flow, not as standalone BIN lookup
- Cost and compliance barriers (PCI 3DS, EMVCo certification) may be prohibitive
- Data freshness varies by source -- cached ranges vs real-time enrollment checks

## Criteria

- [x] ISC-1: Visa Directory Server access requirements documented with specifics
- [x] ISC-2: Visa Directory Server data fields and response format described
- [x] ISC-3: Mastercard Directory Server enrollment process documented
- [x] ISC-4: Mastercard ISSM tool and BIN registration workflow described
- [x] ISC-5: EMVCo 3DS protocol roles identified for directory server queries
- [x] ISC-6: EMVCo PReq/PRes card range mechanism explained
- [x] ISC-7: PCI 3DS compliance requirements and cost barriers outlined
- [x] ISC-8: Stripe 3DS data availability via API documented
- [x] ISC-9: Adyen BinLookup get3dsAvailability endpoint documented
- [x] ISC-10: Checkout.com 3DS enrollment data availability documented
- [x] ISC-11: Mastercard MPGS Check 3DS Enrollment API documented
- [x] ISC-12: Netcetera 3DS Server card range capabilities described
- [x] ISC-13: GPayments ActiveServer BIN range caching described
- [x] ISC-14: Basis Theory and other third-party 3DS services cataloged
- [x] ISC-15: 3dslookup.com and similar public services evaluated
- [x] ISC-16: Card scheme published BIN range list availability assessed
- [x] ISC-17: Feasibility matrix comparing all sources by access and reliability
- [x] ISC-18: Strategic recommendation for Bin-Intelligence integration path

## Decisions

Research-only task -- no code changes. Output is a comprehensive report organized by source type. Adyen BinLookup API identified as optimal integration path.

## Verification

All 18 criteria verified against the research report at `3DS-Enrollment-Data-Research.md`. Each section provides data available, access method, cost/requirements, and reliability assessment. Feasibility matrix and strategic recommendation included.
