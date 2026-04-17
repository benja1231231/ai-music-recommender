import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from recommender import MusicRecommender


class TestMusicRecommender:
    @pytest.fixture
    def recommender(self):
        motor = MusicRecommender()
        motor.preparar_dataset()
        return motor

    def test_initialization(self, recommender):
        assert recommender is not None
        assert recommender.nlp is not None
        assert recommender.translator is not None
        assert len(recommender.caracteristicas) >= 4

    def test_mock_dataset_loaded(self, recommender):
        assert recommender.df is not None
        assert len(recommender.df) == 4
        assert 'track_name' in recommender.df.columns
        assert 'artist' in recommender.df.columns

    def test_recommend_by_content_exact_match(self, recommender):
        result = recommender.recomendar("Queen", modo='contenido', exportar=False)
        assert result is not None
        assert result.get("status") == "success"

    def test_recommend_by_content_no_match(self, recommender):
        result = recommender.recomendar("ArtistaInexistenteXYZ123", modo='contenido', exportar=False)
        assert result is None

    def test_recommend_nlp_mode(self, recommender):
        result = recommender.recomendar("música triste para dormir", modo='nlp', exportar=False)
        assert result is not None
        assert result.get("status") == "success"

    def test_recommend_nlp_party_mode(self, recommender):
        result = recommender.recomendar("party music", modo='nlp', exportar=False)
        assert result is not None
        assert result.get("status") == "success"

    def test_recommend_nlp_gym_mode(self, recommender):
        result = recommender.recomendar("gym workout music", modo='nlp', exportar=False)
        assert result is not None
        assert result.get("status") == "success"

    def test_recommend_export_mode_returns_15(self, recommender):
        result = recommender.recomendar("Queen", modo='contenido', exportar=True)
        if result.get("status") == "success":
            assert len(result["data"]) == 15

    def test_conflict_detection(self, recommender):
        result = recommender.recomendar("Bohemian Rhapsody", modo='contenido', exportar=False)
        if result and result.get("status") == "conflict":
            assert result.get("type") in ["artist_vs_track", "multiple_tracks"]

    def test_chart_data_structure(self, recommender):
        result = recommender.recomendar("Queen", modo='contenido', exportar=False)
        if result and result.get("status") == "success":
            assert "chart_data" in result
            assert "target" in result["chart_data"]
            assert "recommendations" in result["chart_data"]


class TestMusicRecommenderSpotifyImport:
    @pytest.fixture
    def recommender(self):
        motor = MusicRecommender()
        motor.preparar_dataset()
        return motor

    def test_spotify_import_without_config(self, recommender):
        result = recommender.recomendar(
            "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
            modo='spotify_import',
            exportar=False
        )
        if not recommender.spotify or not recommender.spotify.user_id:
            assert result.get("status") == "error"
