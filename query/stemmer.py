from snowballstemmer import stemmer as _make_stemmer

_stemmer = _make_stemmer("english")


def stem(word: str) -> str:
    return _stemmer.stemWord(word)
