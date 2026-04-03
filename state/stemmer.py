import re

step2map = {
    "ational": "ate", "tional": "tion", "enci": "ence", "anci": "ance",
    "izer": "ize", "iser": "ise", "abli": "able", "alli": "al",
    "entli": "ent", "eli": "e", "ousli": "ous", "ization": "ize",
    "isation": "ise", "ation": "ate", "ator": "ate", "alism": "al",
    "iveness": "ive", "fulness": "ful", "ousness": "ous", "aliti": "al",
    "iviti": "ive", "biliti": "ble",
}

step3map = {
    "icate": "ic", "ative": "", "alize": "al", "alise": "al",
    "iciti": "ic", "ical": "ic", "ful": "", "ness": "",
}


def has_vowel(s: str) -> bool:
    return bool(re.search(r"[aeiou]", s))


def measure(s: str) -> int:
    reduced = re.sub(r"[^aeiouy]+", "C", s)
    reduced = re.sub(r"[aeiouy]+", "V", reduced)
    return len(re.findall(r"VC", reduced))


def ends_double_consonant(s: str) -> bool:
    return (
        len(s) >= 2
        and s[-1] == s[-2]
        and not re.search(r"[aeiou]", s[-1])
    )


def ends_cvc(s: str) -> bool:
    if len(s) < 3:
        return False
    c1, v, c2 = s[-3], s[-2], s[-1]
    return (
        not re.search(r"[aeiou]", c1)
        and re.search(r"[aeiou]", v)
        and not re.search(r"[aeiouwxy]", c2)
    )


def stem(word: str) -> str:
    if len(word) <= 2:
        return word

    w = word

    # Step 1a
    if w.endswith("sses"):
        w = w[:-2]
    elif w.endswith("ies"):
        w = w[:-2]
    elif not w.endswith("ss") and w.endswith("s"):
        w = w[:-1]

    # Step 1b
    if w.endswith("eed"):
        if measure(w[:-3]) > 0:
            w = w[:-1]
    elif w.endswith("ed") and has_vowel(w[:-2]):
        w = w[:-2]
        if w.endswith(("at", "bl", "iz")):
            w += "e"
        elif ends_double_consonant(w) and not re.search(r"[lsz]$", w):
            w = w[:-1]
        elif measure(w) == 1 and ends_cvc(w):
            w += "e"
    elif w.endswith("ing") and has_vowel(w[:-3]):
        w = w[:-3]
        if w.endswith(("at", "bl", "iz")):
            w += "e"
        elif ends_double_consonant(w) and not re.search(r"[lsz]$", w):
            w = w[:-1]
        elif measure(w) == 1 and ends_cvc(w):
            w += "e"

    # Step 1c
    if w.endswith("y") and has_vowel(w[:-1]):
        w = w[:-1] + "i"

    # Step 2
    for suffix, replacement in step2map.items():
        if w.endswith(suffix):
            base = w[:-len(suffix)]
            if measure(base) > 0:
                w = base + replacement
            break

    # Step 3
    for suffix, replacement in step3map.items():
        if w.endswith(suffix):
            base = w[:-len(suffix)]
            if measure(base) > 0:
                w = base + replacement
            break

    # Step 4
    match = re.search(
        r"(ement|ment|tion|sion|ance|ence|able|ible|ism|ate|iti|ous|ive|ize|ise|ant|ent|al|er|ic|ou)$",
        w,
    )
    if match:
        suffix = match.group(0)
        base = w[: -len(suffix)]
        if measure(base) > 1:
            w = base

    # Step 5a
    if w.endswith("e"):
        base = w[:-1]
        if measure(base) > 1 or (measure(base) == 1 and not ends_cvc(base)):
            w = base

    # Step 5b
    if ends_double_consonant(w) and w.endswith("l") and measure(w[:-1]) > 1:
        w = w[:-1]

    return w
