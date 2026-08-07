from website_analyzer.crawler.deduplication import PageDeduplicator
from website_analyzer.pages.profiler import PageProfiler


def test_profiler_creates_readable_product_topic_and_template_signature() -> None:
    profile = PageProfiler().profile("https://shop.test/products/rtx-5090", """
    <html><head><title>RTX 5090 | Shop</title><meta name='description' content='High-end graphics card'></head>
    <body><header>Brand</header><main><h1>RTX 5090</h1><p>Price $100</p><button>Add to cart</button></main></body></html>""")
    assert profile.page_type == "product-detail"
    assert profile.topic == "RTX 5090"
    assert profile.output_folder == "product-detail/rtx-5090"
    assert len(profile.template_fingerprint) == 20


def test_profiler_detects_vietnamese_product_signals_and_breadcrumbs() -> None:
    profile = PageProfiler().profile("https://shop.test/san-pham/vga-rtx-4060.html", """
    <html><head><title>VGA RTX 4060 8GB | Phong Vũ</title></head>
    <body><nav aria-label='breadcrumb'><ul><li><a href='/'>Trang chủ</a></li><li><a href='/vga'>VGA Card Màn Hình</a></li></ul></nav>
    <main><h1>VGA RTX 4060 8GB</h1><p>Tình trạng: Còn hàng</p><button>Thêm vào giỏ hàng</button></main></body></html>""")
    assert profile.page_type == "product-detail"
    assert profile.topic == "VGA Card Màn Hình"


def test_card_sampling_keeps_one_representative_for_a_route_shape() -> None:
    deduplicator = PageDeduplicator()
    assert deduplicator.retain_card_link("https://shop.test/products/pc-one")
    assert not deduplicator.retain_card_link("https://shop.test/products/pc-two")
    assert deduplicator.sampled_card_links[0]["representative_url"].endswith("pc-one")


def test_route_pattern_supports_html_and_query_parameters() -> None:
    assert PageDeduplicator.route_pattern("https://shop.test/san-pham/pc-gaming.html") == "/san-pham/{item}.html"
    assert PageDeduplicator.route_pattern("https://shop.test/detail.php?id=99") == "/detail.php?id={item}"

