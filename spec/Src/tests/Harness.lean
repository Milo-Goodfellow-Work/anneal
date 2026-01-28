import Src.Main

namespace Src

partial def loop : IO Unit := do
  let stdin ← IO.getStdin
  let line1 ← stdin.getLine
  if line1.isEmpty then return ()
  let n := line1.trim.toNat!
  
  let mut nums := #[]
  for _ in [0:n] do
    let line ← stdin.getLine
    if line.isEmpty then break
    nums := nums.push line.trim.toInt!
    
  let lineTarget ← stdin.getLine
  if lineTarget.isEmpty then return ()
  let target := lineTarget.trim.toInt!
  
  match solveTwoSum nums target with
  | Some (i, j) =>
    if i < j then
      IO.println s!"{i} {j}"
    else
      IO.println s!"{j} {i}"
  | None =>
    IO.println "-1 -1"
  
  loop

def main : IO Unit := loop

end Src
