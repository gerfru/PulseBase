# PulseBase UX Structure

Status: Implemented-state baseline

This document is the structural source of truth for PulseBase screens, navigation,
tasks, and interface roles. Technical and visual implementation decisions remain in
[Design Decisions](design-decisions.md).

Statements about user frequency or preference are marked **To validate** because no
user research, analytics, or observed task data is currently available.

## Product Intent

PulseBase helps a signed-in user inspect personal health and fitness data, understand
how values change over time, and investigate the methodology behind derived metrics.
It also supports account, data-source, privacy, and optional seizure-diary workflows.

**To validate:** Checking the current daily state and investigating an unexpected
metric are assumed to be the highest-frequency tasks.

## Task Inventory

| Task | Intended outcome | Primary surface |
|---|---|---|
| Check daily state | Understand current readiness, capacity, and notable signals | Dashboard hero |
| Compare a period | View trends in a chosen window and move through history | Dashboard controls and charts |
| Investigate a metric | Open details, evidence, formula, and related values | Metric detail and formula dialog |
| Review training | Inspect recent activities and a selected activity | Dashboard and activity detail |
| Understand data maturity | Distinguish expected missing data from a failure | Onboarding and empty states |
| Review generated insights | Read a longer cross-metric analysis | Insights page and compact summaries |
| Maintain account and sources | Update profile, integrations, preferences, and data rights | Settings and link flows |
| Record seizure information | Review risk context and maintain a seizure diary | Epilepsy screen |
| Access compliance information | Read privacy, terms, imprint, and accessibility information | Global footer |

## Domain And Content Model

| Entity | Meaning | Main relationships |
|---|---|---|
| User | Account owner and data subject | Has settings, sources, metrics, activities, and insights |
| Data source | Garmin or Libre integration supplying personal observations | Belongs to a user; affects data availability |
| Daily status | Current summary of readiness, energy, vitals, and model states | Composed from metrics and insights |
| Metric | Measured or derived health or fitness value | Has history, evidence, formula, and related metrics |
| Period | Selected analysis window and historical offset | Filters dashboard and metric data |
| Activity | One training session and its records | Contributes to training metrics and has a detail screen |
| Insight | Automated cross-metric interpretation | References metrics and is not a medical finding |
| Seizure entry | User-recorded event for the optional diary | Exists only when epilepsy mode is enabled |
| Account setting | Profile, preference, integration, consent, or data-right control | Belongs to a user |

## Navigation Map

```text
Global main navigation
├── PulseBase / Dashboard
├── Seizure diary [only when epilepsy_mode is enabled]
├── Insights
├── Help and methodology
├── Settings
└── Sign out

Dashboard local navigation
├── Analysis window: 1W / 2W / 1M / 3M / 1Y
├── Section tabs: Training / History / Recovery
└── Historical period: previous / next

Global footer navigation
├── Privacy
├── Terms
├── Imprint
└── Accessibility
```

The seizure diary remains a conditionally visible global destination. Moving it into
another workflow requires user evidence; implementation convenience alone is not a
reason to change its ownership.

## Screen Inventory

| Screen group | Entry point | Primary task | Primary action | Visibility |
|---|---|---|---|---|
| Login, registration, verification, reset | Public routes and auth links | Gain or recover access | Submit account credentials | Public |
| Data-source linking | Dashboard notice or Settings | Connect or disconnect a source | Submit or revoke integration | Authenticated |
| Dashboard | Product identity link and successful login | Check status and trends | Select period or open a detail | Authenticated |
| Metric overview and detail | Dashboard metric links | Investigate one metric | Change period or inspect evidence | Authenticated |
| Activity detail | Recent activities | Review one training session | Record RPE or inspect charts/map | Authenticated, activity required |
| Insights | Global main navigation | Read cross-metric interpretation | Select presentation level or regenerate | Authenticated |
| Help and methodology | Global main navigation and metric links | Understand definitions and evidence | Search or open a topic | Authenticated |
| Settings | Global main navigation | Maintain account and sources | Save, link, export, or delete | Authenticated |
| Epilepsy | Conditional global destination | Review risk and maintain diary | Create or edit an entry | Authenticated, mode enabled |
| Legal and compliance | Global footer | Read mandatory information | Follow references or return | Public |

## Primary Flows

### First Useful Status

```text
Register or sign in
-> connect a data source
-> see data-maturity guidance
-> wait for observations to arrive
-> inspect daily status
-> open a metric detail
```

### Historical Investigation

```text
Open Dashboard
-> select an analysis window
-> move to a historical period when needed
-> choose Training, History, or Recovery
-> inspect a chart or activity
-> open its detail or methodology
```

### Account And Data Control

```text
Open Settings
-> update profile or preferences
-> manage Garmin or Libre integration
-> optionally enable epilepsy mode
-> export data or start account deletion when required
```

## Requirement To UI Traceability

| Requirement or constraint | User task | Screen | UI element |
|---|---|---|---|
| Current status must be scannable | Check daily state | Dashboard | Daily-status hero |
| Trends need comparable windows | Compare a period | Dashboard | Range control and period arrows |
| Dashboard density must remain manageable | Find relevant metrics | Dashboard | Training, History, and Recovery tabs |
| Derived values need explainability | Investigate a metric | Dashboard and metric detail | Linked metric surfaces and formula dialog |
| Training context needs drill-down | Review training | Dashboard and activity detail | Activity collection and detail charts |
| Data arrives gradually | Understand data maturity | Dashboard | Dismissible onboarding notice and empty states |
| Automated text is informational | Review generated insights | Dashboard and Insights | Insight surfaces and medical boundary text |
| Optional health workflows must not affect all users | Record seizure information | Dashboard and Epilepsy | Conditional navigation and diary controls |
| Account and source controls need one owner | Maintain account and sources | Settings | Form and status surfaces |
| Legal and accessibility information must remain reachable | Access compliance information | Global | Footer navigation and prose pages |

## Surface Roles

Every element using the shared `.card` base must have exactly one content role.

| Role | Use | Visual behavior |
|---|---|---|
| Hero | One highest-priority dashboard summary | Strongest hierarchy; short entrance motion allowed |
| Metric | A measured or derived value, usually with a chart | Restrained elevation; hover only when linked |
| Collection | A list or history whose rows provide the structure | Flatter than metric surfaces |
| Form | Data entry, authentication, or account controls | Quiet grouping; no entrance motion |
| Status | Current integration, risk, or compact state summary | Color only when it communicates state |
| Insight | Longer analytical interpretation | Reading-oriented spacing; no metric-tile treatment |

Long-form legal and compliance prose is not a card. It uses an unframed prose layout
with constrained measure and vertical rhythm.

## Motion Policy

Motion is a restrained surface and brand decision, not a carrier of health status.
The short `card-in` entrance is limited to the dashboard hero and metric surfaces to
orient the initial dashboard build. Form, status, collection, insight, and prose
surfaces do not receive automatic entrance motion.

All animations and transitions must honor `prefers-reduced-motion`; the final state
must remain complete and understandable without animation.

## Open Validation Questions

- Are daily-status checks and unexpected-metric investigations the most frequent tasks?
- Do compact dashboard insights and the dedicated Insights page have sufficiently distinct purposes?
- Is the seizure diary easiest to find in global navigation for users who enable it?
- Does entrance motion improve orientation, or is it merely decorative for regular users?
