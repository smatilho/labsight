.PHONY: tf-init tf-plan tf-apply tf-destroy tf-fmt tf-validate tf-output

TF_DIR = terraform

tf-init:
	cd $(TF_DIR) && terraform init

tf-plan:
	cd $(TF_DIR) && terraform plan

tf-apply:
	cd $(TF_DIR) && terraform apply

tf-destroy:
	cd $(TF_DIR) && terraform destroy

tf-fmt:
	cd $(TF_DIR) && terraform fmt -recursive

tf-validate:
	cd $(TF_DIR) && terraform validate

tf-output:
	cd $(TF_DIR) && terraform output
