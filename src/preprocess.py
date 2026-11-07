"""
Hindi text normalization + tokenization.

tokenize() returns (position, term) pairs. The position is the word number in
the document counting ALL hindi words, including stopwords. Stopwords are just
not put in the index. That way positions still match the real text, and
phrase queries like "भारत का इतिहास" work.
"""

import os
import re
import unicodedata

NUKTA = "़"
CHANDRABINDU = "ँ"
ANUSVARA = "ं"

# devanagari block is 0900-097F. leave out the danda (0964, 0965),
# the devanagari digits (0966-096F) and the abbreviation sign (0970).
# a word has to start with an actual letter / vowel, not a matra or ं,
# otherwise broken pieces like "ंग्रेजी" end up as terms
WORD_RE = re.compile(r"[ऄ-हऽॐक़-ॡॲ-ॿ]"
                     r"[ऀ-ॣॱ-ॿ]*")

_here = os.path.dirname(os.path.abspath(__file__))


def normalize(text):
    # NFC first so the same character isn't stored in two different byte forms.
    # the nukta letters (क़ ख़ ग़ ज़ ड़ ढ़ फ़ य़) stay as base letter + nukta after NFC,
    # so removing the nukta sign maps क़ानून and कानून to the same term
    text = unicodedata.normalize("NFC", text)
    text = text.replace(NUKTA, "")
    # people use chandrabindu and anusvara pretty much interchangeably (हँसी / हंसी)
    text = text.replace(CHANDRABINDU, ANUSVARA)
    # zero width joiner / non-joiner only change how the letters are drawn
    text = text.replace("‌", "").replace("‍", "")
    return text


def load_stopwords(path=os.path.join(_here, "stopwords_hi.txt")):
    stop = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            w = line.strip()
            if w and not w.startswith("#"):
                stop.add(normalize(w))
    return stop


def words(text):
    """all hindi words in order (nothing removed) - positions are indexes into this list"""
    return WORD_RE.findall(normalize(text))


def tokenize(text, stopwords):
    result = []
    for pos, w in enumerate(words(text)):
        if len(w) < 2 or w in stopwords:
            continue
        result.append((pos, w))
    return result


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    sw = load_stopwords()
    s = "भारत का क़ानून, संविधान १९५० में लागू हुआ। लोग हँसी-ख़ुशी रहते हैं!"
    print(words(s))
    print(tokenize(s, sw))
