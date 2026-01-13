namespace Extract

def add (a b : Nat) : Nat :=
  a + b

def main : IO Unit := do
  IO.println s!"5 + 10 = {add 5 10}"

end Extract
