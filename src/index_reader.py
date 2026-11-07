"""
Loads the vocabulary into memory and reads postings from disk only when needed.

vocab.tsv  ->  dict  term -> (df, cf, offset, length)      [in RAM]
postings.bin is kept open and we seek() to the offset for a term   [on disk]
"""

import os
from preprocess import normalize, words, load_stopwords


class PositionalIndex:
    def __init__(self, index_dir="index"):
        self.index_dir = index_dir
        self.vocab = {}
        with open(os.path.join(index_dir, "vocab.tsv"), encoding="utf-8") as f:
            next(f)  # header
            for line in f:
                # rstrip \r too, in case the file was made with windows line endings
                term, df, cf, off, length = line.rstrip("\r\n").split("\t")
                self.vocab[term] = (int(df), int(cf), int(off), int(length))

        self.postings_file = open(os.path.join(index_dir, "postings.bin"), "rb")
        self.stopwords = load_stopwords()
        self.docs = None   # loaded lazily, only needed for titles / snippets

    def lookup(self, term):
        """returns (df, cf, {doc_id: [positions]}) or None if term not in vocab"""
        term = normalize(term)
        if term not in self.vocab:
            return None
        df, cf, off, length = self.vocab[term]
        self.postings_file.seek(off)
        line = self.postings_file.read(length).decode("utf-8").strip()
        postings = {}
        for entry in line.split(";"):
            d, pos = entry.split(":")
            postings[int(d)] = [int(p) for p in pos.split(",")]
        return df, cf, postings

    def phrase_search(self, phrase):
        """docs where the words of the phrase appear next to each other.
        stopwords in the phrase aren't indexed, but they still take up a position,
        so we just check the offsets of the non-stopword terms"""
        ws = words(phrase)
        terms = [(i, w) for i, w in enumerate(ws) if len(w) >= 2 and w not in self.stopwords]
        if not terms:
            return {}

        lists = []
        for offset, w in terms:
            r = self.lookup(w)
            if r is None:
                return {}
            lists.append((offset, r[2]))

        # start from the rarest term so there are fewer candidates
        lists.sort(key=lambda x: len(x[1]))
        common_docs = set(lists[0][1])
        for _, p in lists[1:]:
            common_docs &= p.keys()

        result = {}
        anchor_off, anchor_postings = lists[0]
        for d in sorted(common_docs):
            pos_sets = [(off, set(p[d])) for off, p in lists]
            matches = []
            for p in anchor_postings[d]:
                start = p - anchor_off   # where the phrase would begin
                if all(start + off in ps for off, ps in pos_sets):
                    matches.append(start)
            if matches:
                result[d] = matches
        return result

    # ---- doc store helpers (titles / original words) ----
    def _load_docs(self):
        self.docs = {}
        with open(os.path.join(self.index_dir, "docs.tsv"), encoding="utf-8") as f:
            next(f)
            for line in f:
                d, page_id, title, nw, off, length = line.rstrip("\r\n").split("\t")
                self.docs[int(d)] = (title, int(off), int(length))

    def title(self, doc_id):
        if self.docs is None:
            self._load_docs()
        return self.docs[doc_id][0]

    def doc_words(self, doc_id):
        if self.docs is None:
            self._load_docs()
        _, off, length = self.docs[doc_id]
        with open(os.path.join(self.index_dir, "doc_text.bin"), "rb") as f:
            f.seek(off)
            return words(f.read(length).decode("utf-8"))

    def snippet(self, doc_id, pos, width=4):
        ws = self.doc_words(doc_id)
        left = ws[max(0, pos - width):pos]
        right = ws[pos + 1:pos + 1 + width]
        return " ".join(left + [f"[{ws[pos]}]"] + right)
