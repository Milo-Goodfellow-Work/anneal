import Spec.Prelude

namespace Spec.test_project

structure Counter where
  value : UInt32
deriving Repr, Inhabited

def init : Counter :=
  { value := 0 }

def increment (c : Counter) : Counter :=
  { value := c.value + 1 }

def get (c : Counter) : UInt32 :=
  c.value

end Spec.test_project
