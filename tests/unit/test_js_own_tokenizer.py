from neuzelaar.engines.js_own.tokenizer import tokenize


def test_tokenize_numbers_strings_keywords_and_semicolon() -> None:
    tokens = tokenize('12.5 + "hi"; false')

    assert [token.kind for token in tokens[:-1]] == [
        "NUMBER",
        "PLUS",
        "STRING",
        "SEMICOLON",
        "FALSE",
    ]
    assert tokens[0].value == 12.5
    assert tokens[2].value == "hi"
    assert tokens[4].value is False


def test_tokenize_multi_character_operators() -> None:
    tokens = tokenize("a === b && c !== d || e <= f")

    assert [token.lexeme for token in tokens[:-1]] == [
        "a",
        "===",
        "b",
        "&&",
        "c",
        "!==",
        "d",
        "||",
        "e",
        "<=",
        "f",
    ]


def test_tokenize_skips_comments_and_handles_unicode_escape_in_strings() -> None:
    tokens = tokenize('/* frontmatter | */ "1\\u0009+\\u00091" // tail')

    assert [token.kind for token in tokens[:-1]] == ["STRING"]
    assert tokens[0].value == "1\t+\t1"
