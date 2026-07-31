# Content-policy architecture — neutral platform, operator-owned policy

Design principle: **design-beast is infrastructure, not an editor.** The platform does
not decide what users may create — the operator configures policy per deployment, users
choose backends that permit their content, and responsibility sits with the account
that made the request. Restriction is never hardcoded into the pipeline; it lives in
one explicit, swappable layer.

## Model/backend registry (the core mechanism)

Every backend (generator, judge, refiner, TTS, video) registers with:

```yaml
- id: grok-image            # example: user's paid xAI subscription
  kind: image
  hosting: cloud            # cloud | local
  license: provider-tos     # what the PROVIDER permits is the ceiling
  content_classes: [general, mature]   # per provider ToS — xAI permits "spicy"
  auth: user-supplied-key   # BYOK: the user's own subscription, their terms
- id: flux-local
  kind: image
  hosting: local
  license: <model license>
  content_classes: [general, mature]   # local = no provider policy server
- id: higgsfield
  content_classes: [general]           # ToS prohibits NSFW — router respects it
- id: qwen3-vl-judge
  kind: judge
  hosting: local
  content_classes: [general, mature]   # judge scores aesthetics, never gatekeeps
```

**Routing rule:** a request tagged with a content class is routed only to backends whose
registry entry covers it. A backend refusal is surfaced as `E_BACKEND_POLICY` with the
list of eligible alternates — never as a silent quality failure and never as a dead end
if any registered backend permits the class.

**Judge rule:** the judge's output is a score, not a verdict. If a judge model refuses
to process an image, that judge is unregistered for that content class and the router
uses one that doesn't (local judges via Ollama don't phone home). A refusal
masquerading as a low score corrupts the quality loop — treat it as a bug.

## Per-tenant policy (SaaS mode)

- Each tenant (operator of a deployment, or customer of the SaaS) gets a policy object:
  allowed content classes, allowed backends, BYOK slots for their own subscriptions
  (their Grok key runs under THEIR xAI agreement, not ours).
- Default tenant policy is operator-defined. The platform ships with no opinion beyond
  the legal floor below.
- All generations are attributed: tenant id, user id, backend, timestamp, prompt hash —
  provenance already exists (manifest.json); it also serves the responsibility model
  ("that will be on them" requires knowing who "them" is).

## The legal floor (non-configurable — law, not taste)

These are the only hard rules, and they exist because statutes and payment rails
impose them on every platform, neutral or not:

1. **Minors: absolute.** No sexual content involving minors, real or synthetic. CSAM
   detection on uploads (PhotoDNA-class hashing) is table stakes for any hosting.
2. **Real-person likeness requires consent.** Soul ID / face cloning + mature content
   is the NCII/deepfake danger zone — most US states, the UK (OSA), and the EU (AI Act)
   now criminalize non-consensual intimate imagery. Identity-cloning workflows require
   verified consent of the person cloned before mature classes unlock for that identity.
3. **Age verification for adult commerce.** Adult-content tenants must age-gate; this is
   processor-mandated (Visa/MC GBPP rules) and increasingly statute-mandated (US state
   AV laws, UK OSA).

Everything above the floor is tenant policy, not platform policy.

## Payments (the real gatekeeper for adult SaaS)

- Mainstream processors (Stripe, PayPal) prohibit adult content — an adult-permissive
  tier cannot bill through them. Options, in order of practicality:
  - **Crypto, self-hosted**: BTCPay Server (self-hosted, no middleman to say no,
    BTC/LN + altcoin plugins) — fits the neutral-infrastructure posture exactly and
    can be offered as an option for ANY tenant, not just adult ones.
  - **Adult-specialized processors**: CCBill, Segpay, Epoch — standard for the industry,
    higher fees (~10-15%), they impose the age/consent compliance themselves.
  - Coinbase Commerce et al. are hosted crypto — easier, but reintroduces a policy owner.
- Practical build order: BTCPay Server as the first payment integration (works for
  every tenant class, zero external policy), specialized processor later if fiat volume
  demands it.

## What this buys
- The user's paid Grok subscription plugs in as a BYOK backend doing exactly what xAI
  permits — no more, no less, and none of it design-beast's decision.
- A game studio tenant, a business-site tenant, and an adult-content tenant run on the
  same pipeline with different policy objects.
- No model refusal ever silently blocks the quality loop again.
- The compliance floor is small, explicit, and identical to what survives contact with
  processors, app stores, and courts — which is what makes the neutral posture durable.
