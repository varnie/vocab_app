"""Unit tests for StatsRepository totals."""


class TestGetStatsTotals:
    """Total word counts must include words without translations."""

    def test_total_includes_words_without_translation(self, test_db, word_repo, stats_repo):
        """Regression: INNER JOIN used to hide untranslated words from totals."""
        word_repo.save_word("lonely", None, "ru")
        word_with = word_repo.save_word("paired", None, "ru")
        word_repo.add_translation(word_with.id, "перевод", "ru")

        stats = stats_repo.get_stats()

        assert stats.total_words >= 2

    def test_today_words_includes_untranslated(self, test_db, word_repo, stats_repo):
        """Words added today without translation count towards today_words."""
        word_repo.save_word("fresh-no-translation", None, "ru")

        stats = stats_repo.get_stats()

        assert stats.today_words >= 1
