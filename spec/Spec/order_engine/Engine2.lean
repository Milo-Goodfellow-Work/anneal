import Spec.Prelude
import Spec.order_engine.Engine

/-!
Translation of `engine.h` into Lean declarations.

The C header `engine.h` provides constants, type declarations, and function
prototypes for the matching engine.

In this repository, the translated definitions and executable semantics live in
`Spec.order_engine.Engine` (translation of `engine.c`).

This module corresponds to the header role: it *re-exports* the API surface.

Important: `Spec.order_engine.Engine` already defines these names in the
`Spec.order_engine` namespace. Attempting to `abbrev`-alias them here causes
name clashes.

Therefore this file is intentionally thin: it only imports `Spec.Prelude` and
`Spec.order_engine.Engine`, and provides no additional declarations.
-/

namespace Spec.order_engine

open Spec

end Spec.order_engine
