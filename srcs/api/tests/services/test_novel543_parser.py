"""Novel543 parser tests."""

import pytest
from shared.novel543_parser import Novel543ParseError, parse_novel543_metadata

SOURCE_URL = "https://www.novel543.com/0603625457/dir"

NOVEL543_HTML = """
<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta property="og:image" content="/files/article/image/0603625457.jpg" />
    <title>瞎眼神醫，開局遇到聖女報恩_小說543</title>
  </head>
  <body>
    <main class="book">
      <h1>瞎眼神醫，開局遇到聖女報恩</h1>
      <dl class="book-info">
        <dd>作者：<a href="/author/1/">十一條金魚</a></dd>
        <dd>類別：奇幻</dd>
        <dd>更新時間：2025年7月31日</dd>
        <dd>主角：林牧、姬梧桐</dd>
      </dl>
      <div class="cover">
        <img src="/images/ignored-cover.jpg" alt="封面" />
      </div>
      <section class="description">
        簡介：瞎眼少年林牧下山行醫，意外救下聖女，兩人踏上尋找真相的旅程。
      </section>
      <section class="latest-chapters">
        <h2>最新章節</h2>
        <ul>
          <li><a href="/0603625457/536.html">第536章 常回來看看（大結局）</a></li>
          <li><a href="/0603625457/535.html">第535章 故人重逢</a></li>
        </ul>
      </section>
      <section class="all-chapters">
        <h2>全部章节</h2>
        <ul>
          <li><a href="/0603625457/1.html">第1章 故事開始</a></li>
          <li><a href="/0603625457/2.html">第2章 踏上旅程</a></li>
          <li><a href="/0603625457/535.html">第535章 故人重逢</a></li>
          <li><a href="/0603625457/536.html">第536章 常回來看看（大結局）</a></li>
        </ul>
      </section>
    </main>
  </body>
</html>
"""


def test_novel543_parser_extracts_expected_metadata() -> None:
    metadata = parse_novel543_metadata(NOVEL543_HTML, SOURCE_URL)

    assert metadata.source_novel_id == "0603625457"
    assert metadata.title == "瞎眼神醫，開局遇到聖女報恩"
    assert metadata.author == "十一條金魚"
    assert metadata.category == "奇幻"
    assert metadata.updated_date == "2025-07-31"
    assert metadata.protagonists == ["林牧", "姬梧桐"]
    assert metadata.description == "瞎眼少年林牧下山行醫，意外救下聖女，兩人踏上尋找真相的旅程。"
    assert metadata.cover_image_url == "https://www.novel543.com/files/article/image/0603625457.jpg"
    assert [chapter.title for chapter in metadata.chapters] == [
        "第1章 故事開始",
        "第2章 踏上旅程",
        "第535章 故人重逢",
        "第536章 常回來看看（大結局）",
    ]
    assert metadata.chapters[0].url == "https://www.novel543.com/0603625457/1.html"
    assert metadata.chapters[0].chapter_number == 1


def test_novel543_parser_raises_when_title_is_missing() -> None:
    with pytest.raises(Novel543ParseError):
        parse_novel543_metadata("<html><body></body></html>", SOURCE_URL)
