/-
This file was edited by Aristotle.

Lean version: leanprover/lean4:v4.24.0
Mathlib version: f897ebcf72cd16f89ab4577d0c826cd14afaafc7
This project request had uuid: 14b492c4-7852-4f5b-90fa-4506d3bc4d6c

The following was proved by Aristotle:

- theorem add_eq_checked (a b : I32) :
    Extract.add a b = a + b

- theorem add_ok_of_inRange {a b : I32}
    (hmin : (I32.min : Int) ≤ a.val + b.val)
    (hmax : a.val + b.val ≤ (I32.max : Int)) :
    ∃ c, Extract.add a b = ok c ∧ (c.val : Int) = a.val + b.val

- theorem add_fail_of_outOfRange {a b : I32}
    (hOverflow : ¬ ((I32.min : Int) ≤ a.val + b.val ∧ a.val + b.val ≤ (I32.max : Int))) :
    Extract.add a b = fail integerOverflow

- theorem main_returns_ok :
    Extract.main = ok ()
-/

import Aeneas
import Spec.Extract


open Aeneas.Std Result Error

open Extract

namespace Verif

/--
`Extract.add` is exactly the checked addition provided by the `I32` instance over the `Result`
monad.
-/
theorem add_eq_checked (a b : I32) :
    Extract.add a b = a + b := by
  rfl

/--
If the mathematical sum of `a` and `b` stays inside the signed 32-bit bounds, the checked addition
succeeds and returns the unique `I32` whose value equals that sum.
-/
theorem add_ok_of_inRange {a b : I32}
    (hmin : (I32.min : Int) ≤ a.val + b.val)
    (hmax : a.val + b.val ≤ (I32.max : Int)) :
    ∃ c, Extract.add a b = ok c ∧ (c.val : Int) = a.val + b.val := by
  exact?

/--
Whenever the mathematical sum of `a` and `b` leaves the signed 32-bit range, the checked addition
fails with `integerOverflow`.
-/
theorem add_fail_of_outOfRange {a b : I32}
    (hOverflow : ¬ ((I32.min : Int) ≤ a.val + b.val ∧ a.val + b.val ≤ (I32.max : Int))) :
    Extract.add a b = fail integerOverflow := by
  -- By definition of `tryMk`, if the sum of `a` and `b` is out of bounds, it returns `fail integerOverflow`.
  have h_tryMk : Aeneas.Std.IScalar.tryMk .I32 (a.val + b.val) = Aeneas.Std.Result.fail Aeneas.Std.Error.integerOverflow := by
    -- By definition of `tryMk`, if the sum is out of bounds, it returns `fail integerOverflow`. Therefore, we can conclude the proof.
    simp [Aeneas.Std.IScalar.tryMk, Aeneas.Std.IScalar.tryMkOpt];
    split_ifs <;> simp_all +decide [ Aeneas.Std.I32.min, Aeneas.Std.I32.max ];
    exact not_le_of_gt ( hOverflow ( by norm_num [ Aeneas.Std.I32.numBits ] at *; linarith ) ) ( by norm_num [ Aeneas.Std.I32.numBits ] at *; linarith );
  exact?

/--
`main` invokes `add` on `5` and `10`. Their sum stays within bounds, so the entire computation
returns `ok ()`.
-/
theorem main_returns_ok :
    Extract.main = ok () := by
  unfold Extract.main;
  unfold Extract.add; aesop;

end Verif