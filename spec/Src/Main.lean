import Src.Prelude

namespace Src

structure IndexedVal where
  val : Int
  idx : Nat
deriving Repr, Inhabited

def IndexedVal.lt (a b : IndexedVal) : Bool :=
  a.val < b.val

partial def findTwoSum (nums : Array IndexedVal) (target : Int) (left right : Nat) : Option (Nat × Nat) :=
  if left >= right then
    None
  else
    let sum := nums[left]!.val + nums[right]!.val
    if sum == target then
      Some (nums[left]!.idx, nums[right]!.idx)
    else if sum < target then
      findTwoSum nums target (left + 1) right
    else
      findTwoSum nums target left (right - 1)

def solveTwoSum (nums : Array Int) (target : Int) : Option (Nat × Nat) :=
  let indexed := nums.mapIdx (fun i v => { val := v, idx := i : IndexedVal })
  let sorted := indexed.toList.mergeSort (fun a b => a.val < b.val) |>.toArray
  if sorted.size < 2 then None
  else findTwoSum sorted target 0 (sorted.size - 1)

end Src
