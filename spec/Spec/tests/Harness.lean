import Spec.Prelude
import Spec.test_project.Main

namespace Spec.test_project

partial def loop (c : Counter) : IO Unit := do
  let stdin ← IO.getStdin
  let line ← stdin.getLine
  if line.isEmpty then
    pure ()
  else
    let op := line.trim
    if op == "inc" then
      loop (increment c)
    else if op == "get" then
      IO.println (get c)
      loop c
    else
      loop c

def main : IO Unit := loop init

end Spec.test_project
