# Tシャツ 左胸ワンポイント 実装計画（pod-admin 側）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tシャツの position に「左胸」を足し、製造データをテンプレート右上の 100×100mm の枠に生成する（REQ-0070）。
設計の正本は rksyo の `docs/superpowers/specs/2026-10-19-left-chest-onepoint-tshirt-design.md` §5.1。

**Architecture:** position は `TshirtPosition` enum に 1 値足すだけで options・受注バリデーションに伝わる。
生成の振り分けは `manufacturing_data.variant`（`left_chest` / NULL）に載せ、position 列は足さない。
`build_generation_spec` が position → variant を決め、runner が variant で箱を選ぶ。

**Tech Stack:** FastAPI / SQLAlchemy / VectorCraft（`app/generator`）/ pytest

---

### Task 1: `TshirtPosition.LEFT_CHEST`

**Files:** `api/app/models/order.py`, `api/tests/unit/test_external_product_options.py`（新規）

- [ ] options に `["正面", "左胸"]` が出るテストと、`左胸` が受注バリデーションを通るテストを書く → 失敗
- [ ] enum に `LEFT_CHEST = "左胸"` を足す → 成功

### Task 2: マッピング（position → variant）

**Files:** `api/app/utils/mfg_product_mapping.py`, `api/tests/unit/test_mfg_product_mapping.py`

- [ ] テスト: tshirt+左胸 → `variant == "left_chest"`、正面/None → `None`、未知 → `MfgMappingError`、
  tote_bag+左胸 → `MfgMappingError`、`position_from_variant` の往復
- [ ] `build_generation_spec(..., position=None)` と `position_from_variant(product_type, variant)` を実装

### Task 3: サービスに position を通す

**Files:** `api/app/services/manufacturing_data_service.py`, `api/tests/unit/test_manufacturing_data_service.py`

- [ ] テスト: 左胸の明細で `find_by_cache_key(..., "left_chest")` が呼ばれ、行の variant が `left_chest`。
  行（variant `left_chest`）からの再生成で spec.variant が `left_chest`
- [ ] `_resolve_or_create` が `item.position`、`generate` が `position_from_variant(md.variant)` を渡す

### Task 4: 生成（右上 100×100mm の箱）

**Files:** `api/app/generator/pipelines.py`, `api/app/generator/runner.py`, `api/tests/generator/test_vectorcraft.py`,
`api/tests/unit/test_generator_tshirt_variant.py`（新規）

- [ ] 単体テスト（CLI 不要）: 箱の計算 `tshirt_left_chest_box(artboard)` が右上に接する 283.46pt 角、
  runner が未知の variant で `GenerationError`
- [ ] 生成テスト（CLI があるときだけ）: 左胸の PDF で画像の `cm` 行列が箱（余白 1mm）に収まり、
  ファイル名・用紙サイズ・ICC が正面と同じ
- [ ] `TSHIRT_LEFT_CHEST_AREA_PT = 100 * MM`、`tshirt(job, image, name, variant=None)` で箱を選ぶ

### Task 5: seed・文書・フィクスチャ

- [ ] `api/scripts/seed.py` / `seed_operation_test.py` に (tshirt, S/M/L/XL, 左胸, 白) の 4 行
- [ ] `api/docs/order-api.md` と `docs/external-api.md` に `左胸`
- [ ] `api/tests/generator/fixtures/` にワンポイント版サンプル PDF（L）1 枚

### Task 6: 重ね合わせの確認

- [ ] ワーカー用イメージ（`pod-admin-worker-test`）で生成テストを回し、出力 PDF の画像の位置を
  サンプル PDF と比較して PR に書く

### Task 7: 品質検証・PR

- [ ] `/quality-gate` → `feat(generator): ...` でコミット → PR（反映順の注意・商品マスタの運用を本文に）
