import Spec.Prelude
import Spec.order_engine.Engine

namespace Spec.order_engine
namespace Tests

open Spec
open Spec.order_engine

private def parseU32Tok (tok : String) : U32 :=
  let cs := tok.toList
  if cs.isEmpty then
    (0 : U32)
  else
    let rec loop (cs : List Char) (acc : U32) : U32 :=
      match cs with
      | [] => acc
      | c :: cs' =>
        if ('0' ≤ c) && (c ≤ '9') then
          let d : U32 := (UInt32.ofNat (c.toNat - '0'.toNat))
          loop cs' (acc * (10 : U32) + d)
        else
          (0 : U32)
    loop cs (0 : U32)

private def parseSideTok (tok : String) : Side :=
  if tok = "B" then Side.SIDE_BUY else Side.SIDE_SELL

private structure St where
  e : Engine
  inited : Bool
  out : Array String

private def outPush (st : St) (s : String) : St :=
  { st with out := st.out.push s }

private def ensureInit (st : St) : St :=
  if st.inited then st else { st with e := init_engine, inited := true }

private def doInit (st : St) : St :=
  outPush { st with e := init_engine, inited := true } "OK\n"

private def doMatch (st : St) : St :=
  let st := ensureInit st
  let (e, logs) := match_orders st.e
  let out := logs.foldl (fun acc s => acc.push s) st.out
  let out := out.push "OK\n"
  { st with e := e, out := out }

private def doSubmit (st : St) (a1 a2 a3 a4 : String) : St :=
  let st := ensureInit st
  let e := submit_order st.e (parseU32Tok a1) (parseU32Tok a2) (parseU32Tok a3) (parseSideTok a4)
  outPush { st with e := e } "OK\n"

/--
Process the input as `harness.c` does:
- Read the input as a *byte stream*, split into lines on `\n`.
- Each line is tokenized on whitespace (`' '`, `\t`, `\r`, `\n`).

Important: unlike `String.splitOn "\n"`, we must preserve the possibility
that the final line does **not** end in `\n`. `String.splitOn` drops the final
empty segment when the string ends with the separator, which can change
observable behavior when the last line is empty.

We therefore implement a tiny newline splitter that matches the stream model.
-/
private def splitLinesPreserveFinal (s : String) : List String :=
  let cs := s.toList
  let rec go (cs : List Char) (cur : List Char) (acc : List String) : List String :=
    match cs with
    | [] =>
        -- finalize last line (possibly empty)
        (String.mk cur.reverse) :: acc |>.reverse
    | c :: cs' =>
        if c = '\n' then
          go cs' [] ((String.mk cur.reverse) :: acc)
        else
          go cs' (c :: cur) acc
  go cs [] []

def harnessMain : IO Unit := do
  let input ← (← IO.getStdin).readToEnd
  let mut st : St := { e := init_engine, inited := false, out := #[] }

  for line in splitLinesPreserveFinal input do
    let toks := (line.split (fun c => c = ' ' || c = '\t' || c = '\r' || c = '\n')).filter (fun s => !s.isEmpty)
    if toks.isEmpty then
      pure ()
    else
      match toks with
      | ["INIT"] =>
          st := doInit st
      | ["MATCH"] =>
          st := doMatch st
      | cmd :: a1 :: a2 :: a3 :: a4 :: _ =>
          if cmd = "SUBMIT" then
            st := doSubmit st a1 a2 a3 a4
          else
            st := outPush (ensureInit st) "ERR\n"
      | _ =>
          st := outPush (ensureInit st) "ERR\n"

  IO.print (String.join st.out.toList)

end Tests
end Spec.order_engine

def main : IO Unit := Spec.order_engine.Tests.harnessMain
