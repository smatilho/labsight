terraform {
  backend "gcs" {
    bucket = "labsight-terraform-state"
    prefix = "terraform/state"
  }
}
