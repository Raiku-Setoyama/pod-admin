#!/usr/bin/env bash
# Terraform の state 置き場を作る。
#
# state バケットだけは Terraform で管理できない（自分の state をどこに置くかを
# 決めるのが backend の設定なので、鶏と卵になる）。ここだけ gcloud で作る。
#
# **state には DB のパスワードが平文で入る。** バージョニングを有効にし、
# バケットへのアクセスは UBLA で IAM に一本化する。
#
#   使い方: bootstrap-state-bucket.sh <PROJECT_ID> [LOCATION]
set -euo pipefail

PROJECT_ID="${1:?usage: $0 <PROJECT_ID> [LOCATION]}"
LOCATION="${2:-asia-northeast1}"
BUCKET="gs://${PROJECT_ID}-tfstate"

if gcloud storage buckets describe "$BUCKET" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "already exists: $BUCKET"
else
  gcloud storage buckets create "$BUCKET" \
    --project="$PROJECT_ID" \
    --location="$LOCATION" \
    --uniform-bucket-level-access \
    --public-access-prevention
  echo "created: $BUCKET"
fi

gcloud storage buckets update "$BUCKET" --project="$PROJECT_ID" --versioning
echo "versioning enabled: $BUCKET"
