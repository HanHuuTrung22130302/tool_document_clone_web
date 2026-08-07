from website_analyzer.utils.urls import canonicalize, is_probably_document, same_origin


def test_canonicalize_removes_fragment_and_tracking() -> None:
    assert canonicalize("HTTPS://Example.COM/shop/?utm_source=x&b=2&a=1#top") == "https://example.com/shop/?a=1&b=2"


def test_scope_and_document_filter() -> None:
    assert same_origin("https://example.com/a", "https://example.com/")
    assert not same_origin("https://cdn.example.com/a", "https://example.com/")
    assert is_probably_document("https://example.com/products")
    assert not is_probably_document("https://example.com/logo.svg")
