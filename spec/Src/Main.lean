import Src.Prelude

namespace Src

def twoSum (nums : Array Int) (target : Int) : Option (Nat × Nat) :=
  let indexed := nums.mapIdx (fun i v => (v, i))
  let sorted := indexed.qsort (fun a b => if a.1 == b.1 then a.2 < b.2 else a.1 < b.1)
  let rec find (i j : Nat) : Option (Nat × Nat) :=
    if h : i < j then
      let left := sorted[i]!
      let right := sorted[j]!
      let sum := left.1 + right.1
      if sum == target then
        let res := if left.2 < right.2 then (left.2, right.2) else (right.2, left.2)
        Some res
      else if sum < target then
        find (i + 1) j
      else
        find i (j - 1)
    else
      None
  if sorted.size < 2 then None
  else find 0 (sorted.size - 1)

def main : IO Unit := do
  let stdin ← IO.getStdin
  let line1 ← stdin.getLine
  if line1.isEmpty then return
  let n := line1.trim.toNat!
  let mut nums := #[]
  for _ in [:n] do
    let valStr ← stdin.getLine
    nums := nums.push valStr.trim.toInt!
  let targetStr ← stdin.getLine
  if targetStr.isEmpty then return
  let target := targetStr.trim.toInt!
  match twoSum nums target with
  | some (i, j) => IO.println s!"{i} {j}"
  | none => IO.println "notfound"

end Src
