import Spec.Prelude

namespace Spec.generated

structure IndexedValue where
  value : Int
  index : Int
  deriving Inhabited

def IndexedValue.lt (a b : IndexedValue) : Bool :=
  if a.value < b.value then true
  else if a.value > b.value then false
  else a.index < b.index

structure TwoSumResult where
  index1 : Int
  index2 : Int
  deriving Repr, BEq

def solveTwoSum (nums : Array Int) (target : Int) : TwoSumResult :=
  let indexed := nums.mapIdx (fun i v => { value := v, index := (i : Int) : IndexedValue })
  let sorted := indexed.qsort IndexedValue.lt
  let rec loop (l r : Nat) : TwoSumResult :=
    if h : l < r then
      let leftVal := sorted.get! l
      let rightVal := sorted.get! r
      let sum := leftVal.value + rightVal.value
      if sum == target then
        if leftVal.index < rightVal.index then
          { index1 := leftVal.index, index2 := rightVal.index }
        else
          { index1 := rightVal.index, index2 := leftVal.index }
      else if sum < target then
        loop (l + 1) r
      else
        loop l (r - 1)
    else
      { index1 := -1, index2 := -1 }
  if sorted.size < 2 then
    { index1 := -1, index2 := -1 }
  else
    loop 0 (sorted.size - 1)

end Spec.generated
