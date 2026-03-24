import re
from collections import Counter
from urllib.parse import urljoin, urlparse

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from bs4 import BeautifulSoup


st.set_page_config(
    page_title="Smart Web Scraper",
    page_icon="🕸️",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #0b1220 0%, #111827 100%);
        color: #f3f4f6;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    .card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.20);
    }
    .hero {
        background: linear-gradient(135deg, rgba(59,130,246,0.18), rgba(168,85,247,0.16));
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 24px;
        padding: 28px;
        margin-bottom: 18px;
    }
    h1, h2, h3 {
        color: #ffffff !important;
    }
    .muted {
        color: #cbd5e1;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "it", "for", "on", "that",
    "this", "with", "as", "are", "was", "were", "be", "by", "at", "from", "has", "have",
    "had", "will", "would", "can", "could", "should", "you", "your", "we", "our", "they",
    "their", "he", "she", "his", "her", "them", "not", "but", "if", "about", "into",
    "than", "then", "so", "such", "these", "those", "also", "there", "here", "which",
    "who", "whom", "what", "when", "where", "why", "how", "all", "any", "each", "more",
    "most", "other", "some", "no", "nor", "only", "own", "same", "too", "very", "s",
    "t", "just", "don", "now"
}


def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.text


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_page_data(url: str) -> dict:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else "No title found"

    meta_description = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_description = meta_tag["content"].strip()

    headings = []
    for level in ["h1", "h2", "h3"]:
        for tag in soup.find_all(level):
            txt = clean_text(tag.get_text(" ", strip=True))
            if txt:
                headings.append({"tag": level.upper(), "text": txt})

    paragraphs = []
    for p in soup.find_all("p"):
        txt = clean_text(p.get_text(" ", strip=True))
        if txt:
            paragraphs.append(txt)

    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        text = clean_text(a.get_text(" ", strip=True))
        full_url = urljoin(url, href)
        if full_url not in seen and full_url.startswith(("http://", "https://")):
            seen.add(full_url)
            links.append(
                {
                    "text": text if text else "(no anchor text)",
                    "url": full_url,
                    "domain": urlparse(full_url).netloc,
                }
            )

    tables = []
    try:
        table_dfs = pd.read_html(html)
        for idx, df in enumerate(table_dfs, start=1):
            tables.append({"name": f"Table {idx}", "data": df})
    except ValueError:
        pass

    all_text = " ".join(
        [title, meta_description] +
        [h["text"] for h in headings] +
        paragraphs
    )
    all_text = clean_text(all_text)

    words = re.findall(r"\b[a-zA-Z]{3,}\b", all_text.lower())
    words = [w for w in words if w not in STOPWORDS]
    word_freq = Counter(words).most_common(15)

    insights = {
        "title": title,
        "meta_description": meta_description,
        "heading_count": len(headings),
        "paragraph_count": len(paragraphs),
        "link_count": len(links),
        "table_count": len(tables),
        "word_count": len(all_text.split()),
        "top_words": word_freq,
    }

    return {
        "url": url,
        "title": title,
        "meta_description": meta_description,
        "headings": headings,
        "paragraphs": paragraphs,
        "links": links,
        "tables": tables,
        "insights": insights,
    }


def build_text_dataframe(data: dict) -> pd.DataFrame:
    rows = []

    rows.append({"type": "title", "content": data["title"]})

    if data["meta_description"]:
        rows.append({"type": "meta_description", "content": data["meta_description"]})

    for h in data["headings"]:
        rows.append({"type": h["tag"], "content": h["text"]})

    for p in data["paragraphs"]:
        rows.append({"type": "paragraph", "content": p})

    return pd.DataFrame(rows)


def build_links_dataframe(data: dict) -> pd.DataFrame:
    if not data["links"]:
        return pd.DataFrame(columns=["text", "url", "domain"])
    return pd.DataFrame(data["links"])


def get_summary_points(data: dict) -> list[str]:
    insights = data["insights"]
    points = []

    points.append(f"Page contains **{insights['heading_count']} headings** and **{insights['paragraph_count']} paragraphs**.")
    points.append(f"Found **{insights['link_count']} links** and **{insights['table_count']} tables**.")
    points.append(f"Estimated visible text size is **{insights['word_count']} words**.")

    if insights["top_words"]:
        top3 = ", ".join([f"{w} ({c})" for w, c in insights["top_words"][:3]])
        points.append(f"Most repeated content words: **{top3}**.")

    if data["headings"]:
        points.append(f"Primary heading signal starts with: **{data['headings'][0]['text']}**.")

    return points


st.markdown(
    """
    <div class="hero">
        <h1>🕸️ Smart Web Scraper + Insights</h1>
        <p class="muted">
            Paste any public webpage URL to extract content, links, tables, and quick insights in a clean dashboard.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

col_a, col_b = st.columns([4, 1], vertical_alignment="bottom")

with col_a:
    url = st.text_input(
        "Enter webpage URL",
        placeholder="https://example.com/article",
        label_visibility="visible"
    )

with col_b:
    st.markdown("<br>", unsafe_allow_html=True)  # pushes button down
    scrape_clicked = st.button("Scrape", use_container_width=True)

with st.expander("Options"):
    max_paragraphs = st.slider("Max paragraphs to show", 5, 100, 20)
    max_links = st.slider("Max links to show", 5, 200, 25)

if scrape_clicked:
    if not url:
        st.error("Please enter a URL.")
        st.stop()

    if not is_valid_url(url):
        st.error("Please enter a valid URL including http:// or https://")
        st.stop()

    try:
        with st.spinner("Scraping webpage and generating insights..."):
            data = extract_page_data(url)
    except Exception as e:
        st.error(f"Could not scrape this page: {e}")
        st.stop()

    text_df = build_text_dataframe(data)
    links_df = build_links_dataframe(data)

    insights = data["insights"]

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Words", insights["word_count"])
    m2.metric("Headings", insights["heading_count"])
    m3.metric("Paragraphs", insights["paragraph_count"])
    m4.metric("Links", insights["link_count"])
    m5.metric("Tables", insights["table_count"])

    left, right = st.columns([1.3, 1])

    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Page Overview")
        st.write(f"**Title:** {data['title']}")
        if data["meta_description"]:
            st.write(f"**Meta description:** {data['meta_description']}")
        st.write(f"**URL:** {data['url']}")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Key Insights")
        for point in get_summary_points(data):
            st.markdown(f"- {point}")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Top Words")
        if insights["top_words"]:
            freq_df = pd.DataFrame(insights["top_words"], columns=["word", "count"])
            fig = px.bar(freq_df, x="word", y="count", title="Most Frequent Words")
            fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No keyword insights available.")
        st.markdown("</div>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["Text", "Links", "Tables", "Download"])

    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Extracted Text")
        if text_df.empty:
            st.info("No text extracted.")
        else:
            st.dataframe(text_df, use_container_width=True, hide_index=True)

            st.markdown("### Preview Paragraphs")
            for i, paragraph in enumerate(data["paragraphs"][:max_paragraphs], start=1):
                st.markdown(f"**{i}.** {paragraph}")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Extracted Links")
        if links_df.empty:
            st.info("No links found.")
        else:
            st.dataframe(links_df.head(max_links), use_container_width=True, hide_index=True)

            domain_counts = (
                links_df["domain"]
                .value_counts()
                .reset_index()
            )
            domain_counts.columns = ["domain", "count"]

            fig_domains = px.pie(domain_counts, names="domain", values="count", title="Links by Domain")
            fig_domains.update_layout(margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_domains, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Tables Found on Page")
        if not data["tables"]:
            st.info("No HTML tables found on this page.")
        else:
            for table in data["tables"]:
                st.markdown(f"### {table['name']}")
                st.dataframe(table["data"], use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Download Data")

        text_csv = text_df.to_csv(index=False).encode("utf-8")
        links_csv = links_df.to_csv(index=False).encode("utf-8")

        json_payload = {
            "url": data["url"],
            "title": data["title"],
            "meta_description": data["meta_description"],
            "headings": data["headings"],
            "paragraphs": data["paragraphs"],
            "links": data["links"],
            "insights": data["insights"],
        }

        st.download_button(
            "Download text CSV",
            data=text_csv,
            file_name="scraped_text.csv",
            mime="text/csv",
        )

        st.download_button(
            "Download links CSV",
            data=links_csv,
            file_name="scraped_links.csv",
            mime="text/csv",
        )

        st.download_button(
            "Download JSON",
            data=pd.Series(json_payload).to_json(indent=2),
            file_name="scraped_data.json",
            mime="application/json",
        )
        st.markdown("</div>", unsafe_allow_html=True)

else:
    st.markdown(
        """
        <div class="card">
            <h3>How it works</h3>
            <p class="muted">
                1. Enter a public webpage URL<br>
                2. Click <b>Scrape</b><br>
                3. View extracted text, links, tables, and keyword insights
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.caption("Use this only on pages you are allowed to scrape. Some websites block automated requests.")