"""Novel543 parser tests."""

import pytest

from app.providers.crawler_parser_novel543 import (
    Novel543ParseError,
    parse_novel543_chapter,
    parse_novel543_metadata,
)

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
    </main>
  </body>
</html>
"""

NOVEL543_DIRECTORY_HTML = """
<!doctype html>
<html lang="zh-Hant">
  <body>
    <main class="book">
      <h1>瞎眼神醫，開局遇到聖女報恩 章節列表</h1>
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
    metadata = parse_novel543_metadata(
        NOVEL543_HTML,
        SOURCE_URL,
        directory_html=NOVEL543_DIRECTORY_HTML,
    )

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


def test_novel543_chapter_parser_extracts_content_lines_and_part_metadata() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>第1章 林神醫 (1/2)</h1>
          <div id="chaptercontent">
            ————————（腦子寄存處）<br>
            大虞王朝，燕山城。<br>
            暴雪初降，城中百姓多受風寒。<br>
            溫馨提示: 如果覺得本書不錯, 請記得加入書架哦
          </div>
          <nav>上一章 | 目錄 | 下一章</nav>
        </main>
      </body>
    </html>
    """

    chapter = parse_novel543_chapter(
        html,
        "https://www.novel543.com/0603625457/8096_1.html",
    )

    assert chapter.source_novel_id == "0603625457"
    assert chapter.title == "第1章 林神醫"
    assert chapter.chapter_number == 1
    assert chapter.part_number == 1
    assert chapter.part_count == 2
    assert chapter.content == [
        "————————（腦子寄存處）",
        "大虞王朝，燕山城。",
        "暴雪初降，城中百姓多受風寒。",
    ]
