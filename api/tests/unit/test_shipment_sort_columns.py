"""REQ-0049: 配送一覧の並び替えキーの組み立て.

ステータスの並びは業務上の進行順（配送準備待ち → 配送準備完了 → 発送完了）にする。
値の文字列（pending / ready / shipped）は辞書順でも同じ並びになってしまうため、
「辞書順ではなく CASE で並べている」ことはデータからは確かめられない。ここで見る。
"""

from sqlalchemy import Case

from app.models.shipment import Shipment, ShipmentStatus
from app.repositories.shipment_repository import _STATUS_SORT_POSITION, _sort_column


class TestStatusSortOrder:
    def test_status_is_sorted_by_case_expression_not_by_raw_column(self) -> None:
        """ステータスの並び替えキーは CASE 式であり、列の値そのものではない."""
        column = _sort_column("status")

        assert isinstance(column, Case)

    def test_status_positions_follow_business_progression(self) -> None:
        """配送準備待ち → 配送準備完了 → 発送完了 の順に並ぶ位置が振られている."""
        positions = [
            _STATUS_SORT_POSITION[status.value]
            for status in (
                ShipmentStatus.PENDING,
                ShipmentStatus.READY,
                ShipmentStatus.SHIPPED,
            )
        ]

        assert positions == sorted(positions)
        assert len(set(positions)) == len(positions)

    def test_every_status_has_a_position(self) -> None:
        """ステータスを増やしたときに、位置の割り当て漏れをここで検知する."""
        assert set(_STATUS_SORT_POSITION) == {status.value for status in ShipmentStatus}


class TestSortColumnFallback:
    def test_unknown_sort_by_falls_back_to_created_at(self) -> None:
        """未知の `sort_by` は作成日にフォールバックする."""
        assert _sort_column("no_such_column") is Shipment.created_at

    def test_known_columns_are_mapped(self) -> None:
        """画面から指定できる 5 列すべてにキーがある."""
        for sort_by in (
            "created_at",
            "estimated_shipping_date",
            "status",
            "order_number",
            "customer_name",
        ):
            assert _sort_column(sort_by) is not None
