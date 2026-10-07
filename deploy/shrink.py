"""Shrink a contract so its deploy tx fits under Testnet Bradbury's per-tx gas cap (~20 KB of code).

    python deploy/shrink.py contracts/x.py build/x.py          # strip docstrings/comments, 1-space indent
    python deploy/shrink.py contracts/x.py build/x.py --pack   # ...then zlib+base85 self-extracting stub

The first line (`# { "Depends": ... }`) is kept verbatim. The output's AST is asserted
equal to the source's (minus docstrings), and --pack asserts a lossless round-trip.
Run the direct tests against the output before deploying it.
"""

import ast
import base64
import re
import sys
import zlib


def _strip_docstrings(tree):
    for n in ast.walk(tree):
        b = getattr(n, "body", None)
        if (
            isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and b
            and isinstance(b[0], ast.Expr)
            and isinstance(b[0].value, ast.Constant)
            and isinstance(b[0].value.value, str)
        ):
            n.body = b[1:] or [ast.Pass()]
    return tree


def shrink(src: str, pack: bool = False) -> str:
    src = src.replace("\r\n", "\n")
    header, _ = src.split("\n", 1)
    assert header.startswith('# { "Depends"'), "first line must be the Depends header"
    body = ast.unparse(_strip_docstrings(ast.parse(src)))
    body = "\n".join(
        re.sub(r"^((?:    )+)", lambda m: " " * (len(m.group(1)) // 4), line) for line in body.split("\n")
    )
    assert ast.dump(_strip_docstrings(ast.parse(src))) == ast.dump(ast.parse(body)), "AST mismatch"
    if not pack:
        return f"{header}\n{body}\n"
    body += "\n"
    blob = base64.b85encode(zlib.compress(body.encode(), 9)).decode()
    assert zlib.decompress(base64.b85decode(blob)).decode() == body
    return f"{header}\nimport zlib,base64\nexec(zlib.decompress(base64.b85decode({blob!r})).decode())\n"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src = open(sys.argv[1], encoding="utf-8").read()
    out = shrink(src, pack="--pack" in sys.argv)
    open(sys.argv[2], "w", encoding="utf-8", newline="\n").write(out)
    print(f"{sys.argv[2]}: {len(src.encode())} -> {len(out.encode())} bytes")
