"""
Runs the test cases on the built index and writes the results to output/
    output/test_cases.txt  - the 5 test cases
    output/rare_terms.txt  - 10 rare terms with their full positional index

    python src/make_tests.py
"""

import os
import sys
import random
from index_reader import PositionalIndex
from preprocess import normalize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")


class Report:
    def __init__(self):
        self.lines = []

    def __call__(self, s=""):
        print(s)
        self.lines.append(s)

    def save(self, path):
        # "\n" line endings on every OS
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(self.lines) + "\n")


def check_positions(idx, term, postings):
    """every stored position should point at that exact word in the document"""
    bad = 0
    for d, pos in postings.items():
        ws = idx.doc_words(d)
        bad += sum(1 for p in pos if p >= len(ws) or ws[p] != term)
    return bad


def test_cases(idx):
    r = Report()
    r("Test cases for the Hindi positional index")
    r("=" * 60)
    with open(os.path.join(idx.index_dir, "stats.txt"), encoding="utf-8") as f:
        r(f.read())

    # ---------------------------------------------------------------
    r("TEST 1: frequent term - df and cf are consistent with the postings")
    r("-" * 60)
    term = "भारत"
    df, cf, postings = idx.lookup(term)
    r(f"term '{term}': df = {df}, cf = {cf}")
    r(f"number of docs in postings list   = {len(postings)}")
    r(f"sum of positions over all docs    = {sum(len(p) for p in postings.values())}")
    r(f"doc ids sorted                    = {list(postings) == sorted(postings)}")
    r(f"positions sorted inside every doc = {all(p == sorted(p) for p in postings.values())}")
    first = list(postings.items())[:3]
    for d, p in first:
        r(f"  doc {d} ({idx.title(d)}): {p[:10]}{' ...' if len(p) > 10 else ''}")
    ok = df == len(postings) and cf == sum(len(p) for p in postings.values())
    r(f"RESULT: {'PASS' if ok else 'FAIL'}\n")

    # ---------------------------------------------------------------
    r("TEST 2: normalization - different spellings give the same postings")
    r("-" * 60)
    pairs = [("क़ानून", "कानून"), ("ज़िला", "जिला"), ("हँसी", "हंसी"), ("फ़िल्म", "फिल्म")]
    all_ok = True
    for a, b in pairs:
        ra, rb = idx.lookup(a), idx.lookup(b)
        same = ra is not None and ra == rb
        all_ok &= same
        info = f"df={ra[0]}, cf={ra[1]}" if ra else "not found"
        r(f"  '{a}' vs '{b}' -> both normalize to '{normalize(a)}', same postings: {same} ({info})")
    r(f"RESULT: {'PASS' if all_ok else 'FAIL'}\n")

    # ---------------------------------------------------------------
    r("TEST 3: stopwords and unknown words are not in the vocabulary")
    r("-" * 60)
    all_ok = True
    for w in ["का", "है", "में", "और", "क्षज्ञत्रकखग"]:
        found = idx.lookup(w) is not None
        all_ok &= not found
        r(f"  '{w}' in vocabulary: {found}")
    r(f"RESULT: {'PASS' if all_ok else 'FAIL'}\n")

    # ---------------------------------------------------------------
    r("TEST 4: phrase queries using the positions")
    r("-" * 60)
    all_ok = True
    for phrase in ["प्रधानमंत्री नरेंद्र मोदी", "भारत का संविधान", "महात्मा गांधी"]:
        res = idx.phrase_search(phrase)
        r(f"  \"{phrase}\" -> {len(res)} docs")
        for d, starts in list(res.items())[:2]:
            r(f"     doc {d} ({idx.title(d)}) at {starts[:5]}:  {idx.snippet(d, starts[0], 4)}")
        # check that the phrase really is there in the original text.
        # stopwords are not indexed so they match any word in that slot
        # (e.g. "भारत का संविधान" also finds "भारत के संविधान") - only compare the others
        target = [normalize(w) for w in phrase.split()]
        for d, starts in list(res.items())[:50]:
            ws = idx.doc_words(d)
            for s in starts:
                for k, w in enumerate(target):
                    if w not in idx.stopwords:
                        all_ok &= ws[s + k] == w
    r("  (checked the first 50 docs of each result against the document text.")
    r("   stopwords aren't indexed, so the का in \"भारत का संविधान\" can be any word,")
    r("   which means it also matches \"भारत के संविधान\" - that's expected)")
    r(f"RESULT: {'PASS' if all_ok else 'FAIL'}\n")

    # ---------------------------------------------------------------
    r("TEST 5: positions point to the right word (random sample of terms)")
    r("-" * 60)
    rng = random.Random(7)
    terms = rng.sample(sorted(t for t, v in idx.vocab.items() if v[0] <= 50), 300)
    checked = bad = 0
    for t in terms:
        df, cf, postings = idx.lookup(t)
        bad += check_positions(idx, t, postings)
        checked += cf
    r(f"  checked {checked} positions of {len(terms)} random terms against the doc text")
    r(f"  wrong positions: {bad}")
    r(f"RESULT: {'PASS' if bad == 0 else 'FAIL'}")
    return r


def rare_terms(idx):
    r = Report()
    r("10 rare terms and their positional index")
    r("format:  term  df  cf  ->  doc_id: [positions]")
    r("=" * 60)
    # rare = appears in only 1-2 docs. take ones that occur more than once
    # so the position list is a bit more interesting, and skip very short ones
    cands = sorted(t for t, (df, cf, _, _) in idx.vocab.items()
                   if df <= 2 and 2 <= cf <= 6 and len(t) >= 5)
    rng = random.Random(2026)
    picked = rng.sample(cands, 10)

    for i, t in enumerate(picked, 1):
        df, cf, postings = idx.lookup(t)
        r(f"\n{i}. {t}   df = {df}   cf = {cf}")
        for d, pos in postings.items():
            r(f"   doc {d}: {pos}      [{idx.title(d)}]")
            for p in pos:
                r(f"      pos {p}: ... {idx.snippet(d, p, 4)} ...")
        bad = check_positions(idx, t, postings)
        r(f"   positions verified against text: {'yes' if bad == 0 else f'NO ({bad} wrong)'}")
    return r


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(OUT, exist_ok=True)
    idx = PositionalIndex(os.path.join(ROOT, "index"))
    test_cases(idx).save(os.path.join(OUT, "test_cases.txt"))
    print()
    rare_terms(idx).save(os.path.join(OUT, "rare_terms.txt"))
