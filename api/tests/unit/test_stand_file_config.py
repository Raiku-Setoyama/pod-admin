"""StandFileConfig のユニットテスト

FEAT-0012: アクリルフィギュアのスタンドファイル設定

テスト対象: stand_file_config モジュール
- get_stand_file_path() がデフォルトファイルパスを返す
- サイズ指定時に正しいファイルパスを返す
- 未定義サイズ時にデフォルトにフォールバックする
- サイズ別マッピングの設定構造が拡張可能である
"""

import pytest

from app.utils.stand_file_config import (
    get_stand_file_path,
    STAND_FILE_MAPPING,
    DEFAULT_STAND_FILE_PATH,
)


class TestGetStandFilePath:
    """get_stand_file_path() のテスト"""

    def test_returns_default_when_no_size_given(self):
        """サイズ未指定時にデフォルトのスタンドファイルパスを返す

        given: サイズ引数なし（None）
        when: get_stand_file_path() を呼ぶ
        then: DEFAULT_STAND_FILE_PATH が返る
        """
        result = get_stand_file_path()
        assert result == DEFAULT_STAND_FILE_PATH

    def test_returns_default_when_size_is_none(self):
        """サイズが None の場合にデフォルトを返す

        given: size=None
        when: get_stand_file_path(size=None) を呼ぶ
        then: DEFAULT_STAND_FILE_PATH が返る
        """
        result = get_stand_file_path(size=None)
        assert result == DEFAULT_STAND_FILE_PATH

    def test_returns_mapped_path_for_known_size(self):
        """マッピングに登録済みのサイズで正しいパスを返す

        given: STAND_FILE_MAPPING にサイズが登録されている
        when: そのサイズで get_stand_file_path() を呼ぶ
        then: マッピングされたパスが返る
        """
        # STAND_FILE_MAPPING に少なくとも1つのエントリがあることを前提
        if STAND_FILE_MAPPING:
            first_size = next(iter(STAND_FILE_MAPPING))
            expected_path = STAND_FILE_MAPPING[first_size]
            result = get_stand_file_path(size=first_size)
            assert result == expected_path

    def test_fallback_to_default_for_unknown_size(self):
        """未定義サイズ時にデフォルトにフォールバック

        given: STAND_FILE_MAPPING に存在しないサイズ
        when: get_stand_file_path(size="999x999mm") を呼ぶ
        then: DEFAULT_STAND_FILE_PATH が返る
        """
        result = get_stand_file_path(size="999x999mm")
        assert result == DEFAULT_STAND_FILE_PATH

    def test_returns_string_path(self):
        """戻り値が文字列であること"""
        result = get_stand_file_path()
        assert isinstance(result, str)

    def test_default_path_is_not_empty(self):
        """デフォルトパスが空でないこと"""
        assert DEFAULT_STAND_FILE_PATH
        assert len(DEFAULT_STAND_FILE_PATH) > 0


class TestStandFileMapping:
    """STAND_FILE_MAPPING の構造テスト"""

    def test_mapping_is_dict(self):
        """マッピングが辞書型であること"""
        assert isinstance(STAND_FILE_MAPPING, dict)

    def test_mapping_keys_are_strings(self):
        """マッピングのキー（サイズ）が文字列であること"""
        for key in STAND_FILE_MAPPING:
            assert isinstance(key, str), f"Key '{key}' is not a string"

    def test_mapping_values_are_strings(self):
        """マッピングの値（ファイルパス）が文字列であること"""
        for key, value in STAND_FILE_MAPPING.items():
            assert isinstance(value, str), f"Value for key '{key}' is not a string"

    def test_default_stand_file_path_is_defined(self):
        """DEFAULT_STAND_FILE_PATH が定義されている"""
        assert DEFAULT_STAND_FILE_PATH is not None
