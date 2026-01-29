import Src.Prelude

namespace Src

partial def readLines (acc : List String) : IO (List String) := do
  let stdin ← IO.getStdin
  let line ← stdin.getLine
  if line.isEmpty then return acc.reverse
  else readLines (line.trim :: acc)

def main : IO Unit := do
  let lines ← readLines []
  for line in lines do
    if line == "NOOP" then IO.println "OK"
    else IO.println "ERR"

end Src
