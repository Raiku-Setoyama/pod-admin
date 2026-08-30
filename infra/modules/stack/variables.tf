variable "project_id" {
  type = string
}

variable "region" {
  # 既定値は置かない。env は provider の設定にも同じ値が要るので、
  # どのみち自分で持つ必要がある。
  type = string
}

variable "env" {
  description = <<-DESC
    環境名。ラベルと GCS のプレフィックスに使う。
    **リソース名には入れない**（環境ごとにプロジェクトが分かれるため）。
  DESC
  type        = string

  validation {
    # GCS_PREFIX になるので、オブジェクトのパスに出せない文字を弾く。
    condition     = can(regex("^[a-z][a-z0-9-]*$", var.env))
    error_message = "env は英小文字で始まる英小文字・数字・ハイフンにしてください。"
  }
}

variable "github_repository" {
  description = "デプロイを許可する GitHub リポジトリ（owner/repo）"
  type        = string
}

variable "gcs_bucket_name" {
  description = "業務ファイルの保管バケット（グローバルに一意）"
  type        = string
}

variable "gcs_retention_days" {
  description = <<-DESC
    アップロードしたファイルを保持する日数。null なら消さない。
    **使い捨て環境専用。** 業務ファイル（製造データ・請求書・チャット添付）は
    参照期限が読めず、消すと DB に残った file_path が実体を失う（ADR-0032）。
  DESC
  type        = number
  default     = null

  validation {
    # ADR-0032 を散文ではなく機械で守る。**消えても困らない環境**
    # （＝バケットごと壊してよい環境）でしか日数を設定させない。
    condition     = var.gcs_retention_days == null || var.gcs_force_destroy
    error_message = "gcs_force_destroy = false の環境で gcs_retention_days は設定できません（ADR-0032）。"
  }
}

variable "gcs_force_destroy" {
  description = <<-DESC
    true にすると中身ごと destroy できる。
    **この値が「使い捨ててよい環境か」の唯一の表明である。**
    false の環境では、下の 2 つが機械的に強制される。
      - 業務ファイルにライフサイクル削除を設定できない（ADR-0032）
      - Cloud Run のリソースが destroy で消せなくなる
  DESC
  type        = bool
}

variable "db_tier" {
  type = string
}

variable "db_disk_size_gb" {
  type = number
}

variable "db_disk_autoresize_limit" {
  description = "ディスク自動拡張の上限（GB）。0 は無制限"
  type        = number
}

variable "db_deletion_protection" {
  type = bool
}

variable "db_pitr_enabled" {
  description = <<-DESC
    ポイントインタイムリカバリ。WAL の保管料がかかる。
    **本番では有効にする。** 日次バックアップだけでは、障害の直前まで戻せない。
  DESC
  type        = bool
}

variable "db_retained_backups" {
  description = "保持する自動バックアップの世代数"
  type        = number
}

variable "db_max_connections" {
  description = <<-DESC
    Cloud SQL の max_connections。明示的に固定する。
    ティアごとの既定値はメモリ量から算出されるため、値を仮定して
    プールを設計すると本番で枯渇する。
  DESC
  type        = number

  validation {
    # 接続数の予算を人間の暗算に任せない。
    # api は max_instances 個まで並ぶ。worker と migrate は Job なので 1 実行ずつ。
    # 残りは管理接続（psql・Cloud SQL 自身）の予備として空けておく。
    condition = (
      (var.api_max_instances + 2) * (var.db_pool_size + var.db_max_overflow)
      <= var.db_max_connections - 5
    )
    error_message = "接続数が max_connections に収まりません。(api_max_instances + 2) × (db_pool_size + db_max_overflow) が db_max_connections - 5 を超えています。"
  }
}

variable "api_min_instances" {
  description = <<-DESC
    常時起動しておく api のインスタンス数。
    0 だとコールドスタート（実測 約 15 秒）を踏む。外部販売サイトの
    タイムアウトが短い、またはリトライしない実装なら 1 にする。
  DESC
  type        = number
  default     = 0
}

variable "api_max_instances" {
  type = number
}

variable "web_max_instances" {
  type = number
}

variable "db_pool_size" {
  description = "1 インスタンスあたりの常設接続数"
  type        = number
}

variable "db_max_overflow" {
  description = "1 インスタンスあたりの追加接続数の上限"
  type        = number
}

variable "worker_max_runtime_seconds" {
  description = <<-DESC
    ワーカーが 1 回の起動で処理を続ける上限秒数。
    **ワーカーは Cloud Run Job のタイムアウトより先に自分で降りる。**
    Job 側のタイムアウトはこの値から導出する（main.tf の locals）。
  DESC
  type        = number
  default     = 600
}

variable "worker_max_items" {
  description = "ワーカーが 1 回の起動で処理する件数の上限"
  type        = number
  default     = 20
}

variable "worker_schedule" {
  type = string
}

variable "worker_schedule_paused" {
  description = "true ならワーカーの定期起動を止めた状態で作る"
  type        = bool
}

variable "illustrator_vm_base_url" {
  description = "製造データ生成 VM の URL。空なら生成機能を無効にする"
  type        = string
  default     = ""
}

variable "sendgrid_from_email" {
  type    = string
  default = ""
}

variable "contact_email" {
  type    = string
  default = ""
}
