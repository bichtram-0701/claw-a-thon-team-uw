@echo off
title Lending Watchdog - Team UW
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$url = 'https://endpoint-02241868-df01-4fa2-9b36-45145561851c.agentbase-runtime.aiplatform.vngcloud.vn/invocations';" ^
  "Write-Host ''; Write-Host '=== Lending Portfolio Watchdog (live on AgentBase) ===' -ForegroundColor Green;" ^
  "Write-Host 'Try: portfolio summary | at-risk accounts | breakdown by province | by segment' -ForegroundColor DarkGray;" ^
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
