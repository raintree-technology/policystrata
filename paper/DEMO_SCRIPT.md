# PolicyStrata Narrated Demo

This is the replacement script for the short silent demo referenced by reviews 38A-38C. The
generated recording is about 3 minutes 25 seconds and includes narration plus an English caption
track.

Build the captioned narrated MP4 with:

```bash
bun run paper:demo-video
```

The output is `paper/build/PolicyStrata-demo.mp4`. The storyboard covers the synthetic CLI
walkthrough, the source-frozen MetricFlow result, the BetterOff production pilot, and the remaining
claim boundary. `paper/build/PolicyStrata-demo.json` records its duration and checksum.

## Recording setup

Start from a clean checkout with PolicyStrata installed. Increase terminal text size enough for the
JSON witness to remain readable after video compression.

```bash
demo_dir="$(mktemp -d /tmp/policystrata-demo.XXXXXX)"
policystrata demo --out "$demo_dir"
```

Do not describe the demo as a production-security evaluation. It uses the built-in synthetic
`support_saas` domain.

## Shot and narration plan

### 0:00-0:25 - The problem

Show the policy-pipeline diagram from the paper.

Narration:

> A data agent repeats policy across six different surfaces: what the model can see, what plans are
> syntactically valid, what the validator authorizes, how the compiler lowers a plan to SQL, what
> the database contains, and what the application releases. Policy drift occurs when one transition
> stops preserving an obligation even though each component still appears locally healthy.

### 0:25-0:55 - Run the deterministic suite

Run:

```bash
policystrata demo --out "$demo_dir"
```

Narration:

> This command runs 50 deterministic seeded cases without an LLM API key. The totals are regression
> coverage over named injected faults, not an estimate of production recall. The useful output is
> the worked example below the totals.

### 0:55-1:45 - Follow the worked example

Pause on the `Worked example: stale tenant-key lowering` block.

Narration:

> The principal is an analyst scoped to one tenant. The canonical policy, manifest, grammar,
> validator, database, and release layer are version 7, but the compiler is version 5. The canonical
> semantic query is allowed. During lowering, the stale compiler binds tenant scope to
> `legacy_tenant_id` instead of `tenant_id`. PolicyStrata evaluates contracts in pipeline order and
> reports the compiler as the first violated transition.

### 1:45-2:20 - Explain containment

Point to the distinguishing values, containment, and release lines.

Narration:

> The generated state distinguishes the canonical value from the stale lowering. Database row-level
> security then blocks the result, so no release occurs. That does not erase the compiler defect.
> The witness records both the upstream violation and the downstream containment. A final-answer
> assertion would see only that nothing leaked and would miss the regression.

### 2:20-2:55 - Open the witness

Run:

```bash
python -m json.tool \
  "$demo_dir/witnesses/compiler_uses_old_tenant_key_01.json" | sed -n '1,180p'
```

Narration:

> The witness contains the semantic IR, surface versions, declared responsibilities, failed contract,
> lowered SQL, database outcome, release decision, and reasons. The reducer may remove dimensions,
> filters, or a non-default limit when replay preserves the same class, location, containment, and
> release outcome. It does not claim globally minimal SQL or source code.

### 2:55-3:20 - Explain retargeting

Show `examples/brownfield/midday/policystrata.yaml` and one trace record.

Narration:

> Retargeting requires a canonical policy, surface contracts, representative traces, and explicit
> mappings for the target's identity and tenancy vocabulary. Missing surfaces remain unobserved.
> MetricFlow supplies independently authored expected-SQL cases, while Raintree supplies the policy
> adapter. BetterOff supplies deployment-linked evidence for the exact revision running in
> production.

### 3:20-3:30 - Close with the evidence boundary

Narration:

> PolicyStrata is a regression tester and diagnostic tool. It does not replace application
> authorization, database policy, or an independently reviewed canonical specification.

## Publication checklist

- Include narration and an English caption track.
- Link the exact release and paper revision used for the recording.
- Show the synthetic-fixture disclaimer on screen.
- Keep the command output visible long enough to read.
- Verify the witness path and example ID against the current CLI before publishing.
