"""
Builds the positional index from the Hindi wikipedia dump.

How it works (SPIMI style, like in the IR book chapter 4):
  1. read articles one by one, tokenize, and add positions to an in-memory
     dictionary  term -> {doc_id: [positions]}
  2. when the block gets big (BLOCK_TOKENS), sort the terms and write the
     block to disk (index/blocks/block_N.txt), then empty the dictionary
  3. at the end, merge all the block files into one big postings file.
     The postings are written to index/postings.bin, and for every term
     we keep  df, cf, byte offset and length  in index/vocab.tsv

So during the merge and when searching, only the vocabulary is in RAM and
the postings stay on disk. index_reader.py seeks to the offset to read one term.

usage:
    python src/indexer.py <path to hiwiki-...-pages-articles.xml.bz2> [--max-docs N]
"""

import os
import sys
import time
import heapq
import argparse

from wiki_reader import read_articles
from preprocess import load_stopwords, tokenize

BLOCK_TOKENS = 5_000_000   # roughly how many postings to keep in RAM before flushing


def write_block(block, block_no, block_dir):
    path = os.path.join(block_dir, f"block_{block_no:03d}.txt")
    with open(path, "w", encoding="utf-8") as f:
        for term in sorted(block):
            # doc ids are already in increasing order because docs come in order
            plist = ";".join(
                f"{d}:{','.join(map(str, pos))}" for d, pos in block[term].items()
            )
            f.write(f"{term}\t{plist}\n")
    return path


def read_block(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            term, plist = line.rstrip("\n").split("\t", 1)
            yield term, plist


def merge_blocks(block_paths, index_dir):
    """k-way merge of the sorted block files -> postings.bin + vocab.tsv"""
    readers = [read_block(p) for p in block_paths]
    # heapq.merge keeps everything sorted by term. for equal terms the block
    # that was written earlier comes first, so doc ids stay sorted
    merged = heapq.merge(*readers, key=lambda x: x[0])

    postings_path = os.path.join(index_dir, "postings.bin")
    vocab_path = os.path.join(index_dir, "vocab.tsv")
    n_terms = 0

    with open(postings_path, "wb") as pf, open(vocab_path, "w", encoding="utf-8") as vf:
        vf.write("term\tdf\tcf\toffset\tlength\n")
        cur_term, parts = None, []

        def flush():
            plist = ";".join(parts)
            df = plist.count(";") + 1
            cf = plist.count(",") + df   # each doc has (commas + 1) positions
            data = (plist + "\n").encode("utf-8")
            offset = pf.tell()
            pf.write(data)
            vf.write(f"{cur_term}\t{df}\t{cf}\t{offset}\t{len(data)}\n")

        for term, plist in merged:
            if term != cur_term:
                if cur_term is not None:
                    flush()
                    n_terms += 1
                cur_term, parts = term, []
            parts.append(plist)
        if cur_term is not None:
            flush()
            n_terms += 1

    return n_terms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--out", default="index")
    ap.add_argument("--max-docs", type=int, default=0, help="0 = whole dump")
    args = ap.parse_args()

    start = time.time()
    block_dir = os.path.join(args.out, "blocks")
    os.makedirs(block_dir, exist_ok=True)

    stopwords = load_stopwords()

    # doc store: cleaned text of every article (doc_text.bin) + docs.tsv with
    # title and where the text is. Not needed for the index itself, but it's how
    # I check that the positions are correct (and to show snippets)
    docs_f = open(os.path.join(args.out, "docs.tsv"), "w", encoding="utf-8")
    docs_f.write("doc_id\tpage_id\ttitle\tnum_words\ttext_offset\ttext_length\n")
    text_f = open(os.path.join(args.out, "doc_text.bin"), "wb")

    block, block_size, block_paths = {}, 0, []
    doc_id = 0
    total_tokens = 0

    for page_id, title, text in read_articles(args.dump):
        toks = tokenize(text, stopwords)
        if not toks:
            continue
        doc_id += 1

        for pos, term in toks:
            block.setdefault(term, {}).setdefault(doc_id, []).append(pos)
        block_size += len(toks)
        total_tokens += len(toks)

        raw = text.encode("utf-8")
        off = text_f.tell()
        text_f.write(raw)
        title = title.replace("\t", " ")
        docs_f.write(f"{doc_id}\t{page_id}\t{title}\t{toks[-1][0] + 1}\t{off}\t{len(raw)}\n")

        if block_size >= BLOCK_TOKENS:
            block_paths.append(write_block(block, len(block_paths), block_dir))
            print(f"  wrote block {len(block_paths)}  (docs so far: {doc_id}, "
                  f"{time.time() - start:.0f}s)")
            block, block_size = {}, 0

        if doc_id % 20000 == 0:
            print(f"{doc_id} docs read")
        if args.max_docs and doc_id >= args.max_docs:
            break

    if block:
        block_paths.append(write_block(block, len(block_paths), block_dir))
    block = None
    docs_f.close()
    text_f.close()

    print(f"merging {len(block_paths)} blocks ...")
    n_terms = merge_blocks(block_paths, args.out)

    for p in block_paths:
        os.remove(p)
    os.rmdir(block_dir)

    elapsed = time.time() - start
    psize = os.path.getsize(os.path.join(args.out, "postings.bin"))
    stats = (
        f"documents          : {doc_id}\n"
        f"indexed tokens     : {total_tokens}  (stopwords not counted)\n"
        f"vocabulary size    : {n_terms}\n"
        f"blocks written     : {len(block_paths)}\n"
        f"postings.bin size  : {psize / 1e6:.1f} MB\n"
        f"time taken         : {elapsed / 60:.1f} min\n"
    )
    print("\n" + stats)
    with open(os.path.join(args.out, "stats.txt"), "w", encoding="utf-8") as f:
        f.write(stats)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
