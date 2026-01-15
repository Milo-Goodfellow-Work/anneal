# Safety Case: `order_engine` (Lean translation hardening)

## Scope
This safety case argues that the Lean 4 translation in `spec/Spec/order_engine/*.lean` preserves the observable semantics of the reference C implementation in `examples/order_engine/*` **for the behaviors exercised by the differential harnesses**, and that the harness/test design is adequate and deterministic for safety-critical differential testing.

**Artefacts**
- Reference implementation: `examples/order_engine/engine.c`, `engine.h`, `main.c`
- Translation: `spec/Spec/order_engine/Engine.lean`, `Engine2.lean`, `Main.lean`
- Specifications/invariants: `spec/Spec/order_engine/Verif.lean`
- Differential testing:
  - C harness: `spec/tests/harness.c`
  - Lean harness: `spec/Spec/tests/Harness.lean`
  - Generator: `spec/tests/gen_inputs.py`

## Explicit claims

### C1. Translation correctness (observational equivalence under harness)
**Claim.** For any generator-produced input case, the Lean harness output matches the C harness output exactly.

**Argument.**
- The harness protocol reduces the engine to a deterministic state machine with visible outputs only via:
  - engine match logs (from `match_orders`), and
  - an `OK\n`/`ERR\n` line per processed command.
- Therefore, equivalence requires (1) identical parsing/dispatch/initialization policy and (2) identical engine semantics.

**Evidence.** See “Differential testing evidence” below; all runs passed with exact stdout equality.

### C2. Test adequacy (exercise of safety-relevant behaviors)
**Claim.** The generator/harness suite exercises safety-relevant corner cases beyond naïve random testing.

**Argument.** `spec/tests/gen_inputs.py` mixes random operations with targeted adversarial sequences:
- **Structural stress:** monotone price ladders (both sides) + repeated `MATCH` draining.
- **Reset/initialization:** explicit `INIT` mid-stream plus implicit init on first non-INIT (matching C harness behavior).
- **Value extremes:** includes `{0, 1, small values, U32_MAX}` for id/price/qty and random 32-bit values.
- **Robustness to malformed input:** malformed lines and unexpected commands (must deterministically yield `ERR`).
- **Tokenizer stress:** variable whitespace plus occasional `\r`.

The generator is constrained to avoid unbounded outputs (important for determinism and reliable comparison): ladder sizes and `MATCH` repetitions are capped.

**Evidence.** Differential run counts and seeds (below) confirm this corpus was executed end-to-end.

### C3. Harness determinism
**Claim.** Both harnesses are deterministic functions of stdin.

**Argument.**
- C harness: `fgets` + `strtok_r` with fixed delimiter set; outputs only `OK\n`/`ERR\n` plus engine logs produced deterministically by `match_orders`.
- Lean harness:
  - reads stdin fully,
  - splits into lines using a custom `splitLinesPreserveFinal` routine (to match stream semantics, including missing final newline),
  - tokenizes on the same whitespace class (`' '`, `\t`, `\r`, `\n`),
  - applies identical command dispatch and implicit initialization.
- Neither harness consults time, global randomness, or concurrency.

**Evidence.** All differential runs were reproducible by seed; the runner verified exact equality.

### C4. Spec relevance
**Claim.** The spec module `Verif.lean` states invariants aligned with the engine’s core safety hazards.

**Argument.** The engine simulates pointer-rich structures using array indices (`Nat` indices into `order_pool`/`level_pool`). The most safety-critical failure modes are:
- out-of-bounds indices (memory safety),
- inconsistent free-list counters leading to invalid allocation/deallocation,
- malformed link structures.

`Verif.lean` defines invariants directly over the translated state:
- `PoolsSized` and `FreeCountsInRange` (bounds/capacity safety)
- link-range predicates for orders and levels

These are the right *shapes* of properties to later prove preservation and to support runtime invariant checking.

## Differential testing evidence (concrete)
The runner was executed after hardening changes.

**Result:** `status = success`

**Runs:** 5/5 passed.

**Seeds and case counts (from runner JSON):**
- seed=1: cases=410
- seed=2: cases=496
- seed=3: cases=412
- seed=4: cases=420
- seed=5: cases=412

Total executed cases across runs: **2150**.

## Identified weaknesses/risks and mitigations

### R1. Line splitting mismatch (final newline / CRLF)
**Risk.** The initial Lean harness used `String.splitOn "\n"`, which *drops* the trailing empty segment when the input ends with `\n`. C’s `fgets` stream semantics can distinguish some of these cases.

**Mitigation performed.** Implemented `splitLinesPreserveFinal` in `spec/Spec/tests/Harness.lean` and tokenized on `' '`, `\t`, `\r`, `\n` to align with the C harness delimiter behavior.

### R2. Test-output blowup masking real mismatches
**Risk.** Large ladders and excessive `MATCH` can emit enormous match logs, increasing runtime/memory and making failures harder to diagnose.

**Mitigation performed.** Tightened generator to keep targeted sequences modest (12+12 ladder and bounded `MATCH` calls) while still stressing structural mutation.

### R3. Under-testing of adversarial sequences
**Risk.** Pure random mixes might fail to generate degenerate book shapes, drains, and ID collision patterns.

**Mitigation performed.** Added explicit targeted subsequences (ladders, drains, collisions, malformed commands) in `spec/tests/gen_inputs.py`.

### R4. Spec is not yet proven
**Risk.** `Verif.lean` currently provides invariants but does not (yet) prove they hold for all reachable states.

**Mitigation plan.**
1. Add executable invariant checkers in Lean (and optionally mirror in C harness) to fail fast on invariant violations during testing.
2. Prove preservation lemmas for `init_engine`, `submit_order`, and `match_orders` with respect to `EngineSafe` / link-range properties.

## Conclusion
- The harnesses are deterministic and now aligned on stream/tokenization edge cases.
- The generator provides both random and adversarial coverage while keeping outputs bounded.
- Differential testing provides concrete empirical evidence of equivalence: **5 seeds, 2150 cases total, all passing**.

This supports high confidence that the Lean translation matches the C behavior for the exercised operational envelope, with a clear plan to further raise assurance via invariant checking and proofs.
