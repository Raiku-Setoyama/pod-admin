"""製造データ生成（REQ-0067 / ADR-0039）.

元データの画像から、製造委託先に渡す製造データ（.ai／.pdf）を作る。以前は Windows VM 上の
Adobe Illustrator（illustrator-vm）が作っていたものを、OSS の VectorCraft で同じ手順のまま作る。

**生成はワーカー（``app.worker``）だけが行う。** 依存（VectorCraft の実行ファイル、
numpy / scipy / pypdf）はワーカー用のイメージにだけ入っており、API のイメージには無い。
そのため、このパッケージの入口（``__init__``）と ``errors`` は重い依存を読み込まない。
生成の本体（``runner``）は、使う関数の中で import すること。

- ``runner``: ``generate``（1 件作る）と ``check_available``（死活確認）
- ``pipelines``: 商品ごとの VectorCraft の操作（illustrator-vm の ExtendScript の移植）
- ``geometry``: カットラインのパス計算
- ``white_plate``: 白版画像の抜けを埋める
- ``legacy_ai``: Illustrator がレイヤー付きで開ける旧形式（Illustrator 8 形式）の .ai に書き直す
- ``pdf_finish``: T シャツ・トートの PDF を整える
"""
