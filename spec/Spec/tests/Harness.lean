import Spec.Prelude
import Spec.generated.Main

namespace Spec.generated

def main : IO Unit := do
  let stdin ← IO.getStdin
  
  -- Read N and target
  let line1 ← stdin.getLine
  if line1.isEmpty then return
  let parts1 := line1.trim.splitOn " " |>.filter (fun s => !s.isEmpty)
  if parts1.length < 2 then return
  let _n := parts1.get! 0 |>.toInt!
  let target := parts1.get! 1 |>.toInt!
  
  -- Read nums
  let line2 ← stdin.getLine
  if line2.isEmpty then return
  let nums := line2.trim.splitOn " " |>.filter (fun s => !s.isEmpty) |>.map String.toInt! |>.toArray
  
  let result := solveTwoSum nums target
  IO.println s!"{result.index1} {result.index2}"

end Spec.generated
