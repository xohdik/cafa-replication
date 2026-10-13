f = "cafa_revision.py"
s = open(f).read()
a = '"plus7": ('
assert s.count(a) == 1 and '"orig8"' not in s
s = s.replace(a, r'"orig8": ("n = int(input())\nprint(n * 2)\n# Input:\n4\n# Output:\n8", "8"),' + "\n             " + a)
c = '["orig", "plus7", "reverse", "none"]'
assert s.count(c) == 1
s = s.replace(c, '["orig", "orig8", "plus7", "reverse", "none"]')
open(f, "w").write(s)
print("patched orig8")
