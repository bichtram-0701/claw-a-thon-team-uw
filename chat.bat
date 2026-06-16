@echo off
title Funnel Agent - Team UW
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$url = 'https://endpoint-2f37c067-4516-4483-ba07-2199f07abb90.agentbase-runtime.aiplatform.vngcloud.vn/invocations';" ^
  "Write-Host ''; Write-Host '=== Funnel Agent (live on AgentBase) ===' -ForegroundColor Green;" ^
  "Write-Host 'Try: /funnel show me the funnel metrics | /jira what is critical or off track | /confluence weekly meeting summary | /model' -ForegroundColor DarkGray;" ^
  "Write-Host 'Press Enter on an empty line to quit.' -ForegroundColor DarkGray; Write-Host '';" ^
  "while ($true) {" ^
  "  $q = Read-Host 'You';" ^
  "  if ([string]::IsNullOrWhiteSpace($q)) { break };" ^
  "  try {" ^
  "    $body = [System.Text.Encoding]::UTF8.GetBytes((@{ message = $q } | ConvertTo-Json));" ^
  "    $r = Invoke-RestMethod -Method Post -Uri $url -ContentType 'application/json; charset=utf-8' -Body $body;" ^
  "    Write-Host ('Agent (' + $r.intent + '):') -ForegroundColor Cyan;" ^
  "    if ($r.answer) { Write-Host $r.answer } else { $r.result | ConvertTo-Json -Depth 6 | Write-Host };" ^
  "  } catch { Write-Host ('Error: ' + $_.Exception.Message) -ForegroundColor Red };" ^
  "  Write-Host '';" ^
  "}"
