output "budget_name" {
  description = "Billing budget resource name"
  value       = google_billing_budget.monthly.name
}

output "notification_channel_name" {
  description = "Monitoring notification channel resource name"
  value       = google_monitoring_notification_channel.email.name
}
