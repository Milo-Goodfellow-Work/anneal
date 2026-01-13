import Spec.Program

namespace Verif

open Extract

theorem add_eq_add (a b : Nat) : add a b = a + b := by
  rfl

end Verif