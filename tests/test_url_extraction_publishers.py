from app.services.url_extraction.publishers.ckxxapp import try_extract_ckxxapp_article


def test_try_extract_ckxxapp_article_extracts_mobile_article_fields() -> None:
    html = """
    <html>
      <head>
        <title>页面标题</title>
        <meta property="og:title" content="OG 标题" />
        <meta property="article:published_time" content="2026-03-22" />
      </head>
      <body>
        <div class="article-title">参考消息标题</div>
        <div class="article-time">2026-03-22 18:45:43</div>
        <script>
          var contentTxt ="<p>第一段正文。</p><p>第二段正文。</p>";
        </script>
      </body>
    </html>
    """
    result = try_extract_ckxxapp_article(
        "https://ckxxapp.ckxx.net/pages/2026/03/22/test.html",
        html,
    )

    assert result is not None
    assert result.title == "参考消息标题"
    assert result.publish_date == "2026-03-22"
    assert result.source_url == "https://ckxxapp.ckxx.net/pages/2026/03/22/test.html"
    assert result.content == "第一段正文。\n\n第二段正文。"


def test_try_extract_ckxxapp_article_returns_none_for_non_matching_url() -> None:
    html = "<html><body><div class='article-title'>标题</div></body></html>"
    result = try_extract_ckxxapp_article("https://example.com/news/1", html)
    assert result is None


def test_try_extract_ckxxapp_article_handles_realworld_escaped_contenttxt_without_garbled_text() -> None:
    html = """
    <html>
      <head>
        <meta property="article:published_time" content="2026-03-22" />
      </head>
      <body>
        <div class="article-title">高油价阴云压顶 外国投资者逃离日本股市</div>
        <div class="article-time">2026-03-22 18:45:43</div>
        <script>
          var contentTxt ="<p style=\\"text-indent: 2em; text-align: left;\\"><strong>参考消息网3月22日报道<\\/strong> 据彭博新闻社网站3月19日报道，石油风险导致前景黯淡之际，外国投资者逃离日本股市。<\\/p><p style=\\"text-indent: 2em; text-align: left;\\">由于越来越担忧油价上涨将打击日本经济，外国人上周成为日本股票的净卖家。<\\/p>";
        </script>
      </body>
    </html>
    """
    result = try_extract_ckxxapp_article(
        "https://ckxxapp.ckxx.net/pages/2026/03/22/test.html",
        html,
    )

    assert result is not None
    assert "参考消息网3月22日报道" in result.content
    assert "外国投资者逃离日本股市" in result.content
    assert "由于越来越担忧油价上涨将打击日本经济" in result.content
    assert "å" not in result.content
    assert "<\\/strong>" not in result.content
