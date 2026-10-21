"""Package-level import graph of shiftlink/ (D9 evidence). Usage: python imports.py <path to shiftlink package>"""
import ast
import collections
import os
import sys

root = sys.argv[1]
edges, sizes = collections.Counter(), collections.Counter()
for dp, _, fs in os.walk(root):
    for f in fs:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        pkg = os.path.relpath(p, root).split(os.sep)[0].removesuffix(".py")
        src = open(p, encoding="utf-8").read()
        sizes[pkg] += src.count("\n")
        for n in ast.walk(ast.parse(src)):
            mods = []
            if isinstance(n, ast.ImportFrom):
                if n.level >= 2 and n.module:
                    mods = [n.module.split(".")[0]]
                elif n.level == 0 and n.module and n.module.startswith("shiftlink."):
                    mods = [n.module.split(".")[1]]
            elif isinstance(n, ast.Import):
                mods = [a.name.split(".")[1] for a in n.names if a.name.startswith("shiftlink.")]
            for m in mods:
                if m != pkg:
                    edges[(pkg, m)] += 1
print(dict(sizes))
for (a, b), c in sorted(edges.items()):
    print(a, "->", b, c)
