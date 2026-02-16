output "static_ip" {
  description = "Static IP for DNS A record"
  value       = google_compute_global_address.frontend.address
}

output "frontend_iap_url" {
  description = "IAP-protected frontend URL"
  value       = "https://${var.domain}"
}
