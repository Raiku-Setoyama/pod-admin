"""Manufacturing data repository for database operations."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.manufacturing_data import ManufacturingData, MfgDataStatus

# 行を「手つかずの生成待ち」へ戻すときに書く値。
#
# **4 か所が同じ状態を作っていた**（手動リトライ・再作成/元画像差し替え・失敗行の再受注・
# 一括リトライ）。再試行まわりの列が増えるたびに 4 か所を直すことになり、
# 1 か所忘れると「戻したのに前回の試行回数を引きずる」という気づきにくい形で残る。
# **正本をここに 1 つ置き、ORM 経由の 3 か所は reset_to_pending() を通す。**
_PENDING_RESET_VALUES: dict[str, Any] = {
    "status": MfgDataStatus.PENDING.value,
    "error_message": None,
    # 人の判断による仕切り直しなので、到達不能の数え直しも待ち時間も手放す。
    "attempts": 0,
    "next_attempt_at": None,
    "lease_expires_at": None,
}


def retry_delay_interval(attempts: Any) -> Any:
    """試行回数から再試行までの待ち時間を作る（SQL 式）.

    **サービス側の ``ManufacturingDataService._retry_delay`` と同じ形である。**
    あちらは Python で 1 件ぶんを計算し、こちらは SQL で一括に適用する。
    片方だけ変えると、生成の失敗で戻した行とクラッシュで戻した行で間隔が食い違う。
    """
    seconds = func.least(
        settings.MFG_RETRY_BASE_SECONDS
        * func.pow(2, func.greatest(attempts - 1, 0)),
        settings.MFG_RETRY_MAX_SECONDS,
    )
    return func.make_interval(0, 0, 0, 0, 0, 0, seconds)


def reset_to_pending(md: ManufacturingData) -> None:
    """読み込み済みの行を、手つかずの生成待ちへ戻す（永続化は呼び出し側）."""
    for field, value in _PENDING_RESET_VALUES.items():
        setattr(md, field, value)


class ManufacturingDataRepository:
    """Repository for ManufacturingData model."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_id(self, mfg_data_id: str) -> ManufacturingData | None:
        """Find a manufacturing data row by ID."""
        result = await self._db.execute(
            select(ManufacturingData).where(ManufacturingData.id == mfg_data_id)
        )
        return result.scalar_one_or_none()

    async def claim_next_generation(
        self, lease_seconds: float
    ) -> tuple[str, datetime] | None:
        """生成待ちの最も古い 1 行を確保して generating にし、``(id, リース期限)`` を返す.

        生成待ちが無ければ None。

        **これがキューからの取り出しである。**候補の選択・確保・リースの付与を 1 つの文で
        行うので、複数のワーカーが同時に走っても同じ行を 2 度取り出すことはない
        （``FOR UPDATE SKIP LOCKED`` が、他のワーカーが掴んでいる行を黙って飛ばす）。

        リースの期限は、その行を「今まさに処理している」と見なす期限である。期限を過ぎても
        generating のままなら、処理していたワーカーが落ちたと判断できる
        （→ reclaim_expired_generation_leases）。

        **返すリース期限は、その所有権の証明として使う。**結果を書き戻すときにこの値を
        添えれば、リースが失効して別のワーカーに再確保された行を、古いワーカーが
        上書きしてしまうことを防げる（→ finish_generation）。
        """
        oldest_pending = (
            select(ManufacturingData.id)
            .where(
                ManufacturingData.status == MfgDataStatus.PENDING.value,
                # 再試行の予定時刻が来ていない行は飛ばす。NULL は「今すぐ対象」。
                # **これが待ち行列の先頭詰まりを防いでいる。** 到達不能で戻された行は
                # 予定時刻ぶん後ろに下がるので、後続の行が先に処理される。
                or_(
                    ManufacturingData.next_attempt_at.is_(None),
                    ManufacturingData.next_attempt_at <= func.now(),
                ),
            )
            .order_by(ManufacturingData.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        result = await self._db.execute(
            update(ManufacturingData)
            .where(ManufacturingData.id == oldest_pending)
            .values(
                status=MfgDataStatus.GENERATING.value,
                attempts=ManufacturingData.attempts + 1,
                error_message=None,
                # 確保した時点で予定は消化済み。**残すとリース失効で戻ってきた行が
                # 過去の予定を引きずり**、再開の判定が読めなくなる。
                next_attempt_at=None,
                lease_expires_at=func.now() + timedelta(seconds=lease_seconds),
            )
            .returning(ManufacturingData.id, ManufacturingData.lease_expires_at)
            .execution_options(synchronize_session=False)
        )
        row = result.first()
        return None if row is None else (row[0], row[1])

    async def finish_generation(
        self, mfg_data_id: str, *, lease_token: datetime, values: dict[str, Any]
    ) -> bool:
        """リースを保持している間だけ、生成結果を書き戻してリースを外す.

        ``lease_token`` は claim_next_generation が返したリース期限である。
        書き戻しの時点でこの値が一致していなければ、**リースが失効して別のワーカーが
        再確保した後**ということなので、何も書かずに False を返す。

        これが無いと、期限を誤って短く設定したときに、古いワーカーの結果が新しい
        ワーカーの処理を静かに上書きする（しかも誰も気づけない）。
        """
        result = await self._db.execute(
            update(ManufacturingData)
            .where(
                ManufacturingData.id == mfg_data_id,
                ManufacturingData.lease_expires_at == lease_token,
            )
            .values(**values, lease_expires_at=None)
            .returning(ManufacturingData.id)
            .execution_options(synchronize_session=False)
        )
        return result.scalars().first() is not None

    async def reclaim_expired_leases(self) -> int:
        """リースが切れた generating 行を pending へ戻し、戻した件数を返す.

        **この判定は、ワーカーが何本走っているかに依存しない。**期限内のリースを持つ行は
        誰かが処理中なので触らない。リースを持たない generating は、リース導入前に確保された
        行（または確保直後に落ちた行）なので、期限切れとして扱う。

        pending の行は対象にしない。戻す必要が無いうえ、同じ値で UPDATE すると
        バックログ全件の updated_at が動き、戻した件数も読めなくなる。

        **戻すときは再試行の間隔を空ける。** 間隔を空けないと、ワーカーを落とす行
        （巨大な画像で OOM になる等）が即座に取り直され、しかも取り出しは古い順なので
        待ち行列の先頭に居座り続ける。**後続のすべてがその 1 行で止まる。**
        生成の途中で落ちた行は ``_handle_failure`` を通らないので、
        ここが唯一の歯止めである。

        間隔は ``attempts`` から導く（確保のたびに増えるので、何度も落ちている行ほど
        後ろへ下がる）。1 度きりのクラッシュなら 1 回目の間隔で戻ってくる。
        """
        result = await self._db.execute(
            update(ManufacturingData)
            .where(
                ManufacturingData.status == MfgDataStatus.GENERATING.value,
                or_(
                    ManufacturingData.lease_expires_at.is_(None),
                    ManufacturingData.lease_expires_at < func.now(),
                ),
            )
            .values(
                status=MfgDataStatus.PENDING.value,
                lease_expires_at=None,
                next_attempt_at=func.now() + retry_delay_interval(
                    ManufacturingData.attempts
                ),
            )
            .execution_options(synchronize_session=False)
        )
        # RETURNING で id を運ばない。**件数しか使っていない。**
        # UPDATE の戻りは実体としては CursorResult だが、async の execute() は
        # 総称の Result として型付けされているため、ここで絞る。
        return cast(CursorResult[Any], result).rowcount

    async def retry_failed(self, ids: list[str] | None = None) -> int:
        """失敗した生成を待ち行列へ戻し、戻した件数を返す.

        ``ids`` を渡せばその行だけ、渡さなければ ``failed`` の全行が対象になる。

        **対象は failed だけである。** ready/generating/pending を巻き戻すと、その行を
        共有する他の注文の発注可否まで劣化する（ManufacturingDataService.retry と同じ理由）。

        書き戻す値は _PENDING_RESET_VALUES が正本である（ORM 経由の 3 か所と揃える）。
        """
        conditions = [ManufacturingData.status == MfgDataStatus.FAILED.value]
        if ids is not None:
            if not ids:
                return 0
            conditions.append(ManufacturingData.id.in_(ids))

        result = await self._db.execute(
            update(ManufacturingData)
            .where(*conditions)
            .values(**_PENDING_RESET_VALUES)
            .execution_options(synchronize_session=False)
        )
        # RETURNING で id を運ばない。**件数しか使っていない。** VM 停止明けの
        # 一括復旧はこの経路が本命で、そこが最も行数の多い呼び出しになる。
        return cast(CursorResult[Any], result).rowcount

    async def count_by_status(self) -> dict[str, int]:
        """ステータスごとの件数を返す（管理画面の集計用）.

        **絞り込みを掛けない全件集計である。** 一覧が failed だけを映していても
        「いま全体で何件溜まっているか」を出すためで、それがこの画面の用途だからである。

        この表は**受注ごとではなく商品ごと**に 1 行を持つキャッシュ
        （受注元 × 商品コード × サイズ × バリアント）なので、行数は商品の種類数で頭打ちになり、
        受注が増えても伸びない。**受注量に比例して重くなる類の集計ではない。**
        伸び始めたら status に索引があるので、部分集計へ落とす余地も残っている。
        """
        result = await self._db.execute(
            select(ManufacturingData.status, func.count(ManufacturingData.id)).group_by(
                ManufacturingData.status
            )
        )
        return dict(result.tuples().all())

    async def find_by_cache_key(
        self,
        order_source_id: str | None,
        product_code: str,
        size: str | None,
        variant: str | None,
    ) -> ManufacturingData | None:
        """Find manufacturing data by cache key (order_source × product_code × size × variant).

        NULL の size/variant は NULL 同士で一致させる（キャッシュ一意制約と整合）。
        """
        conditions = [
            ManufacturingData.product_code == product_code,
            _eq_or_null(ManufacturingData.order_source_id, order_source_id),
            _eq_or_null(ManufacturingData.size, size),
            _eq_or_null(ManufacturingData.variant, variant),
        ]
        result = await self._db.execute(
            select(ManufacturingData).where(and_(*conditions))
        )
        return result.scalar_one_or_none()

    async def create(self, mfg_data: ManufacturingData) -> ManufacturingData:
        """Create a new manufacturing data row."""
        self._db.add(mfg_data)
        await self._db.flush()
        await self._db.refresh(mfg_data)
        return mfg_data

    async def update(self, mfg_data: ManufacturingData) -> ManufacturingData:
        """Persist changes to a manufacturing data row."""
        await self._db.flush()
        await self._db.refresh(mfg_data)
        return mfg_data

    async def list(
        self,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
        order_source_id: str | None = None,
        product_code: str | None = None,
    ) -> tuple[list[ManufacturingData], int]:
        """List manufacturing data rows with pagination and filters."""
        # 条件を一度だけ組み立て、本体クエリと件数クエリの双方に適用する
        conditions = []
        if status:
            conditions.append(ManufacturingData.status == status)
        if order_source_id:
            conditions.append(ManufacturingData.order_source_id == order_source_id)
        if product_code:
            conditions.append(ManufacturingData.product_code == product_code)

        query = select(ManufacturingData).where(*conditions)
        count_query = select(func.count(ManufacturingData.id)).where(*conditions)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * limit
        query = (
            query.order_by(ManufacturingData.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._db.execute(query)
        return list(result.scalars().all()), total


def _eq_or_null(column: Any, value: Any) -> Any:
    """value が None なら IS NULL、そうでなければ等価比較を返す."""
    if value is None:
        return column.is_(None)
    return column == value
