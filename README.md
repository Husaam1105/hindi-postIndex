# Positional Index for Hindi (IR Assignment 1)

This program builds a positional index over the Hindi Wikipedia. For every term it stores the
document frequency (df), the collection frequency (cf), and a postings list holding
the positions of the term inside each document. The vocabulary is kept in main memory and
the postings lists stay on disk. A lookup reads only the postings of the term being
looked up.

Plain Python 3.8 or newer. Only the standard library, nothing to pip install. It works on
Windows, Linux and macOS. I wrote it on Windows (Python 3.13) and also tested it on Ubuntu
22.04 (Python 3.10). The index files are byte-for-byte the same on both, so an index built on
one OS can be used on another.

GitHub: https://github.com/Husaam1105/hindi-postIndex

The code and the test output are on GitHub. The dump (242 MB) and the built index (~940 MB) are
too big for GitHub, so they're not in the repo. The dump can be downloaded from the link in the
Dataset section below, and running `src/indexer.py` on it rebuilds exactly the same index in
about 4 minutes.


## Dataset

The Hindi Wikipedia dump `hiwiki-latest-pages-articles.xml.bz2` (dump dated 01-Nov-2026), downloaded from
https://dumps.wikimedia.org/hiwiki/latest/ . It's one XML file that contains every article,
242 MB compressed (about 1.5 GB of XML once uncompressed).

The program reads the `.bz2` file directly, so you don't need to extract it. Only real articles
(namespace 0) are used. Redirects, talk pages, user pages, templates and so on are skipped.

After indexing the whole dump:

```
documents          : 174766
indexed tokens     : 28276768  (stopwords not counted)
vocabulary size    : 845356
blocks written     : 6
postings.bin size  : 217.8 MB
time taken         : 4.1 min
```

(the build was on my laptop, the time depends on the machine)


## How to run

On **Linux / macOS** use `python3` instead of `python` in all the commands below. On Windows,
use Windows Terminal or the VS Code terminal so the Hindi text displays properly (the old
console window shows boxes).

The commands are written to be run from the `hindi-index` folder, but the scripts find
`index/` and `output/` relative to their own location, so they also work from anywhere else.

```
# 1. download the dump (or use the drive link above)
#    put it in  dump/hiwiki-latest-pages-articles.xml.bz2
#    linux/mac:  curl -L -o dump/hiwiki-latest-pages-articles.xml.bz2 \
#                  https://dumps.wikimedia.org/hiwiki/latest/hiwiki-latest-pages-articles.xml.bz2

# 2. build the index (~4 min for the whole dump on my laptop)
python src/indexer.py dump/hiwiki-latest-pages-articles.xml.bz2

#    for a quick try on a small part of the dump (into a separate folder,
#    so it doesn't overwrite the full index):
python src/indexer.py dump/hiwiki-latest-pages-articles.xml.bz2 --max-docs 5000 --out index_small

# 3. look up terms / phrases
python src/query.py भारत
python src/query.py "महात्मा गांधी"
python src/query.py            (interactive mode, type exit to quit)

# 4. run the test cases, which writes output/test_cases.txt and output/rare_terms.txt
python src/make_tests.py
```

The index gets written to `index/`:

| file | what's in it |
|---|---|
| `vocab.tsv` | one line per term: `term  df  cf  offset  length`. This is the vocabulary that gets loaded into memory |
| `postings.bin` | all the postings lists, one after the other. `offset`/`length` in vocab.tsv say where each term's list is |
| `docs.tsv` | doc_id, wikipedia page id, title, number of words, and where its text is in doc_text.bin |
| `doc_text.bin` | cleaned text of every article. Not needed for the index itself, only used to show snippets and to check that the positions are correct |
| `stats.txt` | numbers from the last build |


## Modules (src/)

**wiki_reader.py**: reads the dump. It opens the bz2 file and goes through the XML with
`ElementTree.iterparse`, clearing elements once each page is done, so memory stays small
even though the file is huge. It keeps only namespace 0 pages that aren't redirects. Then
`clean_wikitext()` removes the wiki markup: comments, `<ref>` tags, templates `{{...}}` (which
can be nested, so it removes the innermost ones in a loop), tables, file and category links
(`[[चित्र:...]]`, `[[श्रेणी:...]]`), and HTML tags. Normal links like `[[target|label]]` are
replaced by their label. It yields `(page_id, title, text)` for each article.

**preprocess.py**: Hindi normalization and tokenization.
- Unicode NFC normalization, so the same letter is always stored the same way.
- The nukta is removed: `क़ानून` → `कानून`, `ज़िला` → `जिला`. On Wikipedia the same word is
  spelled both ways all the time.
- Chandrabindu becomes anusvara: `हँसी` → `हंसी`. Same reason.
- Zero-width joiner and non-joiner are removed.
- Words are runs of Devanagari characters that start with a proper letter (not a matra).
  The danda `।`, digits (both Devanagari `१२३` and normal ones), punctuation and English
  words aren't counted as words.
- Stopwords (`stopwords_hi.txt`, 150 words like का, के, की, है, में, और, से...) are not indexed.

  One important detail: the position of a word is its word number in the article, counting
  **all** Hindi words, stopwords included. Stopwords just don't get their own postings. So
  the positions match the real text, and a phrase like "भारत का संविधान" still works
  even though "का" isn't in the index.

**indexer.py**: builds the index with a SPIMI-style approach (Single-Pass In-Memory
Indexing, IR book chapter 4.3):
1. Articles are read one at a time and their positions are added to an in-memory dict
   `term -> {doc_id: [positions]}`.
2. Once the block holds `BLOCK_TOKENS` (5 million) positions, its terms are sorted, the block is
   written to `index/blocks/block_NNN.txt`, and the dict is emptied. So memory use during
   indexing doesn't grow with the size of the collection.
3. At the end all blocks are merged with a k-way merge (`heapq.merge`). The blocks are already
   sorted by term, and doc ids only go up from one block to the next, so the postings of a term
   are joined in block order and stay sorted. While merging, df and cf are computed for each
   term, the postings are appended to `postings.bin`, and the term with df, cf, byte offset and
   length goes into `vocab.tsv`. The block files are deleted afterwards.

**index_reader.py**: the `PositionalIndex` class used for searching. It loads `vocab.tsv`
into a dict (the vocabulary in main memory) and keeps `postings.bin` open. `lookup(term)`
normalizes the term, gets its offset from the dict, does a `seek()` and reads only those bytes.
`phrase_search()` gets the postings of every non-stopword word in the phrase, keeps the docs
that contain all of them, and then checks that the positions line up at the same offsets as
in the query. There are also helpers for titles and snippets.
One side effect: since stopwords aren't indexed, a stopword in a phrase query matches any
word in that position. So "भारत का संविधान" also finds "भारत के संविधान". I think that's
actually fine for Hindi, because का/के/की change with gender and number anyway.

**query.py**: command line tool. One word shows df, cf and the postings with positions. More
than one word is treated as a phrase query and prints the matching docs with a snippet.

**make_tests.py**: runs the test cases and writes the `output/` files (see below).


## Postings format

Each line of `postings.bin` is one term's postings list:

```
doc_id:pos,pos,pos;doc_id:pos;doc_id:pos,pos ...
```

Example (`vocab.tsv` line, and then the bytes at that offset in `postings.bin`):
```
vocab.tsv   : अंकुशम	3	6	71680	42
postings.bin: 155000:58,115;156402:59;161800:45,362,589
```

I kept it as text instead of a binary encoding so it's easy to check by hand. Gap encoding and
variable byte compression (book chapter 5) would make the file a lot smaller, but I didn't
do that.


## Test cases (output/)

`output/test_cases.txt`, 5 tests:
1. **Frequent term (भारत):** df equals the number of docs in its postings list, cf equals the
   total number of positions, and doc ids and positions are sorted.
2. **Normalization:** क़ानून/कानून, ज़िला/जिला, हँसी/हंसी and फ़िल्म/फिल्म return the same postings.
3. **Stopwords and unknown words:** का, है, में, और and a made-up word are not in the vocabulary.
4. **Phrase queries:** "प्रधानमंत्री नरेंद्र मोदी", "भारत का संविधान", "महात्मा गांधी". The results
   are checked against the actual document text.
5. **Position check:** for 300 random terms, every stored position is looked up in the document
   text to confirm the word at that position really is the term.

`output/rare_terms.txt` has 10 rare terms (df ≤ 2), each with its df, cf, full positional
postings, and the words around every position so you can see it's correct.


## Limitations / things I'd improve

- No stemming. `किताब` and `किताबें` are different terms. A light suffix-stripping stemmer for
  Hindi would merge them, but it also merges words it shouldn't.
- English words, numbers and dates inside the Hindi articles are ignored completely.
- The markup cleaner is regex based. A few odd templates or tables still leave some junk text
  behind, which is where some of the strange rare terms come from (typos and transliterated
  names are also common in Wikipedia).
- The postings aren't compressed (see above).
- The whole vocabulary is loaded into a Python dict. That's fine for this size, but for a much
  bigger collection a B-tree or a front-coded sorted array would use less RAM.
