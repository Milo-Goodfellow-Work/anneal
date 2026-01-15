import Spec.Prelude
import Spec.order_engine.Engine

/-!
Translation of `engine.h` into Lean declarations.

`engine.h` is a header-only API/type description. The executable semantics and
all concrete type definitions are provided by `Spec.order_engine.Engine`
(translation of `engine.c`).

Lean's `export` command cannot re-export from the *current* namespace
(`Spec.order_engine`) into itself (it is a self-export).  The declarations
already live in `Spec.order_engine` via the imported module, so this file simply
provides the header-level module without redeclaring or re-exporting anything.
-/

namespace Spec.order_engine

open Spec

-- All declarations corresponding to `engine.h` are defined in
-- `Spec.order_engine.Engine` and are available in this namespace after import.

end Spec.order_engine
