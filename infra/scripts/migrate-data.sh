#!/usr/bin/env bash
# migrate-data.sh — 本番データを Railway から Cloud SQL へ移すための道具（REQ-0054）。
#
# **カットオーバーの手順 3 を、当日その場で組み立てないための script である。**
# 事前にリハーサルで通し、当日は同じコマンドを同じ順で叩くだけにする。
#
#   counts   <PGURL>              全テーブルの行数を出す（読み取りのみ）
#   dump     <PGURL> <OUT>        pg_dump を取る（読み取りのみ）
#   reset    <PGURL>              public スキーマを作り直す（**破壊的**）
#   restore  <PGURL> <DUMP>       dump を流し込む（**破壊的**）
#   counts-dump <DUMP>            ダンプファイルから行数を数える（DB に繋がない）
#   compare  <SRC> <DST>          counts の出力 2 つを突合する（差があれば異常終了）
#
# ## 移送元を壊さないための作り
#
# 移送元と移送先の取り違えが、この作業で唯一取り返しのつかない事故である。
# **注意では防げないので、破壊的な操作は「許可した宛先」でしか動かない。**
#
# 除外（Railway ならやめる）ではなく許可（Cloud SQL Auth Proxy 越しの
# pod_admin だけ）にしてある。**除外は空振りしたときに通ってしまう** —
# 空文字を渡せば PG* 環境変数の既定接続に落ち、`railway run` の下では
# それが移送元そのものを指す。許可なら、想定外はすべて止まる。
#
# 逆向き（Cloud SQL から Railway へ）の操作はこの script に無い。
#
# ## macOS には psql が無い
#
# あればそれを使い、無ければ docker の postgres:17-alpine で実行する。
# **当日に初めて pull すると 400MB 超の取得が待ち時間になる。**
# 前日までに `docker pull postgres:17-alpine` を済ませておく。
set -euo pipefail

# 移送先の Cloud SQL に合わせる。正本は infra/modules/cloud-sql/main.tf の
# database_version（POSTGRES_17）。**client を server より古くしない。**
# 17 系のダンプは `\restrict` を含み、**psql 16 では解釈できない。**
readonly PG_IMAGE="postgres:17-alpine"

# 破壊的な操作を許可する宛先。Terraform が決めている値と揃える
# （infra/modules/stack/main.tf の cloud_sql: database_name / user_name）。
readonly ALLOWED_DB=pod_admin
readonly ALLOWED_USER=pod_admin

# 行番号で切り出すと、ヘッダを書き換えるたびに黙ってずれる（実際ずれていた）。
# 終端を特定のサブコマンド名にもしない。**そのコマンドを最後に置き続ける約束**が
# 生まれ、あとから足した人のぶんが黙って usage から消える。空コメント行で閉じる。
usage() { sed -n '/^#   counts /,/^#$/p' "$0" | sed '$d' >&2; exit 2; }

die() { echo "$*" >&2; exit 1; }

# 接続 URL を libpq の PG* 環境変数へ分解する。
#
# **URL をそのまま psql の引数に渡すと、パスワードが ps に出る。**
# libpq に「URL を読む環境変数」は無いので、自分で分解して環境変数に置く。
# docker のときは -e で名前だけ渡し、値をコマンド行に載せない
# （それでも docker inspect からは見える。そこまでは隠せない）。
parse_pgurl() {
  # **パスワードにシェルのメタ文字が入りうる**ので shlex で確実に括る。
  # Cloud SQL 側は `-_.~` しか使わせていないが（modules/cloud-sql）、
  # 移送元の Railway が何を使っているかはこちらで決められない。
  eval "$(python3 - "$1" <<'PYEOF'
import shlex, sys, urllib.parse as u
p = u.urlparse(sys.argv[1])
for k, v in (("PGHOST", p.hostname), ("PGPORT", p.port),
             ("PGUSER", u.unquote(p.username or "")),
             ("PGPASSWORD", u.unquote(p.password or "")),
             ("PGDATABASE", (p.path or "/").lstrip("/"))):
    if v not in (None, ""):
        print(f"export {k}={shlex.quote(str(v))}")
PYEOF
)"
  # **ホストが取れなければ、ここで止める。**
  # 空のまま進むと libpq が既定の Unix ソケットへ落ち、
  # 「/var/run/postgresql/.s.PGSQL.5432 が無い」という**接続先と無関係な
  # エラー**になる。原因（URL が空 / ホストが空）が読み取れない。
  #
  # Railway の DATABASE_PUBLIC_URL は、TCP プロキシを有効化していないと
  # `postgresql://user:pass@:/railway` のようにホストとポートが空で返る。
  if [ -z "${PGHOST-}" ]; then
    die "接続先のホストがありません。渡した URL を確認してください。
  - 変数が空ではないか（例: \$RAILWAY_DATABASE_URL が未設定）
  - ホストが空の URL ではないか（例: postgresql://user:pass@:/railway）
    Railway の DATABASE_PUBLIC_URL は TCP プロキシを有効化するまでこの形になる
  - 内部向けの URL ではないか（postgres.railway.internal は外から解決できない）"
  fi

  # cloud-sql-proxy はホスト側で待ち受ける。**コンテナの中の 127.0.0.1 は
  # コンテナ自身を指す**ので、docker を使うときだけ名前を差し替える。
  case "${PGHOST-}" in
    127.0.0.1|localhost|::1) PGHOST_IN_DOCKER=host.docker.internal ;;
    *)                       PGHOST_IN_DOCKER="${PGHOST-}" ;;
  esac
}

# psql / pg_dump を透過的に呼ぶ。第 1 引数がコマンド名、以降がその引数。
# **接続先は引数ではなく PG* 環境変数から取らせる。**
pg() {
  local cmd="$1"; shift
  if [ "$USE_DOCKER" = no ]; then
    "$cmd" "$@"
  else
    docker run --rm -i \
      -e "PGHOST=$PGHOST_IN_DOCKER" -e PGPORT -e PGUSER -e PGPASSWORD -e PGDATABASE \
      --add-host=host.docker.internal:host-gateway \
      --entrypoint "$cmd" "$PG_IMAGE" "$@"
  fi
}

# **破壊的な操作の宛先を、こちらから積極的に確かめる。**
#
# 手で書いた URL を眺めるだけでは足りない。**繋がった先のサーバに聞く。**
# 前日のステージング用 proxy が同じポートに残っていた、という事故が
# URL の見た目では区別できないためである。
assert_writable_target() {
  # 1. Cloud SQL へは Auth Proxy 経由でしか触らない。ループバック以外は宛先にしない
  # ホストが空の場合は parse_pgurl が既に落としている。
  case "$PGHOST" in
    127.0.0.1|localhost|::1) ;;
    *) die "拒否: 接続先 ${PGHOST} は Cloud SQL Auth Proxy ではありません。" ;;
  esac

  # 2. 実際に繋がった先の身元を確かめる。**移送元の Railway は railway/postgres
  #    であって pod_admin/pod_admin ではない**ので、ここで必ず止まる
  local who
  who=$(pg psql -Atc "SELECT current_database() || '/' || current_user") \
    || die "拒否: 接続先を確認できませんでした。"
  [ "$who" = "${ALLOWED_DB}/${ALLOWED_USER}" ] \
    || die "拒否: 接続先が ${who} です。許可しているのは ${ALLOWED_DB}/${ALLOWED_USER} だけです。"

  # 3. どちらの Cloud SQL かは URL からは判らない（proxy 越しは常に 127.0.0.1）。
  #    **最後は人間に見せて止める。**
  echo "破壊的な操作の宛先: ${PGUSER}@${PGHOST}:${PGPORT}/${PGDATABASE}"
  echo "  （ポートが指す Cloud SQL インスタンスを cloud-sql-proxy の起動コマンドで確認すること）"
  if [ "${MIGRATE_DATA_ASSUME_YES-}" = 1 ]; then
    echo "  MIGRATE_DATA_ASSUME_YES=1 のため確認を省略します。"
    return
  fi
  local ans
  read -r -p "続行するには yes と入力: " ans < /dev/tty
  [ "$ans" = yes ] || die "中止しました。"
}

cmd_counts() {
  # **数えるテーブルを手で並べない。** カタログから引く。
  #
  # 一覧を書くと、モデルが増えたときに書き漏らす。**そのとき突合は
  # 「一致」と報告する** — 移送元でも移送先でも同じ 1 テーブルを見落とすからである。
  # 何も失っていないことを示すのが唯一の仕事のコマンドが、
  # 一生に一度しか使わない日に黙って通る。
  #
  # このリポジトリは同じ失敗を一度している（api/alembic/env.py のコメントを参照。
  # モデルの import を手で並べて AppSetting と OrderSource を取りこぼしていた）。
  # そこでの答えと同じく、列挙をやめて導出する。
  #
  # 副産物として alembic_version も数に入る。**移送後の migrate Job が no-op に
  # なることの確認**は、手で並べた一覧では取りこぼしていた。
  #
  # 1 文なので断面は自動的に揃う（テーブルごとに叩くと数えている間に値が動く）。
  pg psql -v ON_ERROR_STOP=1 -Atc "
    SELECT c.relname || '|' ||
           (xpath('/row/c/text()', query_to_xml(
              format('SELECT count(*) AS c FROM %I.%I', n.nspname, c.relname),
              false, true, '')))[1]::text::bigint
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relkind = 'r' AND n.nspname = 'public'
     ORDER BY c.relname;"
}

# 「移行前後で各件数が一致する」（REQ-0054 の受入基準）を人間の目視で終わらせない。
# **差があれば異常終了する。** メンテナンス枠の終わりに 2 画面を見比べる作業にしない。
cmd_compare() {
  [ $# -eq 2 ] || usage
  local src="$1" dst="$2"
  if diff -u "$src" "$dst"; then
    echo "✅ 全テーブルの件数が一致（$(grep -c . "$src") テーブル）"
  else
    die "❌ 件数が一致しません。移送は完了していません。"
  fi
}

# **移送元の件数をダンプそのものから数える。**
#
# 移送元に繋がずに済むのが要点である。カットオーバーでは依頼者が手元で
# pg_dump を取るので（REQ-0054）、こちらから Railway へ接続する経路は無い。
#
# ただし **これだけでは「移送できた」ことの証明にならない。**
# src と dst の両方がこのダンプから派生してしまうため、compare が確かめるのは
# 「ダンプ → 移送先」の一段だけになり、**「移送元 → ダンプ」で落ちたものは
# 両側から等しく消えて一致と報告される**（`-t` / `-T` を付けて取ると起きる）。
# そこで、**ダンプの外にある正本**＝アプリのモデル定義と突き合わせる。
#
# reset は破壊的で後戻りできない。**その手前に立つ唯一の関門がここ**なので、
# 形式の異常（不完全・データのみ・INSERT 形式）もここで落とす。
cmd_counts_dump() {
  [ $# -eq 1 ] || usage
  local dump="$1"
  [ -r "$dump" ] || die "読めません: $dump"
  python3 - "$dump" "$(dirname "$0")/../../api/app/models" <<'PYEOF'
import pathlib, re, sys

dump = sys.argv[1]

# ダンプの外にある正本。**ここを手で並べない。**
# 一覧を手書きすると、モデルが増えたときに書き漏らし、
# その 1 テーブルが落ちても「一致」と報告される（このリポジトリは
# api/alembic/env.py で同じ失敗をしている）。
models = pathlib.Path(sys.argv[2])
expected = {m.group(1) for f in models.glob("*.py")
            for m in re.finditer(r'__tablename__\s*=\s*"([^"]+)"', f.read_text(encoding="utf-8"))}
if not expected:
    sys.exit(f"モデル定義が読めません: {models}")
expected.add("alembic_version")  # モデルではないが移送の対象

# **完結しているか**を先に見る。転送で切れたダンプと、-t/-T で意図的に
# 減らされたダンプは症状が同じ（テーブルが足りない）なので、ここで区別する。
with open(dump, "rb") as f:
    try:
        f.seek(-4096, 2)
    except OSError:
        f.seek(0)
    if b"PostgreSQL database dump complete" not in f.read():
        sys.exit("ダンプが完結していません（転送が途中で切れています）。取り直してください。")

counts, table, crlf, creates, headers = {}, None, False, 0, 0
with open(dump, "rb") as f:
    for raw in f:
        if raw.endswith(b"\r\n"):
            crlf = True
        line = raw.decode("utf-8", "surrogateescape").rstrip("\r\n")
        if table is None:
            if line.startswith("CREATE TABLE "):
                creates += 1
            elif line.startswith("COPY ") and line.endswith("FROM stdin;"):
                headers += 1
                m = re.match(r'COPY (?:([A-Za-z_][A-Za-z0-9_]*)\.)?"?([A-Za-z_][A-Za-z0-9_]*)"?\s*\(.*\) FROM stdin;', line)
                if not m:
                    # 解釈できない形は落とす。**黙って 1 テーブル消えるより良い。**
                    sys.exit(f"COPY ヘッダを解釈できません: {line}")
                schema, table = m.group(1) or "public", m.group(2)
                if table in counts:
                    sys.exit(f"テーブル名が重複しています（{schema}.{table}）。public 以外のスキーマが混ざっていませんか？")
                counts[table] = 0
        elif line == r"\.":
            # データ中の `\` は `\\` に逃がされるので、2 文字の `\.` だけの行は
            # 終端にしかならない（COPY のテキスト形式の仕様）。
            table = None
        else:
            counts[table] += 1

if table is not None:
    sys.exit(f"ダンプが途中で終わっています（{table} の COPY が閉じていません）。")

# **形式の異常は reset の手前で落とす。** ここを通すと、移送先を壊してから
# 「実は流し込めないダンプだった」と判ることになる。
if not counts:
    if headers == 0 and creates == 0:
        sys.exit("COPY も CREATE TABLE もありません。--format=plain のダンプですか？")
    sys.exit("データがありません（--schema-only で取っていませんか？）。")
if creates == 0:
    sys.exit("CREATE TABLE がありません（--data-only で取っていませんか？）。")
if crlf:
    sys.exit("改行コードが CRLF です。**転送の途中で書き換えられた合図なので信用しない。**"
             " LF のまま受け渡して取り直してください。")

# **ダンプの外の正本と突き合わせる。** これが無いと、-t / -T で
# テーブルごと落ちたダンプが「一致」と報告される。
missing = expected - counts.keys()
if missing:
    sys.exit(f"ダンプに無いテーブル: {sorted(missing)}。-t / -T が付いていませんか？")

for t in sorted(counts):
    print(f"{t}|{counts[t]}")
PYEOF
}

cmd_dump() {
  local out="${1:?usage: dump <PGURL> <OUT>}"
  # --no-owner / --no-acl: 移送先に Railway のロールは存在しない。
  #   付けないと restore が所有者の付け替えで落ちる。
  pg pg_dump --no-owner --no-acl --format=plain > "$out"
  echo "取得: $out ($(wc -c < "$out" | tr -d ' ') bytes)"
}

# **件数が合っていてもアプリは動かない。**
#
# 移送元のコード世代が古ければ、ダンプのスキーマも古い。移送先では新しい
# コードが動くので、存在しない列を触って 500 になる。**実際に踏んだ** —
# 本番で manufacturing_data.lease_expires_at が無く、受注一覧が落ちた
# （REQ-0054）。**そのとき件数の突合は通っていた。** 件数は関係ないからである。
#
# 手順書に「migrate Job を流す」と書くだけでは、飛ばした人を止められない。
# 流し込んだ直後に、機械が気づいて言う。
assert_schema_at_head() {
  local head db_rev
  head=$(python3 "$(dirname "$0")/alembic-head.py" "$(dirname "$0")/../../api/alembic/versions" 2>/dev/null || echo "")
  db_rev=$(pg psql -Atc "SELECT version_num FROM alembic_version" 2>/dev/null || echo "")

  case "$head" in
    "")      echo "警告: alembic のヘッドを判定できませんでした。手動で確認してください。" >&2 ;;
    MULTI:*) echo "警告: alembic のヘッドが複数あります（${head#MULTI:}）。本番の起動が壊れます。マージマイグレーションが要ります。" >&2 ;;
    "$db_rev") echo "スキーマはコードに追いついています（${db_rev}）。" ;;
    *)
      echo "" >&2
      echo "**このままではアプリが 500 になります。**" >&2
      echo "  流し込んだスキーマ: ${db_rev:-（不明）}" >&2
      echo "  コードが要求する  : ${head}" >&2
      echo "  → migrate Job を実行してください（カットオーバー手順 5）:" >&2
      echo "     gcloud run jobs execute pod-admin-migrate --project=<PROJECT> --region=<REGION> --wait" >&2
      ;;
  esac
}

cmd_reset() {
  # **カットオーバーの直前に必ず実行する。** PR 1 で migrate Job を流したので
  # 移送先にはスキーマが入っており、pg_dump の CREATE TABLE が衝突する。
  # 「今どうなっているか」で分岐せず、常に同じ状態から始める。
  #
  # AUTHORIZATION と GRANT を明示するのは、**作り直した public が
  # 初期状態と同じ権限を持たないから**である。--no-acl のダンプは
  # 権限を持ってこないので、ここで戻さないと後から誰も直せない。
  pg psql -v ON_ERROR_STOP=1 \
    -c "DROP SCHEMA public CASCADE;" \
    -c "CREATE SCHEMA public AUTHORIZATION pg_database_owner;" \
    -c "GRANT USAGE ON SCHEMA public TO PUBLIC;"
  echo "public スキーマを作り直しました。"
}

cmd_restore() {
  local dump="${1:?usage: restore <PGURL> <DUMP>}"
  # --single-transaction: 途中で落ちたときに**中途半端に入った状態を残さない。**
  # 移送元が第三者から受け取ったダンプの場合、これが唯一の防波堤になる。
  pg psql -v ON_ERROR_STOP=1 -q --single-transaction < "$dump"
  # **統計を作ってから引き渡す。** 直後の動作確認（カットオーバー手順 7）が
  # 後戻りできない手順 8 の判断材料になる。統計が無いと素の全表走査になり、
  # 「移送が壊れている」のか「統計がまだ無い」のかを操作者が区別できない。
  #
  # public のテーブルだけを対象にする。**素の `VACUUM ANALYZE` はシステム
  # カタログにも触れにいって WARNING を出す**（pg_parameter_acl など、
  # 移送に使う権限では触れない）。当日の出力に警告を混ぜない。
  pg psql -v ON_ERROR_STOP=1 -q -c "
    DO \$\$
    DECLARE t record;
    BEGIN
      FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ANALYZE public.%I', t.tablename);
      END LOOP;
    END
    \$\$;"
  echo "流し込みと VACUUM ANALYZE が完了。"
  assert_schema_at_head
}

[ $# -ge 2 ] || usage
sub="$1"; shift

# この 2 つは DB に繋がない（ファイルを読むだけ）。
case "$sub" in
  compare)     cmd_compare "$@"; exit 0 ;;
  counts-dump) cmd_counts_dump "$@"; exit 0 ;;
esac

PGURL="$1"; shift

# **psql と pg_dump は同じ出どころに揃える。** 片方だけ手元にある環境で
# 混ざると、ヘッダが約束している「client も 16」が崩れる。
if command -v psql >/dev/null 2>&1 && command -v pg_dump >/dev/null 2>&1; then
  USE_DOCKER=no
else
  USE_DOCKER=yes
fi
parse_pgurl "$PGURL"
export PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE

# **宛先の検査は dispatch で行う。** 各サブコマンドの中に置くと、
# あとから破壊的なサブコマンドを足した人が呼び忘れても何も起きない。
case "$sub" in
  reset|restore) assert_writable_target ;;
  counts|dump)   ;;   # 読み取りのみ。移送元に対しても使える
  *)             usage ;;
esac

case "$sub" in
  counts)  [ $# -eq 0 ] || usage; cmd_counts ;;
  dump)    cmd_dump "$@" ;;
  reset)   [ $# -eq 0 ] || usage; cmd_reset ;;
  restore) cmd_restore "$@" ;;
esac
