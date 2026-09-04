variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "env" {
  description = "ラベルに入る環境名"
  type        = string
}

variable "subnetwork_id" {
  description = "VM を置くサブネット。modules/network の出力を渡す"
  type        = string
}

variable "network_tag" {
  description = <<-DESC
    ファイアウォールの適用先になるネットワークタグ。
    **modules/network の `illustrator_target_tag` 出力を渡す。文字列を直書きしない。**
  DESC
  type        = string
}

variable "internal_ip" {
  description = <<-DESC
    予約する内部 IP。**modules/network の VM 用サブネットの範囲内であること。**
    生成 API の宛先になるので、呼び出し側は同じ値から
    `illustrator_vm_base_url` を組み立てる。
  DESC
  type        = string
}

variable "source_image" {
  description = <<-DESC
    起動元のイメージ。**移送元のディスクから作ったものを、このプロジェクトへ
    コピーしたものを指す。** 個人プロジェクトのイメージを直接指すと、
    それを消した時点で作り直せなくなる。

    **ブートディスクの作成にしか使われない**（`ignore_changes` を参照）。
  DESC
  type        = string
}
