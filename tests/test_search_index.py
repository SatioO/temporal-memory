import pytest
from schema.domain import CompressedObservation, ObservationType
from state.search_index import SearchIndex


@pytest.fixture
def index():
    return SearchIndex()


@pytest.fixture
def obs():
    return CompressedObservation(
        id="obs-1",
        session_id="sess-1",
        timestamp="2026-01-01T00:00:00Z",
        type=ObservationType.FILE_READ,
        title="Read config file",
        subtitle="Loading settings",
        narrative="The agent read the config file to load application settings.",
        facts=["config loaded", "no errors found"],
        concepts=["configuration", "startup"],
        files=["config/settings.py"],
        importance=3,
    )


# --- _tokenize ---

def test_tokenize_basic(index):
    tokens = index._tokenize("hello world")
    assert tokens == ["hello", "world"]


def test_build_search_index(index, obs):
    index.add(obs)
    obs2 = CompressedObservation(
        id="obs-2",
        session_id="sess-1",
        timestamp="2026-01-01T00:00:00Z",
        type=ObservationType.COMMAND_RUN,
        title="Run tests",
        subtitle=None,
        narrative="Ran the test suite.",
        facts=[],
        concepts=[],
        files=[],
        importance=2,
    )
    index.add(obs2)
    result = index.search("null")
    print(result)


# def test_tokenize_preserves_case(index):
#     # _tokenize does not lowercase; callers are responsible for that
#     tokens = index._tokenize("Hello World")
#     assert tokens == ["Hello", "World"]


# def test_tokenize_removes_short_tokens(index):
#     # tokens with length <= 1 are filtered out
#     tokens = index._tokenize("a go run the tests")
#     assert "a" not in tokens
#     assert "go" in tokens


# def test_tokenize_strips_special_chars(index):
#     tokens = index._tokenize("hello, world! foo@bar")
#     assert "hello" in tokens
#     assert "world" in tokens
#     assert "foo" in tokens
#     assert "bar" in tokens


# def test_tokenize_preserves_paths_and_underscores(index):
#     tokens = index._tokenize("src/main.py some_var")
#     assert "src/main.py" in tokens
#     assert "some_var" in tokens


# def test_tokenize_empty_string(index):
#     assert index._tokenize("") == []


# # --- _extract_terms ---

# def test_extract_terms_includes_title(index, obs):
#     terms = index._extract_terms(obs)
#     assert "read" in terms
#     assert "config" in terms
#     assert "file" in terms


# def test_extract_terms_includes_narrative(index, obs):
#     terms = index._extract_terms(obs)
#     assert "agent" in terms
#     assert "application" in terms
#     assert "settings" in terms


# def test_extract_terms_includes_facts(index, obs):
#     terms = index._extract_terms(obs)
#     assert "loaded" in terms
#     assert "errors" in terms


# def test_extract_terms_includes_concepts(index, obs):
#     terms = index._extract_terms(obs)
#     assert "configuration" in terms
#     assert "startup" in terms


# def test_extract_terms_includes_files(index, obs):
#     terms = index._extract_terms(obs)
#     assert "config/settings.py" in terms


# def test_extract_terms_includes_type(index, obs):
#     terms = index._extract_terms(obs)
#     assert "file_read" in terms


# def test_extract_terms_no_subtitle(index):
#     obs = CompressedObservation(
#         id="obs-2",
#         session_id="sess-1",
#         timestamp="2026-01-01T00:00:00Z",
#         type=ObservationType.COMMAND_RUN,
#         title="Run tests",
#         subtitle=None,
#         narrative="Ran the test suite.",
#         facts=[],
#         concepts=[],
#         files=[],
#         importance=2,
#     )
#     terms = index._extract_terms(obs)
#     assert "run" in terms
#     assert "tests" in terms
