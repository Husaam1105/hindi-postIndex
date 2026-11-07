"""
Reads the Hindi Wikipedia XML dump (the .bz2 file, no need to extract it)
and gives back one article at a time as (page_id, title, plain_text).

Uses iterparse so the whole 1.5GB xml is never loaded into memory.
Only normal articles (namespace 0) are kept, redirects are skipped.
"""

import bz2
import re
import xml.etree.ElementTree as ET


def strip_ns(tag):
    # '{http://www.mediawiki.org/xml/export-0.11/}page' -> 'page'
    return tag.rsplit("}", 1)[-1]


# links to files/images/categories should be removed completely, not turned into text
# (hindi wiki uses both the hindi and the english names)
SKIP_LINK_PREFIXES = ("चित्र:", "फ़ाइल:", "फाइल:", "file:", "image:",
                      "श्रेणी:", "category:", "media:")


def _replace_link(m):
    inside = m.group(1)
    if inside.lower().startswith(SKIP_LINK_PREFIXES):
        return " "
    # [[target|label]] -> label,  [[target]] -> target
    return inside.split("|")[-1]


def clean_wikitext(text):
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<ref[^>]*/>", " ", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", " ", text, flags=re.S | re.I)

    # templates {{...}} can be nested, so remove the innermost ones again and again
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\{\{[^{}]*\}\}", " ", text)

    # tables {| ... |}
    text = re.sub(r"\{\|.*?\|\}", " ", text, flags=re.S)

    # internal links, again innermost first (image captions can contain links)
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\[\[([^\[\]]*)\]\]", _replace_link, text)

    # external links [http://... label] -> label
    text = re.sub(r"\[https?://\S+\s*([^\]]*)\]", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)          # leftover html tags
    text = re.sub(r"'{2,}", "", text)             # bold / italic
    text = re.sub(r"={2,}", " ", text)            # == headings ==
    text = text.replace("&nbsp;", " ")
    return text


def read_articles(dump_path):
    with bz2.open(dump_path, "rb") as f:
        context = ET.iterparse(f, events=("start", "end"))
        _, root = next(context)

        title = page_id = text = None
        ns = None
        is_redirect = False
        in_revision = False

        for event, elem in context:
            tag = strip_ns(elem.tag)

            if event == "start":
                if tag == "page":
                    title = page_id = text = ns = None
                    is_redirect = False
                elif tag == "revision":
                    in_revision = True
                continue

            # end events
            if tag == "title":
                title = elem.text
            elif tag == "ns":
                ns = elem.text
            elif tag == "id" and not in_revision and page_id is None:
                page_id = elem.text        # page id, not the revision id
            elif tag == "redirect":
                is_redirect = True
            elif tag == "text":
                text = elem.text or ""
            elif tag == "revision":
                in_revision = False
            elif tag == "page":
                if ns == "0" and not is_redirect and text:
                    if not text.lstrip().lower().startswith(("#redirect", "#अनुप्रेषित")):
                        yield int(page_id), title, clean_wikitext(text)
                # free memory, otherwise the tree keeps growing
                root.clear()
