$ErrorActionPreference = "Stop"
$base = $env:NEXT_PUBLIC_API_BASE_URL
if (-not $base) { $base = "http://127.0.0.1:8000" }

Write-Host "Health:"
Invoke-RestMethod "$base/health" | ConvertTo-Json -Compress

Write-Host "Mode:"
Invoke-RestMethod "$base/api/v1/mode" | ConvertTo-Json -Compress

Write-Host "Demo profiles:"
(Invoke-RestMethod "$base/api/v1/profiles/demo").Count

$body = @{
  profile_ids = @("demo-profile-maya","demo-profile-jordan","demo-profile-sam")
  target_domain = "urn:entity:place"
  location_query = "New York"
  experience = "evening_out"
  take = 6
} | ConvertTo-Json

$plan = Invoke-RestMethod -Method POST -Uri "$base/api/v1/concierge/plan" -ContentType "application/json" -Body $body
Write-Host "Plan primary:" $plan.primary.name "mode=" $plan.mode "source=" $plan.primary.source

$rejected = $plan.primary.entity_id
$regen = Invoke-RestMethod -Method POST -Uri "$base/api/v1/concierge/plan/$($plan.id)/reject?entity_id=$rejected"
Write-Host "Regenerated primary:" $regen.primary.name
if ($regen.primary.entity_id -eq $rejected) { throw "Reject did not change primary" }
Write-Host "SMOKE OK"
