"""storage モジュールのユニットテスト（zh-cn n-gram 検索含む）"""
import sqlite3
import unittest

from docbot.storage import (
    _query_to_ngrams_cjk,
    _normalize_cjk,
    open_db,
    upsert_page,
    search_index,
    SCHEMA,
)


class TestQueryToNgramsCjk(unittest.TestCase):
    """zh-cn 用 n-gram クエリ生成のテスト"""

    def test_cjk_2chars_or_more_returns_ngram_or_query(self):
        """CJK 2文字以上 → ngram OR クエリが返る"""
        result = _query_to_ngrams_cjk("插件管理")
        self.assertIsNotNone(result)
        self.assertIn(" OR ", result)
        self.assertTrue(result.count('"') >= 4)

    def test_cjk_1char_returns_none(self):
        """CJK 1文字 → None（フォールバック用）"""
        self.assertIsNone(_query_to_ngrams_cjk("插"))

    def test_cjk_empty_returns_none(self):
        """CJK 0文字（英数字のみ） → None"""
        self.assertIsNone(_query_to_ngrams_cjk("plugin"))
        self.assertIsNone(_query_to_ngrams_cjk("ab"))

    def test_cjk_mixed_extracts_and_uses_cjk(self):
        """混在クエリから CJK のみ抽出して ngram 生成"""
        result = _query_to_ngrams_cjk("插件 plugin 管理")
        self.assertIsNotNone(result)
        self.assertIn(" OR ", result)


class TestZhCnSearch(unittest.TestCase):
    """zh-cn 検索の E2E テスト（インメモリ DB）"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(SCHEMA)

    def tearDown(self):
        self.conn.close()

    def test_zh_cn_ngram_search_finds_page(self):
        """zh-cn で CJK 2文字以上 → ngram 検索でヒット"""
        url = "https://example.com/zh-cn/plugins.md"
        title = "插件管理"
        ngrams = "插件 件管 管理 理"
        upsert_page(
            self.conn, url, "zh-cn", title, "", "插件管理", "", "", ngrams, 0
        )
        hits = search_index(self.conn, "插件", lang="zh-cn", limit=5)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], title)
        self.assertIsNotNone(hits[0]["score"])

    def test_zh_cn_fallback_single_char(self):
        """zh-cn で CJK 1文字 → unicode フォールバックでヒット"""
        url = "https://example.com/zh-cn/single.md"
        title = "插"
        upsert_page(self.conn, url, "zh-cn", title, "", "", "", "插", "", 0)
        hits = search_index(self.conn, "插", lang="zh-cn", limit=5)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], title)


class TestJaJpEnUsUnchanged(unittest.TestCase):
    """ja-jp / en-us の既存挙動が変わっていないことを確認"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(SCHEMA)

    def tearDown(self):
        self.conn.close()

    def test_ja_jp_ngram_search_still_works(self):
        """ja-jp は従来どおり ngram 検索"""
        url = "https://example.com/ja-jp/intro.md"
        upsert_page(
            self.conn, url, "ja-jp", "はじめに", "", "", "", "",
            "はじ じめ めに", 0
        )
        hits = search_index(self.conn, "はじめに", lang="ja-jp", limit=5)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], "はじめに")

    def test_en_us_search_still_works(self):
        """en-us は従来どおり BM25 検索"""
        url = "https://example.com/en-us/intro.md"
        upsert_page(self.conn, url, "en-us", "Introduction", "", "", "", "", "", 0)
        hits = search_index(self.conn, "Introduction", lang="en-us", limit=5)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], "Introduction")
