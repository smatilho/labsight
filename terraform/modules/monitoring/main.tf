resource "google_monitoring_notification_channel" "email" {
  display_name = "Labsight Owner Email"
  type         = "email"
  project      = var.project_id

  labels = {
    email_address = var.owner_email
  }
}

resource "google_billing_budget" "monthly" {
  billing_account = var.billing_account_id
  display_name    = "Labsight Monthly Budget"

  budget_filter {
    projects = ["projects/${var.project_id}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_amount)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.8
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "CURRENT_SPEND"
  }

  all_updates_rule {
    monitoring_notification_channels = [
      google_monitoring_notification_channel.email.name,
    ]
    enable_project_level_recipients = true
  }
}
