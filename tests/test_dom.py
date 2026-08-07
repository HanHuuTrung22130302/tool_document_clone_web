from website_analyzer.dom.analyzer import DomAnalyzer


def test_dom_analyzer_extracts_forms_components_and_links() -> None:
    result = DomAnalyzer().analyze("https://example.com/", """
    <html><body><header><nav aria-label='Primary'>Menu</nav></header>
    <main><article class='card'><a href='/products'>Products</a></article>
    <form id='login-form' method='post'><input name='email' required placeholder='Email'><input name='password' type='password'></form></main>
    <footer>Footer</footer></body></html>""")
    assert result["links"] == [{"url": "https://example.com/products", "label": "Products", "card_context": True}]
    assert result["forms"][0].category == "login"
    assert {component.kind for component in result["components"]} >= {"Navbar", "Card", "Footer"}
