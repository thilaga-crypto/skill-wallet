@echo off
echo Checking what is using port 8000...
echo.
netstat -ano | findstr :8000
echo.
echo If you see LISTENING above, the last number is the PID of the old application.
echo You do NOT need to stop it to use this fixed FitBuddy version because FitBuddy now runs on port 5050.
pause
