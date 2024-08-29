@echo off
REM Prompt the user to input environment variable values
set /p data_source="Enter the path for data_source (e.g., C:\Users\%currentUser%\VTDownloader\db\files_info.db): "
set /p malware_destination="Enter the path for malware_destination (e.g., C:\malware): "
set /p fp_destination="Enter the path for fp_destination (e.g., D:\FP): "

REM Set the environment variables
setx data_source "%data_source%"
setx malware_destination "%malware_destination%"
setx fp_destination "%fp_destination%"
pause
