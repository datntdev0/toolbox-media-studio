"""HTML parser for Novel543 novel metadata pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


class Novel543ParseError(ValueError):
    """Raised when required Novel543 metadata cannot be parsed."""


@dataclass(frozen=True, slots=True)
class ParsedChapter:
    """Chapter metadata parsed from a Novel543 directory page."""

    title: str
    url: str
    chapter_number: int | None = None


@dataclass(frozen=True, slots=True)
class ParsedNovelMetadata:
    """Novel metadata parsed from Novel543."""

    source_novel_id: str
    title: str
    author: str | None
    category: str | None
    updated_date: str | None
    protagonists: list[str]
    description: str | None
    cover_image_url: str | None
    chapters: list[ParsedChapter]


_NOVEL_ID_PATTERN = re.compile(r"^/(?P<source_novel_id>[0-9]+)/dir$")
_DATE_PATTERN = re.compile(
    r"(?P<year>[0-9]{4})[-/.年](?P<month>[0-9]{1,2})[-/.月](?P<day>[0-9]{1,2})"
)
_CHAPTER_NUMBER_PATTERN = re.compile(r"第\s*(?P<number>[0-9]+)\s*[章回話话]")
_ENGLISH_CHAPTER_PATTERN = re.compile(r"\b(?:chapter|ch)\.?\s*(?P<number>[0-9]+)\b", re.IGNORECASE)

_AUTHOR_LABELS = ("作者", "作家")
_CATEGORY_LABELS = ("類別", "类别", "分類", "分类", "類型", "类型")
_UPDATED_LABELS = ("更新時間", "更新时间", "更新日期", "最新更新", "更新")
_PROTAGONIST_LABELS = ("主角", "主人公", "男女主角")
_DESCRIPTION_LABELS = ("簡介", "简介", "內容簡介", "内容简介")
_ALL_LABELS = (
    *_AUTHOR_LABELS,
    *_CATEGORY_LABELS,
    *_UPDATED_LABELS,
    *_PROTAGONIST_LABELS,
    *_DESCRIPTION_LABELS,
)


def parse_novel543_metadata(
    html: str,
    source_url: str | None = None,
    source_novel_id: str | None = None,
    canonical_url: str | None = None,
) -> ParsedNovelMetadata:
    """Parse a Novel543 novel directory page into normalized metadata."""

    page_url = canonical_url or source_url
    if page_url is None:
        raise Novel543ParseError("Source URL is required")

    soup = BeautifulSoup(html, "html.parser")
    novel_id = source_novel_id or _source_novel_id_from_url(page_url)
    title = _extract_title(soup)
    if title is None:
        raise Novel543ParseError("Novel title was not found")

    return ParsedNovelMetadata(
        source_novel_id=novel_id,
        title=title,
        author=_extract_labeled_text(soup, _AUTHOR_LABELS),
        category=_extract_labeled_text(soup, _CATEGORY_LABELS),
        updated_date=_parse_date(_extract_labeled_text(soup, _UPDATED_LABELS)),
        protagonists=_split_people(_extract_labeled_text(soup, _PROTAGONIST_LABELS)),
        description=_extract_description(soup),
        cover_image_url=_extract_cover_image_url(soup, page_url),
        chapters=_extract_chapters(soup, page_url, novel_id),
    )


def _source_novel_id_from_url(source_url: str) -> str:
    path = urlsplit(source_url).path
    match = _NOVEL_ID_PATTERN.fullmatch(path)
    if match is None:
        raise Novel543ParseError("Novel id was not found in the source URL")
    return match.group("source_novel_id")


def _extract_title(soup: BeautifulSoup) -> str | None:
    title = _first_text(soup, ("h1", ".book-title", ".novel-title", "[itemprop='name']"))
    if title:
        return title

    meta_title = _meta_content(soup, "property", "og:title") or _meta_content(soup, "name", "title")
    if meta_title:
        return _clean_title(meta_title)

    if soup.title and soup.title.string:
        return _clean_title(soup.title.string)
    return None


def _first_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        tag = soup.select_one(selector)
        if isinstance(tag, Tag):
            text = _normalize_space(tag.get_text(" ", strip=True))
            if text:
                return text
    return None


def _clean_title(value: str) -> str:
    title = _normalize_space(value)
    for separator in ("_", "-", "|"):
        if separator in title:
            title = title.split(separator, maxsplit=1)[0].strip()
    return title


def _extract_labeled_text(soup: BeautifulSoup, labels: tuple[str, ...]) -> str | None:
    for tag_name in ("li", "p", "tr", "td", "dd", "span", "div"):
        for tag in soup.find_all(tag_name):
            if not isinstance(tag, Tag):
                continue
            value = _strip_labeled_value(_normalize_space(tag.get_text(" ", strip=True)), labels)
            if value:
                return value
    return None


def _strip_labeled_value(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        if text == label:
            continue
        for prefix in (f"{label}:", f"{label}："):
            index = text.find(prefix)
            if index >= 0:
                value = text[index + len(prefix) :].strip(" :：-")
                value = _trim_at_next_label(value, labels)
                return value or None
        if text.startswith(label):
            value = text[len(label) :].strip(" :：-")
            value = _trim_at_next_label(value, labels)
            return value or None
    return None


def _trim_at_next_label(value: str, current_labels: tuple[str, ...]) -> str:
    earliest: int | None = None
    for label in _ALL_LABELS:
        if label in current_labels:
            continue
        for marker in (f" {label}:", f" {label}：", f"{label}:", f"{label}："):
            index = value.find(marker)
            if index >= 0 and (earliest is None or index < earliest):
                earliest = index
    return value[:earliest].strip() if earliest is not None else value


def _parse_date(value: str | None) -> str | None:
    if value is None:
        return None
    match = _DATE_PATTERN.search(value)
    if match is None:
        return None
    year = int(match.group("year"))
    month = int(match.group("month"))
    day = int(match.group("day"))
    return f"{year:04d}-{month:02d}-{day:02d}"


def _split_people(value: str | None) -> list[str]:
    if value is None:
        return []
    return [name for name in re.split(r"[、,，/／;；\s]+", value) if name]


def _extract_description(soup: BeautifulSoup) -> str | None:
    for selector in (
        "[itemprop='description']",
        ".description",
        ".desc",
        ".intro",
        "#intro",
        ".book-intro",
        ".bookIntro",
    ):
        tag = soup.select_one(selector)
        if not isinstance(tag, Tag):
            continue
        text = _normalize_space(tag.get_text(" ", strip=True))
        text = _strip_labeled_value(text, _DESCRIPTION_LABELS) or text
        if text:
            return text

    return _meta_content(soup, "name", "description") or _meta_content(
        soup,
        "property",
        "og:description",
    ) or _first_plain_paragraph(soup)


def _first_plain_paragraph(soup: BeautifulSoup) -> str | None:
    for tag in soup.find_all("p"):
        if not isinstance(tag, Tag):
            continue
        text = _normalize_space(tag.get_text(" ", strip=True))
        if text and not any(label in text for label in _ALL_LABELS):
            return _strip_labeled_value(text, _DESCRIPTION_LABELS) or text
    return None


def _extract_cover_image_url(soup: BeautifulSoup, source_url: str) -> str | None:
    meta_image = _meta_content(soup, "property", "og:image")
    if meta_image:
        return urljoin(source_url, meta_image)

    for selector in (".cover img", ".book-cover img", ".book img", "img"):
        tag = soup.select_one(selector)
        if not isinstance(tag, Tag):
            continue
        image_url = _first_attr(tag, ("src", "data-src", "data-original", "data-lazy-src"))
        if image_url:
            return urljoin(source_url, image_url)
    return None


def _extract_chapters(
    soup: BeautifulSoup,
    source_url: str,
    source_novel_id: str,
) -> list[ParsedChapter]:
    links = _all_chapter_links(soup)
    chapters: list[ParsedChapter] = []
    seen_urls: set[str] = set()
    for link in links:
        href = _string_attr(link, "href")
        title = _normalize_space(link.get_text(" ", strip=True))
        if href is None or not title:
            continue
        url = urljoin(source_url, href)
        if not _is_chapter_url(url, source_url, source_novel_id):
            continue
        if url in seen_urls:
            continue
        chapters.append(
            ParsedChapter(
                title=title,
                url=url,
                chapter_number=_parse_chapter_number(title),
            )
        )
        seen_urls.add(url)
    return chapters


def _all_chapter_links(soup: BeautifulSoup) -> list[Tag]:
    for heading in soup.find_all(("h1", "h2", "h3", "h4", "h5", "h6")):
        if not isinstance(heading, Tag):
            continue
        heading_text = _normalize_space(heading.get_text(" ", strip=True))
        if "全部章" not in heading_text:
            continue
        return [
            element
            for element in heading.find_all_next("a")
            if isinstance(element, Tag)
        ]

    for selector in (
        ".all-chapters a",
        ".allChapter a",
        ".chapter-list a",
        ".dirlist a",
        "#all-chapters a",
        "#chapter-list a",
        "#dirlist a",
    ):
        links = [tag for tag in soup.select(selector) if isinstance(tag, Tag)]
        if links:
            return links

    return [tag for tag in soup.find_all("a") if isinstance(tag, Tag)]


def _is_chapter_url(url: str, source_url: str, source_novel_id: str) -> bool:
    parsed = urlsplit(url)
    source = urlsplit(source_url)
    if parsed.scheme != source.scheme or parsed.netloc != source.netloc:
        return False
    chapter_path = re.compile(rf"^/{re.escape(source_novel_id)}/[^/]+\.html$")
    return chapter_path.fullmatch(parsed.path) is not None


def _parse_chapter_number(title: str) -> int | None:
    match = _CHAPTER_NUMBER_PATTERN.search(title) or _ENGLISH_CHAPTER_PATTERN.search(title)
    if match is None:
        return None
    return int(match.group("number"))


def _meta_content(soup: BeautifulSoup, key: str, value: str) -> str | None:
    tag = soup.find("meta", attrs={key: value})
    if not isinstance(tag, Tag):
        return None
    return _string_attr(tag, "content")


def _first_attr(tag: Tag, names: tuple[str, ...]) -> str | None:
    for name in names:
        value = _string_attr(tag, name)
        if value:
            return value
    return None


def _string_attr(tag: Tag, name: str) -> str | None:
    value = tag.get(name)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _normalize_space(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())
