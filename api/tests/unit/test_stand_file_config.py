"""StandFileConfig のユニットテスト

FEAT-0012: アクリルフィギュアのスタンドファイル設定

テスト対象: stand_file_config モジュール
- get_stand_file_path() がサイズに応じたフルパスを返す
- load_stand_file() がファイル内容を返す / ファイルがなければ None を返す
"""

from pathlib import Path

from app.utils.stand_file_config import (
    get_stand_file_path,
    load_stand_file,
    STAND_FILE_MAPPING,
    STAND_TEMPLATES_DIR,
    DEFAULT_STAND_FILENAME,
)


class TestGetStandFilePath:
    """get_stand_file_path() のテスト"""

    def test_returns_default_when_no_size_given(self):
        """サイズ未指定時にデフォルトのスタンドファイルパスを返す"""
        result = get_stand_file_path()
        assert result == STAND_TEMPLATES_DIR / DEFAULT_STAND_FILENAME

    def test_returns_default_when_size_is_none(self):
        """サイズが None の場合にデフォルトを返す"""
        result = get_stand_file_path(size=None)
        assert result == STAND_TEMPLATES_DIR / DEFAULT_STAND_FILENAME

    def test_returns_mapped_path_for_known_size(self):
        """マッピングに登録済みのサイズで正しいパスを返す"""
        result = get_stand_file_path(size="50x50mm")
        assert result == STAND_TEMPLATES_DIR / STAND_FILE_MAPPING["50x50mm"]

    def test_fallback_to_default_for_unknown_size(self):
        """未定義サイズ時にデフォルトにフォールバック"""
        result = get_stand_file_path(size="999x999mm")
        assert result == STAND_TEMPLATES_DIR / DEFAULT_STAND_FILENAME

    def test_returns_path_object(self):
        """戻り値が Path であること"""
        result = get_stand_file_path()
        assert isinstance(result, Path)


class TestLoadStandFile:
    """load_stand_file() のテスト"""

    def test_returns_content_when_file_exists(self, tmp_path, monkeypatch):
        """ファイルが存在する場合に内容を返す"""
        template_dir = tmp_path / "stand_templates"
        template_dir.mkdir()
        template_file = template_dir / DEFAULT_STAND_FILENAME
        template_file.write_bytes(b"AI_FILE_CONTENT")

        monkeypatch.setattr(
            "app.utils.stand_file_config.STAND_TEMPLATES_DIR", template_dir
        )

        result = load_stand_file()
        assert result == b"AI_FILE_CONTENT"

    def test_returns_none_when_file_not_found(self, tmp_path, monkeypatch):
        """ファイルが存在しない場合に None を返す"""
        template_dir = tmp_path / "stand_templates"
        template_dir.mkdir()

        monkeypatch.setattr(
            "app.utils.stand_file_config.STAND_TEMPLATES_DIR", template_dir
        )

        result = load_stand_file()
        assert result is None

    def test_returns_correct_file_for_size(self, tmp_path, monkeypatch):
        """サイズ指定時に対応するファイルの内容を返す"""
        template_dir = tmp_path / "stand_templates"
        template_dir.mkdir()
        template_file = template_dir / STAND_FILE_MAPPING["100x100mm"]
        template_file.write_bytes(b"100MM_CONTENT")

        monkeypatch.setattr(
            "app.utils.stand_file_config.STAND_TEMPLATES_DIR", template_dir
        )

        result = load_stand_file(size="100x100mm")
        assert result == b"100MM_CONTENT"


class TestStandFileMapping:
    """STAND_FILE_MAPPING の構造テスト"""

    def test_mapping_is_dict(self):
        """マッピングが辞書型であること"""
        assert isinstance(STAND_FILE_MAPPING, dict)

    def test_mapping_keys_are_strings(self):
        """マッピングのキー（サイズ）が文字列であること"""
        for key in STAND_FILE_MAPPING:
            assert isinstance(key, str)

    def test_mapping_values_are_strings(self):
        """マッピングの値（ファイル名）が文字列であること"""
        for value in STAND_FILE_MAPPING.values():
            assert isinstance(value, str)

    def test_all_filenames_end_with_ai(self):
        """全ファイル名が .ai で終わること"""
        for value in STAND_FILE_MAPPING.values():
            assert value.endswith(".ai")
        assert DEFAULT_STAND_FILENAME.endswith(".ai")
