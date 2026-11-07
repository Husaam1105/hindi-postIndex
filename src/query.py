"""
Small command line tool to look things up in the index.

    python src/query.py                 -> interactive
    python src/query.py भारत            -> single term: df, cf and postings
    python src/query.py "भारत का संविधान" -> more than one word = phrase query
"""

import sys
from index_reader import PositionalIndex

SHOW_DOCS = 10


def show_term(idx, term):
    r = idx.lookup(term)
    if r is None:
        print(f"'{term}' is not in the vocabulary (stopword or never seen)")
        return
    df, cf, postings = r
    print(f"term: {term}   df = {df}   cf = {cf}")
    for d, pos in list(postings.items())[:SHOW_DOCS]:
        p = ", ".join(map(str, pos[:15])) + (" ..." if len(pos) > 15 else "")
        print(f"  doc {d:<7} ({idx.title(d)})  tf={len(pos)}  positions: [{p}]")
    if df > SHOW_DOCS:
        print(f"  ... {df - SHOW_DOCS} more docs")


def show_phrase(idx, phrase):
    res = idx.phrase_search(phrase)
    print(f"phrase: \"{phrase}\"  ->  found in {len(res)} docs")
    for d, starts in list(res.items())[:SHOW_DOCS]:
        print(f"  doc {d:<7} ({idx.title(d)})  at positions {starts[:10]}")
        print(f"      ... {idx.snippet(d, starts[0], 5)} ...")


def run(idx, q):
    q = q.strip().strip('"')
    if not q:
        return
    if len(q.split()) > 1:
        show_phrase(idx, q)
    else:
        show_term(idx, q)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    idx = PositionalIndex("index")
    print(f"vocabulary loaded: {len(idx.vocab)} terms (postings stay on disk)\n")

    if len(sys.argv) > 1:
        run(idx, " ".join(sys.argv[1:]))
        return

    while True:
        try:
            q = input("query> ")
        except EOFError:
            break
        if q.strip() in ("exit", "quit"):
            break
        run(idx, q)
        print()


if __name__ == "__main__":
    main()
