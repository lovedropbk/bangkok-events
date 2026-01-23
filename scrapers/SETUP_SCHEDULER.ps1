$taskName = "BangkokEventsScraper"
$scriptPath = "C:\Users\Patrick\coding\event_party_app\scrapers\AUTO_SCRAPE.bat"

# Create a scheduled task to run daily at 1 PM
$action = New-ScheduledTaskAction -Execute $scriptPath
$trigger = New-ScheduledTaskTrigger -Daily -At "1:00PM"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register the task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Scrapes Bangkok events from Facebook daily and deploys to Vercel" -Force

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " SCHEDULED TASK CREATED!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Task Name: $taskName"
Write-Host "Schedule: Daily at 1:00 PM"
Write-Host "Script: $scriptPath"
Write-Host ""
Write-Host "To run manually: schtasks /run /tn $taskName"
Write-Host "To check status: schtasks /query /tn $taskName"
Write-Host "To delete: schtasks /delete /tn $taskName /f"
Write-Host ""
