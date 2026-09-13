"""Unit tests for ReviewService."""


class TestReviewService:
    """Tests for ReviewService."""

    def test_get_next_word_returns_due_word(self, word_service, review_service):
        """Test getting next word for review."""
        word_service.add_word("test", translation="тест")

        next_word = review_service.get_next_word()
        assert next_word is not None

    def test_review_word(self, word_service, review_service):
        """Test that review records the review."""
        word = word_service.add_word("review", translation="проверка")

        review_service.review_word(word.id)

    def test_skip_word(self, word_service, review_service):
        """Test that skip records the review."""
        word = word_service.add_word("skipme", translation="пропустить")

        review_service.skip_word(word.id)

    def test_get_stats_returns_dict(self, review_service):
        """Test getting statistics."""
        stats = review_service.get_stats()

        assert isinstance(stats, dict)
        assert "total_words" in stats
        assert "today_reviews" in stats
        assert "streak" in stats

    def test_get_language_counts(self, word_service, review_service):
        """Test getting language counts."""
        word_service.add_word("counttest", translation="тест")

        counts = review_service.get_language_counts()
        assert isinstance(counts, dict)

    def test_get_next_word_least_seen_first(self, word_service, review_service):
        """Test that words with fewer reviews appear first."""
        word1 = word_service.add_word("word1", translation="w1")
        word_service.add_word("word2", translation="w2")
        word_service.add_word("word3", translation="w3")

        first = review_service.get_next_word()
        assert first is not None

        review_service.review_word(word1.id)

        second = review_service.get_next_word()
        assert second is not None
        assert second.id != word1.id

    def test_new_word_appears_before_reviewed(self, word_service, review_service):
        """Test that never-reviewed words appear before reviewed ones."""
        word_service.add_word("alpha", translation="а")
        word_service.add_word("beta", translation="б")

        first = review_service.get_next_word()
        first_id = first.id

        review_service.review_word(first_id)

        second = review_service.get_next_word()

        assert second.id != first_id

    def test_get_next_word_returns_word_when_available(self, word_service, review_service):
        """Test that get_next_word returns a word when one exists."""
        word_service.add_word("available", translation="доступный")

        result = review_service.get_next_word()
        assert result is not None

    def test_equal_counts_broken_by_oldest_last_reviewed(self):
        """Sort contract is (review_count, last_reviewed): ties go to oldest."""
        from unittest.mock import MagicMock

        from application.review_service import ReviewService
        from domain.entities import Word

        word_repo = MagicMock()
        stats_repo = MagicMock()
        settings_service = MagicMock()
        settings_service.get_target_lang.return_value = "ru"
        word_repo.get_for_review.return_value = [
            Word(id=1, phrase="newer", last_reviewed=200),
            Word(id=2, phrase="older", last_reviewed=100),
        ]
        stats_repo.get_review_counts.return_value = {1: 1, 2: 1}

        service = ReviewService(word_repo, stats_repo, settings_service)

        assert service.get_next_word().id == 2

    def test_fewer_reviews_beats_older_timestamp(self):
        """Review count is the primary key, last_reviewed only breaks ties."""
        from unittest.mock import MagicMock

        from application.review_service import ReviewService
        from domain.entities import Word

        word_repo = MagicMock()
        stats_repo = MagicMock()
        settings_service = MagicMock()
        settings_service.get_target_lang.return_value = "ru"
        word_repo.get_for_review.return_value = [
            Word(id=1, phrase="old-often-reviewed", last_reviewed=100),
            Word(id=2, phrase="new-once-reviewed", last_reviewed=200),
        ]
        stats_repo.get_review_counts.return_value = {1: 5, 2: 1}

        service = ReviewService(word_repo, stats_repo, settings_service)

        assert service.get_next_word().id == 2

    def test_fewer_reviews_wins_beyond_candidate_limit(self, word_service, review_service, test_db):
        from infrastructure.models import History, WordStats

        for index in range(50):
            word = word_service.add_word(f"old{index}", "translation")
            test_db.session.add(WordStats(word_id=word.id, last_reviewed=1))
            test_db.session.add_all([
                History(word_id=word.id, reviewed_at=timestamp) for timestamp in (1, 2)
            ])
        newer = word_service.add_word("newer", "translation")
        test_db.session.add(WordStats(word_id=newer.id, last_reviewed=100))
        test_db.session.add(History(word_id=newer.id, reviewed_at=100))
        test_db.commit()

        assert review_service.get_next_word().id == newer.id
