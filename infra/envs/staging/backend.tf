# state バケットは Terraform で作れない（鶏卵）ため、先に
# infra/scripts/bootstrap-state-bucket.sh で作る。
terraform {
  backend "gcs" {
    bucket = "tosyo-api-stg-tfstate"
    prefix = "envs/staging"
  }
}
