# Card Auto Add

The goal of this project is to automatically add member cards to a WinDSX database. It runs as a windows service and uses the WinDSX API to talk to the system. It's still in its infancy and could use some TLC still.


## Instructions:
Our goal is to create a Windows Service that can run in the background on a machine running WinDSX and add cards without any user interaction. Since the version of WinDSX this was made for has an API, we write to that API format. Unfortunately, the program needs to be opened and logged into so this service tries to manage that as well.

### Create Service exe
pyinstaller -F --hidden-import=win32timezone --paths
 "%CSIDL_LOCAL_APPDATA%\Programs\Python\Python38-32\Lib\site-packages" --hidden-import="sentry_sdk.integration
s.logging" --hidden-import="sentry_sdk.integrations.stdlib" --hidden-import="sentry_sdk.integrations.excepthook" --hidden-im
port="sentry_sdk.integrations.dedupe" --hidden-import="sentry_sdk.integrations.atexit" --hidden-import="sentry_sdk.integrati
ons.modules" --hidden-import="sentry_sdk.integrations.argv" --hidden-import="sentry_sdk.integrations.threading" main.py
