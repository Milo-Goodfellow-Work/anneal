import Spec.Prelude
import Spec.generated.Main

namespace Spec.generated

open Arena

partial def loop (stdin : IO.FS.Stream) (stdout : IO.FS.Stream) (arena : Arena.State) : IO Unit := do
  let line ← stdin.getLine
  if line.isEmpty then return ()
  
  let trimmed := line.trim
  if trimmed == "" then 
      if line.length == 0 then return () else loop stdin stdout arena

  let parts := trimmed.splitOn " "
  match parts with
  | ["init", capStr] =>
    if let some cap := capStr.toNat? then
      stdout.putStrLn "init ok"
      loop stdin stdout (Arena.init cap)
    else
      stdout.putStrLn "error parsing capacity"
      loop stdin stdout arena
      
  | ["alloc", sizeStr] =>
    if let some size := sizeStr.toNat? then
      let (newArena, res) := Arena.alloc arena size
      match res with
      | some offset => stdout.putStrLn s!"alloc {offset}"
      | none => stdout.putStrLn "alloc fail"
      loop stdin stdout newArena
    else
      stdout.putStrLn "error parsing size"
      loop stdin stdout arena

  | ["getpos"] =>
    let pos := Arena.getPos arena
    stdout.putStrLn s!"pos {pos}"
    loop stdin stdout arena

  | ["setpos", posStr] =>
    if let some pos := posStr.toNat? then
      let newArena := Arena.setPos arena pos
      stdout.putStrLn "setpos ok"
      loop stdin stdout newArena
    else
      stdout.putStrLn "error parsing pos"
      loop stdin stdout arena

  | ["reset"] =>
    let newArena := Arena.reset arena
    stdout.putStrLn "reset ok"
    loop stdin stdout newArena

  | _ => 
    stdout.putStrLn s!"unknown command: {trimmed}"
    loop stdin stdout arena

def main : IO Unit := do
  let stdin ← IO.getStdin
  let stdout ← IO.getStdout
  loop stdin stdout (Arena.init 0)

end Spec.generated

def main := Spec.generated.main
