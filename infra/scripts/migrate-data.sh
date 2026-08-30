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
# あればそれを使い、無ければ docker の postgres:16-alpine で実行する。
# **当日に初めて pull すると 411MB の取得が待ち時間になる。**
# 前日までに `docker pull postgres:16-alpine` を済ませておく。
set -euo pipefail

# 移送先の Cloud SQL に合わせる。正本は infra/modules/cloud-sql/main.tf の
# database_version（POSTGRES_16）。**client を server より古くしない。**
readonly PG_IMAGE="postgres:16-alpine"

# 破壊的な操作を許可する宛先。Terraform が決めている値と揃える
# （infra/modules/stack/main.tf の cloud_sql: database_name / user_name）。
readonly ALLOWED_DB=pod_admin
readonly ALLOWED_USER=pod_admin

# 行番号で切り出すと、ヘッダを書き換えるたびに黙ってずれる（実際ずれていた）。
usage() { sed -n '/^#   counts/,/^#   compare/p' "$0" >&2; exit 2; }

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
  case "${PGHOST-}" in
    127.0.0.1|localhost|::1) ;;
    "") die "拒否: 接続先が空です。破壊的な操作に既定接続（PG* 環境変数）は使えません。" ;;
    *)  die "拒否: 接続先 ${PGHOST} は Cloud SQL Auth Proxy ではありません。" ;;
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
  local src="${1:?usage: compare <SRC> <DST>}" dst="${2:?usage: compare <SRC> <DST>}"
  if diff -u "$src" "$dst"; then
    echo "✅ 全テーブルの件数が一致（$(grep -c . "$src") テーブル）"
  else
    die "❌ 件数が一致しません。移送は完了していません。"
  fi
}

cmd_dump() {
  local out="${1:?usage: dump <PGURL> <OUT>}"
  # --no-owner / --no-acl: 移送先に Railway のロールは存在しない。
  #   付けないと restore が所有者の付け替えで落ちる。
  pg pg_dump --no-owner --no-acl --format=plain > "$out"
  echo "取得: $out ($(wc -c < "$out" | tr -d ' ') bytes)"
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
  pg psql -v ON_ERROR_STOP=1 -q -c "VACUUM ANALYZE;"
  echo "流し込みと VACUUM ANALYZE が完了。"
}

[ $# -ge 2 ] || usage
sub="$1"; shift

# compare だけは DB に繋がない（counts の出力ファイル 2 つを比べるだけ）。
if [ "$sub" = compare ]; then
  cmd_compare "$@"
  exit 0
fi

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
  counts|dump)   ;;   # 読み取りのみ。移送元（Railway）に対して使う
  *)             usage ;;
esac

case "$sub" in
  counts)  [ $# -eq 0 ] || usage; cmd_counts ;;
  dump)    cmd_dump "$@" ;;
  reset)   [ $# -eq 0 ] || usage; cmd_reset ;;
  restore) cmd_restore "$@" ;;
esac
