import Aeneas
import Spec.Extract

open Aeneas.Std Result Error
open Extract

namespace GemSpec

/-- Specification for the `add` function on the concrete inputs used by `main`. -/
@[simp] theorem add_fifteen :
    Extract.add 5#i32 10#i32 = ok 15#i32 := by
  sorry

/-- The `main` function should succeed and return `()` when `add` is called on `5` and `10`. -/
@[simp] theorem main_ok :
    Extract.main = ok () := by
  sorry

end GemSpec
